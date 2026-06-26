"""Loop principal do relay: LISTEN outbox_novo + poll de seguranca (RF-018).

Abre uma conexao psycopg2 raw em autocommit para ``LISTEN outbox_novo`` e
fica em ``select`` aguardando notificacao OU timeout de poll
(``OUTBOX_POLL_SEGUNDOS``, default 5s). A cada acorde (NOTIFY ou timeout)
drena a fila chamando ``processar_ciclo`` (claim-then-deliver com lease)
repetidamente ate nao haver mais linhas elegiveis — o poll cobre eventos
perdidos (NOTIFY e best-effort se o relay estava fora no momento do COMMIT),
linhas reagendadas por backoff e linhas cujo lease venceu apos um crash de
entrega.

Heartbeat (F6): a cada ciclo do loop o relay faz ``touch`` no arquivo
``RELAY_HEARTBEAT`` (default ``/tmp/relay-heartbeat``); a ``livenessProbe``
do k8s falha se o heartbeat ficar velho — assim um SMTP travado (apesar do
timeout do adapter) ou um loop preso reinicia o pod, em vez de ``kill -0 1``
passar com o processo vivo porem inerte.

O processamento usa o ``engine`` SQLAlchemy (pool); a conexao de LISTEN e
dedicada e separada do pool de trabalho.
"""

from __future__ import annotations

import os
import select
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from relay.processador import emitir_profundidade, processar_ciclo
from src.compartilhado.infraestrutura.outbox_mapping import CANAL_NOTIFY

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
# folga; NAO baixar abaixo do timeout de entrega do adapter.
_LEASE_PADRAO = 60
# Caminho efemero do pod (sobrescrito por RELAY_HEARTBEAT); intencional.
_HEARTBEAT_PADRAO = "/tmp/relay-heartbeat"  # noqa: S108  # nosec B108


def _config_do_ambiente() -> tuple[float, int, timedelta]:
    """Le poll/lote/lease do ambiente com defaults seguros."""
    poll = float(os.environ.get("OUTBOX_POLL_SEGUNDOS", str(_POLL_PADRAO)))
    lote = int(os.environ.get("OUTBOX_LOTE", str(_LOTE_PADRAO)))
    lease = timedelta(
        seconds=int(os.environ.get("OUTBOX_LEASE_SEGUNDOS", str(_LEASE_PADRAO)))
    )
    return poll, lote, lease


def _heartbeat() -> None:
    """Atualiza o mtime do arquivo de heartbeat (liveness do F6)."""
    caminho = Path(os.environ.get("RELAY_HEARTBEAT", _HEARTBEAT_PADRAO))
    caminho.touch()


def _drenar(
    engine: Engine,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
    lote: int,
    lease: timedelta,
    relogio: Callable[[], datetime],
) -> None:
    """Processa ciclos ate esvaziar as linhas elegiveis e loga a profundidade.

    Apos drenar, emite o gauge ``outbox_profundidade`` (design §7): uma query
    por ciclo de drain (NAO por entrega) — pendentes, idade do mais antigo e
    tamanho da DLQ.
    """
    while processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler=nome_handler,
        limite=lote,
        lease=lease,
        relogio=relogio,
    ):
        continue
    emitir_profundidade(engine)


def executar_relay(
    engine: Engine,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
    relogio: Callable[[], datetime],
    parar: Callable[[], bool] = lambda: False,
) -> None:
    """Loop infinito: LISTEN + poll, drenando a outbox a cada acorde.

    ``parar`` permite encerrar o loop em teste (default nunca para). A
    conexao de LISTEN usa o DBAPI raw do proprio engine em autocommit. A
    cada ciclo (antes de drenar) atualiza o heartbeat para a liveness (F6).
    """
    poll, lote, lease = _config_do_ambiente()
    raw = engine.raw_connection()
    try:
        # psycopg2 nunca devolve None apos conexao bem-sucedida; guarda
        # explicita (em vez de assert, que `python -O` removeria) que tambem
        # estreita o tipo para o mypy.
        driver_conn = raw.driver_connection
        if driver_conn is None:  # pragma: no cover — psycopg2 conectado nunca e None
            msg = "raw_connection sem driver_connection (psycopg2 nao conectado)"
            raise RuntimeError(msg)
        # psycopg2 real conn; _ConnectionFairy nao propaga autocommit.
        driver_conn.autocommit = True
        cursor = raw.cursor()
        cursor.execute(f"LISTEN {CANAL_NOTIFY}")
        _log.info(
            "relay iniciado",
            canal=CANAL_NOTIFY,
            poll_segundos=poll,
            lote=lote,
            lease_segundos=lease.total_seconds(),
        )
        # Drena o que ja estava pendente antes do primeiro NOTIFY.
        _heartbeat()
        _drenar(
            engine,
            handlers=handlers,
            nome_handler=nome_handler,
            lote=lote,
            lease=lease,
            relogio=relogio,
        )
        # Reusa o driver_connection ja narrowed acima (mesmo objeto psycopg2).
        conexao_dbapi = driver_conn
        while not parar():
            pronto = select.select([conexao_dbapi], [], [], poll)
            if pronto != ([], [], []):
                conexao_dbapi.poll()
                # Consome as notificacoes acumuladas (coalesce).
                while conexao_dbapi.notifies:
                    conexao_dbapi.notifies.pop(0)
            # Resiliencia por ciclo (F6/operacao): um erro transitorio de DB
            # (failover, hiccup do pool) durante heartbeat/drain NAO derruba o
            # processo — derrubar reinicia o pod e desmonta o socket de LISTEN
            # a cada blip (restart-storm). At-least-once + lease garantem que
            # nada se perde: loga e CONTINUA; o proximo poll/NOTIFY re-drena.
            # KeyboardInterrupt/SystemExit (BaseException) seguem propagando.
            # Uma falha do gauge (emitir_profundidade, no fim de _drenar) cai
            # de proposito aqui tambem: e a MESMA classe de blip transitorio de
            # DB e o exc_info distingue a causa no log.
            try:
                # Heartbeat a cada acorde (NOTIFY ou timeout de poll): prova que
                # o loop esta vivo E progredindo, nao so que o processo existe.
                _heartbeat()
                _drenar(
                    engine,
                    handlers=handlers,
                    nome_handler=nome_handler,
                    lote=lote,
                    lease=lease,
                    relogio=relogio,
                )
            except Exception:  # noqa: BLE001 — blip transitorio vira log+continue, nao restart
                _log.error("outbox_ciclo_falhou", exc_info=True)
                continue
    finally:
        # Restaura autocommit=False antes de devolver ao pool; sem isso a
        # conexao retornaria "contaminada" (autocommit ligado) e quebraria
        # testes/codigo que usam SAVEPOINTs na mesma conexao reaproveitada.
        try:
            dc = raw.driver_connection
            if dc is not None:
                dc.autocommit = False
        # Best-effort: conexao ja fechada/invalida no shutdown, nada a tratar.
        except Exception:  # noqa: BLE001, S110  # nosec B110
            pass
        raw.close()
