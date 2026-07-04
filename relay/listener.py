"""Loop principal do relay: LISTEN outbox_novo + poll de seguranca (RF-018).

Abre uma conexao psycopg2 DEDICADA (fora do pool do engine) em autocommit para
``LISTEN outbox_novo`` e fica em ``select`` aguardando notificacao OU timeout
de poll (``OUTBOX_POLL_SEGUNDOS``, default 5s). A cada acorde (NOTIFY ou
timeout) drena a fila chamando ``processar_ciclo`` (claim-then-deliver com
lease) repetidamente ate nao haver mais linhas elegiveis — o poll cobre
eventos perdidos (NOTIFY e best-effort se o relay estava fora no momento do
COMMIT), linhas reagendadas por backoff e linhas cujo lease venceu apos um
crash de entrega.

Resiliencia da conexao de LISTEN (#165): a conexao dedicada leva keepalives
TCP (um failover/NAT/LB que mata o socket em silencio deixaria o relay surdo
a NOTIFY para sempre — o poll de seguranca mascararia com latencia; com
keepalives o kernel detecta a morte e o ``select``/``poll`` levanta erro) e,
ao cair, e fechada e reconstruida com backoff incremental (teto 30s) SEM
derrubar o processo — derrubar reiniciaria o pod a cada blip (restart-storm).

Heartbeat (F6): o relay faz ``touch`` no arquivo ``RELAY_HEARTBEAT`` (default
``/tmp/relay-heartbeat``) antes de CADA ciclo de drain (#163), nao apenas por
acorde — uma fila profunda segura o drain em lotes sucessivos por minutos e a
``livenessProbe`` do k8s (janela de 60s) reiniciaria um pod saudavel. A probe
falha se o heartbeat ficar velho — assim um SMTP travado (apesar do timeout do
adapter) ou um loop preso reinicia o pod, em vez de ``kill -0 1`` passar com o
processo vivo porem inerte.

O processamento usa o ``engine`` SQLAlchemy (pool); a conexao de LISTEN e
dedicada e separada do pool de trabalho — por isso o autocommit dela nunca
contamina transacoes de trabalho nem precisa ser restaurado no shutdown.
"""

from __future__ import annotations

import contextlib
import os
import select
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from relay.processador import emitir_profundidade, processar_ciclo
from src.compartilhado.infraestrutura.outbox_mapping import CANAL_NOTIFY
from src.ordem_servico.infraestrutura.email_adapter import (
    _TIMEOUT_SEGUNDOS as _TIMEOUT_SMTP_S,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime
    from typing import Any

    from sqlalchemy import Engine

_log = structlog.get_logger(__name__)

_POLL_PADRAO = 5.0
# Lote pequeno por padrao (F3): a janela de duplicacao em crash e <= ao lote
# em voo; commit por linha ja limita a 1, o lote pequeno limita o trabalho
# perdido por ciclo.
_LOTE_PADRAO = 10
# Lease (visibility timeout) > timeout do SMTP (5s no adapter): em crash de
# entrega a linha so volta a ser elegivel apos o lease vencer (F3).
#
# INVARIANTE DE HA (design §5.5/§9): o lease DEVE exceder a latencia de pior
# caso de uma unica chamada de handler (limitada pelo timeout do SMTP). Em
# ``replicas:1`` o drain sequencial torna isso seguro — um so worker, a linha
# em voo nao re-elegivel durante a entrega. Escalar para ``replicas>1`` exige
# que essa invariante se mantenha (ou um fencing no momento da entrega): se o
# lease vencer no meio de uma entrega lenta, outra replica re-reivindica a
# mesma linha e o e-mail duplica. O default 60s >> timeout do SMTP cobre a
# folga; NAO baixar abaixo do timeout de entrega do adapter (validado em
# ``_config_do_ambiente`` contra ``_TIMEOUT_SMTP_S``, a constante do adapter).
_LEASE_PADRAO = 60
# Caminho efemero do pod (sobrescrito por RELAY_HEARTBEAT); intencional.
_HEARTBEAT_PADRAO = "/tmp/relay-heartbeat"  # noqa: S108  # nosec B108
# Throttle do gauge structlog em fila ociosa: com poll de 5s, 12 acordes
# ~= 1 log de profundidade por minuto (em vez de 1 a cada 5s). Um drain que
# processou >= 1 linha loga imediatamente; o ObservableGauge OTel
# (relay/metrics.py) segue continuo, por scrape.
_ACORDES_POR_LOG = 12
# Backoff da reconstrucao da conexao de LISTEN (#165): incremental dobrado com
# teto. Teto de 30s < janela de 60s da livenessProbe — o heartbeat tocado a
# cada tentativa mantem o pod vivo enquanto o DB nao volta (reiniciar o pod
# nao conserta o DB e desmontaria o LISTEN a cada blip).
_RECONEXAO_BASE_S = 1.0
_RECONEXAO_TETO_S = 30.0
# Keepalives TCP da conexao dedicada de LISTEN (parametros libpq/psycopg2):
# sonda apos 30s ocioso, a cada 10s, 3 falhas => socket morto detectado em
# ~60s. Sem isso, um peer que sumiu em silencio deixa o select bloqueado num
# socket zumbi e o relay surdo a NOTIFY.
_KEEPALIVES_LISTEN: dict[str, int] = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}


def _int_do_ambiente(nome: str, padrao: int) -> int:
    """Le um inteiro do ambiente; misconfig vira erro claro no boot."""
    bruto = os.environ.get(nome, str(padrao))
    try:
        return int(bruto)
    except ValueError as exc:
        msg = f"config invalida no boot: {nome}={bruto!r} (esperado numero inteiro)"
        raise RuntimeError(msg) from exc


def _float_do_ambiente(nome: str, padrao: float) -> float:
    """Le um numero do ambiente; misconfig vira erro claro no boot."""
    bruto = os.environ.get(nome, str(padrao))
    try:
        return float(bruto)
    except ValueError as exc:
        msg = f"config invalida no boot: {nome}={bruto!r} (esperado numero)"
        raise RuntimeError(msg) from exc


def _config_do_ambiente() -> tuple[float, int, timedelta]:
    """Le poll/lote/lease do ambiente com defaults seguros, validando no boot.

    Falha RAPIDO (``RuntimeError``) em misconfig, em vez de estourar com um
    ``ValueError`` criptico ou — pior — aceitar um valor que quebra invariante
    em producao: valor nao numerico, ``poll``/``lote`` nao positivos ou
    ``lease <= _TIMEOUT_SMTP_S`` (o timeout de entrega do adapter SMTP). Um
    lease menor que a entrega em voo re-elegibiliza a linha NO MEIO da entrega
    e duplica o e-mail em ``replicas>1`` (invariante de HA, design §5.5).
    """
    poll = _float_do_ambiente("OUTBOX_POLL_SEGUNDOS", _POLL_PADRAO)
    lote = _int_do_ambiente("OUTBOX_LOTE", _LOTE_PADRAO)
    lease_s = _int_do_ambiente("OUTBOX_LEASE_SEGUNDOS", _LEASE_PADRAO)
    if poll <= 0:
        msg = f"config invalida no boot: OUTBOX_POLL_SEGUNDOS={poll} (esperado > 0)"
        raise RuntimeError(msg)
    if lote <= 0:
        msg = f"config invalida no boot: OUTBOX_LOTE={lote} (esperado > 0)"
        raise RuntimeError(msg)
    if lease_s <= _TIMEOUT_SMTP_S:
        msg = (
            f"config invalida no boot: OUTBOX_LEASE_SEGUNDOS={lease_s} deve "
            f"exceder o timeout de entrega SMTP ({_TIMEOUT_SMTP_S}s) — lease "
            "menor que a entrega em voo re-elegibiliza a linha durante a "
            "entrega e duplica o e-mail (design §5.5)"
        )
        raise RuntimeError(msg)
    return poll, lote, timedelta(seconds=lease_s)


def _heartbeat() -> None:
    """Atualiza o mtime do arquivo de heartbeat (liveness do F6)."""
    caminho = Path(os.environ.get("RELAY_HEARTBEAT", _HEARTBEAT_PADRAO))
    caminho.touch()


def _conectar_listen(engine: Engine) -> Any:  # noqa: ANN401 — conexao DBAPI (psycopg2) crua
    """Abre a conexao DEDICADA de LISTEN (psycopg2 direto, fora do pool).

    Nao usa ``engine.raw_connection()`` de proposito: (1) keepalives TCP sao
    parametros de CONEXAO (libpq) e o pool nao aceita connect_args por
    checkout; (2) uma conexao que nunca volta ao pool dispensa restaurar o
    ``autocommit`` no shutdown (a antiga devolucao "contaminada" quebrava
    SAVEPOINTs de quem reusasse a conexao). ``create_connect_args`` deriva
    credenciais/host/query da MESMA URL do engine — nada de config paralela.
    """
    cargs, cparams = engine.dialect.create_connect_args(engine.url)
    cparams.update(_KEEPALIVES_LISTEN)
    conexao = engine.dialect.loaded_dbapi.connect(*cargs, **cparams)
    conexao.autocommit = True
    cursor = conexao.cursor()
    try:
        cursor.execute(f"LISTEN {CANAL_NOTIFY}")
    finally:
        cursor.close()
    return conexao


def _fechar_listen(conexao: Any) -> None:  # noqa: ANN401 — conexao DBAPI (psycopg2) crua
    """Fecha a conexao de LISTEN best-effort (pode ja estar morta/fechada)."""
    # Best-effort: conexao ja fechada/quebrada no shutdown ou na reconexao.
    with contextlib.suppress(Exception):
        conexao.close()


def _reconectar_listen(
    engine: Engine,
    *,
    parar: Callable[[], bool],
    dormir: Callable[[float], None] = time.sleep,
) -> Any | None:  # noqa: ANN401 — conexao DBAPI (psycopg2) crua ou None
    """Reconstroi a conexao de LISTEN com backoff incremental (teto 30s).

    Insiste ate conseguir (um failover pode deixar o DB fora por minutos) ou
    ate ``parar()`` (SIGTERM durante a reconexao encerra sem esperar o DB
    voltar — retorna ``None``). Entre tentativas dorme com atraso dobrado ate
    ``_RECONEXAO_TETO_S`` e toca o heartbeat: DB fora NAO deve estourar a
    livenessProbe (reiniciar o pod nao conserta o DB); o teto de 30s mantem o
    intervalo entre touches abaixo da janela de 60s da probe.
    """
    atraso = _RECONEXAO_BASE_S
    while not parar():
        try:
            conexao = _conectar_listen(engine)
        except Exception:  # noqa: BLE001 — DB fora e transitorio: loga, dorme e re-tenta
            _log.warning(
                "listen_reconexao_falhou",
                proxima_tentativa_s=atraso,
                exc_info=True,
            )
            _heartbeat()
            dormir(atraso)
            atraso = min(atraso * 2, _RECONEXAO_TETO_S)
        else:
            _log.info("listen_reconectado", canal=CANAL_NOTIFY)
            return conexao
    return None


def _drenar(
    engine: Engine,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
    lote: int,
    lease: timedelta,
    relogio: Callable[[], datetime],
    heartbeat: Callable[[], None],
    parar: Callable[[], bool],
) -> int:
    """Processa ciclos ate esvaziar as linhas elegiveis; retorna o total.

    Toca o ``heartbeat`` antes de CADA ``processar_ciclo`` (#163): uma fila
    profunda encadeia lotes cheios por minutos e um heartbeat apenas por
    acorde estouraria a janela de 60s da livenessProbe com o relay saudavel
    (starvation). ``parar`` e checado no topo de cada ciclo: apos SIGTERM o
    relay NAO reivindica lote novo — encerra dentro do grace period; a linha
    em voo termina sua tx normalmente (at-least-once cobre o resto).
    """
    total = 0
    while not parar():
        heartbeat()
        processadas = processar_ciclo(
            engine,
            handlers=handlers,
            nome_handler=nome_handler,
            limite=lote,
            lease=lease,
            relogio=relogio,
        )
        if not processadas:
            break
        total += processadas
    return total


def executar_relay(
    engine: Engine,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
    relogio: Callable[[], datetime],
    parar: Callable[[], bool] = lambda: False,
) -> None:
    """Loop infinito: LISTEN + poll, drenando a outbox a cada acorde.

    ``parar`` permite encerrar o loop (sinal em producao, teste em suite) e e
    observado tambem DENTRO do drain (entre ciclos) e da reconexao de LISTEN.
    A conexao de LISTEN e dedicada (psycopg2 com keepalives TCP) e, se cair, e
    reconstruida com backoff sem derrubar o processo (#165). O heartbeat da
    liveness e tocado a cada ciclo de drain (#163). O gauge
    ``outbox_profundidade`` e logado quando um drain processa >= 1 linha OU a
    cada ``_ACORDES_POR_LOG`` acordes ociosos (throttle do log; o gauge OTel
    continua continuo, por scrape).
    """
    poll, lote, lease = _config_do_ambiente()
    conexao = _conectar_listen(engine)
    # Classes de erro do proprio driver (psycopg2), sem importa-lo direto: o
    # DBAPI ja esta carregado no dialect do engine.
    dbapi = engine.dialect.loaded_dbapi
    try:
        _log.info(
            "relay iniciado",
            canal=CANAL_NOTIFY,
            poll_segundos=poll,
            lote=lote,
            lease_segundos=lease.total_seconds(),
        )
        # Acordes ociosos desde o ultimo log de profundidade (throttle).
        acordes_sem_gauge = 0
        # Drena o que ja estava pendente antes do primeiro NOTIFY — dentro do
        # MESMO guarda-chuva de resiliencia do drain in-loop: um blip de DB no
        # boot nao derruba o relay; o proximo acorde re-drena.
        try:
            _drenar(
                engine,
                handlers=handlers,
                nome_handler=nome_handler,
                lote=lote,
                lease=lease,
                relogio=relogio,
                heartbeat=_heartbeat,
                parar=parar,
            )
            emitir_profundidade(engine)  # baseline de profundidade no boot
        except Exception:  # noqa: BLE001 — blip transitorio vira log+continue, nao restart
            _log.error("outbox_ciclo_falhou", exc_info=True)
        while not parar():
            # Resiliencia da conexao de LISTEN (#165): um socket morto
            # (failover do Postgres, NAT/LB que dropou a conexao ociosa —
            # denunciado pelos keepalives) levanta OperationalError/OSError no
            # select/poll. Fecha a conexao velha e reconstroi com backoff, sem
            # derrubar o processo; o drain via pool segue no mesmo acorde.
            try:
                pronto = select.select([conexao], [], [], poll)
                if pronto != ([], [], []):
                    conexao.poll()
                    # Consome as notificacoes acumuladas (coalesce): um unico
                    # drain cobre todas.
                    conexao.notifies.clear()
            except (dbapi.Error, OSError):
                _log.warning("listen_conexao_perdida", exc_info=True)
                _fechar_listen(conexao)
                substituta = _reconectar_listen(engine, parar=parar)
                if substituta is None:
                    break  # sinal chegou durante a reconexao: encerra sem DB
                conexao = substituta
            # Resiliencia por ciclo (F6/operacao): um erro transitorio de DB
            # (failover, hiccup do pool) durante heartbeat/drain NAO derruba o
            # processo — derrubar reinicia o pod e desmonta o socket de LISTEN
            # a cada blip (restart-storm). At-least-once + lease garantem que
            # nada se perde: loga e CONTINUA; o proximo poll/NOTIFY re-drena.
            # KeyboardInterrupt/SystemExit (BaseException) seguem propagando.
            # Uma falha do gauge (emitir_profundidade) cai de proposito aqui
            # tambem: e a MESMA classe de blip transitorio de DB e o exc_info
            # distingue a causa no log. O heartbeat por ciclo vive dentro de
            # `_drenar` (#163): prova que o loop esta vivo E progredindo.
            try:
                processadas = _drenar(
                    engine,
                    handlers=handlers,
                    nome_handler=nome_handler,
                    lote=lote,
                    lease=lease,
                    relogio=relogio,
                    heartbeat=_heartbeat,
                    parar=parar,
                )
                acordes_sem_gauge += 1
                if processadas or acordes_sem_gauge >= _ACORDES_POR_LOG:
                    emitir_profundidade(engine)
                    acordes_sem_gauge = 0
            except Exception:  # noqa: BLE001 — blip transitorio vira log+continue, nao restart
                _log.error("outbox_ciclo_falhou", exc_info=True)
                continue
    finally:
        # Conexao dedicada: basta fechar (nao volta a pool nenhum, nada de
        # autocommit a restaurar).
        _fechar_listen(conexao)
