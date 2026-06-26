"""Ciclo claim-then-deliver da outbox com lease (RF-018).

Estrategia (F3 — evita reverter entregas ja feitas, soltar lock/conexao no
SMTP e duplicar ate o lote inteiro num crash):

1. CLAIM (tx curta): ``reivindicar_lote`` reivindica linhas ``pendente``
   elegiveis ordenadas por ``id`` com ``FOR UPDATE SKIP LOCKED`` e, na MESMA
   tx, estende ``proxima_tentativa_em`` por um LEASE (visibility timeout >
   timeout do SMTP). Comita -> o lock e liberado imediatamente. O lease
   atrasa a re-elegibilidade: se o processo cair durante a entrega, a linha
   volta a ser elegivel so apos o lease vencer (at-least-once, sem status
   novo e sem reaper).
2. HEAD-OF-LINE por agregado (F2): a query de claim exclui linha cujo
   agregado tenha uma predecessora (``id`` menor) NAO-terminal — ou seja,
   um evento em backoff segura os sucessores do MESMO agregado. ``dead`` NAO
   bloqueia (gap aceito; ver F4).
3. DELIVER (fora de transacao): ``processar_linha`` entrega UMA linha por
   vez, em ordem de ``id``, cada uma com idempotencia (``processed_events``)
   -> handler -> ``entregue`` / retry / ``dead``, gravada numa TX CURTA
   PROPRIA POR LINHA. Assim um erro de DB numa linha tardia nunca reverte o
   ``entregue`` de uma linha anterior, e um crash duplica no MAXIMO 1 e-mail
   (a linha em voo), nao o lote.

A logica de transicao (``processar_linha``) e desacoplada do banco por uma
fachada (``ConexaoOutbox``) para teste unitario sem Postgres; a
implementacao real (``ConexaoOutboxSQL``) fala SQLAlchemy Core e e
construida com uma conexao por linha em ``processar_ciclo``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from sqlalchemy import text

from relay.backoff import calcular_proxima_tentativa, deve_ir_para_dlq
from src.compartilhado.infraestrutura.logging import redigir_pii_erro

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime, timedelta
    from uuid import UUID

    from sqlalchemy import Connection, Engine

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LinhaOutbox:
    """Snapshot de uma linha reivindicada da outbox."""

    id: int
    agregado_id: UUID
    tipo: str
    payload: dict[str, Any]
    tentativas: int


class ConexaoOutbox(Protocol):
    """Fachada dos efeitos sobre a outbox (permite fake em teste)."""

    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def ja_processado(self, outbox_id: int, handler: str) -> bool:
        pass

    def marcar_entregue(self, outbox_id: int) -> None:
        pass

    def registrar_processed(self, outbox_id: int, handler: str) -> None:
        pass

    def agendar_retry(self, outbox_id: int, tentativas: int, erro: str) -> None:
        pass

    def marcar_dead(self, outbox_id: int, tentativas: int, erro: str) -> None:
        pass

    def tem_sucessor_pendente(self, agregado_id: UUID, outbox_id: int) -> bool:
        pass


def processar_linha(
    conn: ConexaoOutbox,
    linha: LinhaOutbox,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
) -> None:
    """Processa uma linha: idempotencia -> handler -> entregue/retry/dead.

    Sem handler registrado para o ``tipo`` a linha vai direto para a DLQ
    (config invalida: evento na outbox sem consumidor) preservando
    ``tentativas`` (nao houve tentativa de entrega). Falha de handler
    incrementa ``tentativas``; ao atingir o maximo, ``dead``. ``marcar_dead``
    recebe o valor EXPLICITO de ``tentativas`` (F5) — fonte unica de
    verdade, identica a ``agendar_retry``.
    """
    handler = handlers.get(linha.tipo)
    if handler is None:
        _log.error(
            "outbox: tipo sem handler registrado; movendo para DLQ",
            outbox_id=linha.id,
            tipo=linha.tipo,
        )
        conn.marcar_dead(
            linha.id, linha.tentativas, f"sem handler para tipo {linha.tipo}"
        )
        _alertar_dead_com_sucessores(conn, linha)
        return

    if conn.ja_processado(linha.id, nome_handler):
        # Efeito ja aplicado num ciclo anterior (crash apos handler, antes
        # de marcar entregue): nao reinvoca, apenas finaliza a linha.
        conn.marcar_entregue(linha.id)
        _log.info(
            "outbox: linha ja processada (idempotente); marcada entregue",
            outbox_id=linha.id,
            handler=nome_handler,
        )
        return

    try:
        handler(linha.payload)
    except Exception as exc:  # noqa: BLE001 — falha de handler vira retry/DLQ, nunca derruba o relay
        tentativas = linha.tentativas + 1
        erro = redigir_pii_erro(f"{type(exc).__name__}: {exc}")
        if deve_ir_para_dlq(tentativas):
            conn.marcar_dead(linha.id, tentativas, erro)
            _log.error(
                "outbox: entrega falhou no maximo de tentativas; DLQ",
                outbox_id=linha.id,
                tipo=linha.tipo,
                tentativas=tentativas,
            )
            _alertar_dead_com_sucessores(conn, linha)
        else:
            conn.agendar_retry(linha.id, tentativas, erro)
            _log.warning(
                "outbox: entrega falhou; reagendada com backoff",
                outbox_id=linha.id,
                tipo=linha.tipo,
                tentativas=tentativas,
            )
        return

    conn.registrar_processed(linha.id, nome_handler)
    conn.marcar_entregue(linha.id)
    _log.info(
        "outbox: evento entregue",
        outbox_id=linha.id,
        tipo=linha.tipo,
        handler=nome_handler,
    )


def _alertar_dead_com_sucessores(conn: ConexaoOutbox, linha: LinhaOutbox) -> None:
    """Loga ``error`` se a linha promovida a ``dead`` deixa sucessores pendentes.

    Politica do gap (F4): ``dead`` NAO bloqueia os sucessores do mesmo
    agregado (a notificacao e advisory, RF-024), mas a ordenacao por
    agregado fica com um buraco. Sinaliza-se com log ``error`` para a banca
    investigar — e o ``listar_dead`` (Task 12) marca a linha como tendo
    sucessores pendentes.
    """
    if conn.tem_sucessor_pendente(linha.agregado_id, linha.id):
        _log.error(
            "outbox_dead_com_sucessores_pendentes",
            agregado_id=str(linha.agregado_id),
            outbox_id=linha.id,
        )


class ConexaoOutboxSQL:
    """Implementacao SQLAlchemy Core de ``ConexaoOutbox`` (Postgres)."""

    def __init__(self, conn: Connection, agora: datetime) -> None:
        self._conn = conn
        self._agora = agora

    def ja_processado(self, outbox_id: int, handler: str) -> bool:
        linha = self._conn.execute(
            text(
                "SELECT 1 FROM processed_events WHERE outbox_id = :id AND handler = :h"
            ),
            {"id": outbox_id, "h": handler},
        ).first()
        return linha is not None

    def marcar_entregue(self, outbox_id: int) -> None:
        self._conn.execute(
            text(
                "UPDATE outbox SET status='entregue', entregue_em=:agora WHERE id = :id"
            ),
            {"id": outbox_id, "agora": self._agora},
        )

    def registrar_processed(self, outbox_id: int, handler: str) -> None:
        self._conn.execute(
            text(
                "INSERT INTO processed_events (outbox_id, handler, processado_em) "
                "VALUES (:id, :h, :agora) ON CONFLICT DO NOTHING"
            ),
            {"id": outbox_id, "h": handler, "agora": self._agora},
        )

    def agendar_retry(self, outbox_id: int, tentativas: int, erro: str) -> None:
        self._conn.execute(
            text(
                "UPDATE outbox SET tentativas=:t, proxima_tentativa_em=:prox, "
                "ultimo_erro=:erro WHERE id = :id"
            ),
            {
                "id": outbox_id,
                "t": tentativas,
                "prox": calcular_proxima_tentativa(tentativas, self._agora),
                "erro": erro,
            },
        )

    def marcar_dead(self, outbox_id: int, tentativas: int, erro: str) -> None:
        # Grava o valor EXPLICITO de tentativas (F5), igual a agendar_retry —
        # NAO `tentativas+1` (o caller ja computou o valor final). entregue_em
        # zerado: linha morta nunca foi entregue.
        self._conn.execute(
            text(
                "UPDATE outbox SET status='dead', tentativas=:t, "
                "ultimo_erro=:erro, entregue_em=NULL WHERE id = :id"
            ),
            {"id": outbox_id, "t": tentativas, "erro": erro},
        )

    def tem_sucessor_pendente(self, agregado_id: UUID, outbox_id: int) -> bool:
        # Existe linha posterior (id maior) do mesmo agregado ainda
        # `pendente`? Usado para alertar sobre gap no DLQ (F4).
        linha = self._conn.execute(
            text(
                "SELECT 1 FROM outbox WHERE agregado_id = :aid "
                "AND id > :id AND status = 'pendente' LIMIT 1"
            ),
            {"aid": agregado_id, "id": outbox_id},
        ).first()
        return linha is not None


def reivindicar_lote(
    conn: Connection, agora: datetime, limite: int, lease: timedelta
) -> list[LinhaOutbox]:
    """Reivindica ate ``limite`` linhas elegiveis (id-ordered) e aplica o lease.

    Numa unica tx (a do caller, ``processar_ciclo`` -> ``engine.begin()``):

    - SELECT com ``FOR UPDATE SKIP LOCKED``: linhas ``pendente`` com
      ``proxima_tentativa_em <= now()`` cujo agregado NAO tenha predecessora
      (``id`` menor) NAO-terminal (head-of-line por agregado, F2 — ``dead``
      nao bloqueia). Linhas travadas por outra instancia sao puladas.
    - UPDATE ``proxima_tentativa_em = now() + lease`` nas linhas
      reivindicadas (visibility timeout, F3): adia a re-elegibilidade
      enquanto a entrega ocorre fora de transacao; em crash, voltam a ser
      elegiveis so apos o lease vencer.

    O commit desta tx (no caller) libera os locks ANTES de qualquer I/O de
    rede (SMTP). Os campos retornados refletem o estado pre-lease
    (``tentativas`` etc.) para o ``processar_linha``.
    """
    # Alias `o` para a outbox; subquery `p` exclui linha com predecessora
    # NAO-terminal do mesmo agregado (head-of-line por agregado, F2).
    # `dead` e `entregue` sao terminais e NAO bloqueiam.
    linhas = conn.execute(
        text(
            "SELECT o.id, o.agregado_id, o.tipo, o.payload, o.tentativas "
            "FROM outbox o "
            "WHERE o.status = 'pendente' AND o.proxima_tentativa_em <= :agora "
            "AND NOT EXISTS ( "
            "  SELECT 1 FROM outbox p "
            "  WHERE p.agregado_id = o.agregado_id "
            "    AND p.id < o.id "
            "    AND p.status NOT IN ('entregue','dead') "
            ") "
            "ORDER BY o.id FOR UPDATE OF o SKIP LOCKED LIMIT :limite"
        ),
        {"agora": agora, "limite": limite},
    ).all()
    reivindicadas = [
        LinhaOutbox(
            id=row.id,
            agregado_id=row.agregado_id,
            tipo=row.tipo,
            payload=row.payload,
            tentativas=row.tentativas,
        )
        for row in linhas
    ]
    if reivindicadas:
        # Estende o lease (visibility timeout) das linhas reivindicadas (F3).
        conn.execute(
            text("UPDATE outbox SET proxima_tentativa_em = :ate WHERE id = ANY(:ids)"),
            {"ate": agora + lease, "ids": [linha.id for linha in reivindicadas]},
        )
    return reivindicadas


def emitir_profundidade(engine: Engine) -> None:
    """Loga um gauge ``info`` da profundidade da outbox (design §7).

    Uma unica query por chamada (barata; os indices de ``status`` ja existem):
    quantos eventos ``pendente``, ha quanto tempo o mais antigo espera
    (segundos) e quantos estao em ``dead`` (DLQ). Emitido uma vez por ciclo de
    drain (em ``_drenar``), nao por entrega — observabilidade de fila sem
    inflar o volume de logs por evento.

    ``idade_mais_antigo_s`` e ``None`` quando nao ha pendentes (o
    ``min(... ) FILTER`` retorna NULL); o caller registra como tal.
    """
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE status = 'pendente') AS pendentes, "
                "EXTRACT(EPOCH FROM (now() - min(criado_em) "
                "  FILTER (WHERE status = 'pendente'))) AS idade_mais_antigo_s, "
                "count(*) FILTER (WHERE status = 'dead') AS dead "
                "FROM outbox"
            )
        ).one()
    idade = row.idade_mais_antigo_s
    _log.info(
        "outbox_profundidade",
        pendentes=int(row.pendentes),
        idade_mais_antigo_s=float(idade) if idade is not None else None,
        dead=int(row.dead),
    )


def processar_ciclo(
    engine: Engine,
    *,
    handlers: Mapping[str, Callable[[dict[str, Any]], None]],
    nome_handler: str,
    limite: int,
    lease: timedelta,
    relogio: Callable[[], datetime],
) -> int:
    """Claim-then-deliver de um ciclo. Retorna #linhas reivindicadas.

    1. CLAIM (tx curta): reivindica + aplica lease; o commit libera o lock
       ANTES da entrega.
    2. DELIVER: entrega cada linha em ordem de id, FORA da tx de claim, cada
       uma na PROPRIA tx curta (``engine.begin()`` por linha). Erro de DB
       numa linha nao reverte o ``entregue`` das anteriores; crash duplica no
       maximo a linha em voo (F3).

    INVARIANTE DO LEASE (HA / N replicas): o lease (visibility timeout
    aplicado em ``reivindicar_lote``) precisa exceder a latencia de pior caso
    de UMA chamada de handler — limitada pelo timeout do SMTP do adapter. O
    drain e SEQUENCIAL e em ``replicas:1`` so existe um worker, entao a linha
    em voo nunca volta a ser elegivel durante a entrega: seguro. Escalar para
    ``replicas>1`` exige que essa invariante se mantenha (ou uma checagem de
    fencing no momento da entrega); se o lease vencer no meio de uma entrega
    lenta, uma segunda replica re-reivindica a MESMA linha e o e-mail
    duplica. A configuracao shipada e ``replicas:1`` deliberadamente.
    """
    agora = relogio()
    with engine.begin() as conn:
        linhas = reivindicar_lote(conn, agora, limite, lease)
    for linha in linhas:
        with engine.begin() as conn:
            fachada = ConexaoOutboxSQL(conn, agora)
            processar_linha(
                fachada,
                linha,
                handlers=handlers,
                nome_handler=nome_handler,
            )
    if linhas:
        _log.info("outbox: ciclo processado", linhas=len(linhas))
    return len(linhas)
