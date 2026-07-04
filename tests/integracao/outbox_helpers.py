"""Helpers SQL compartilhados da outbox para os testes de integracao.

Antes copiados em ``test_admin_outbox.py``, ``relay/test_relay_fluxo.py``,
``relay/test_dlq.py`` e ``relay/test_relay_smtp_falha.py`` (issue #173).
Inserem/consultam linhas via Core (isolam os testes da UoW; a UoW e coberta
em ``compartilhado/test_outbox_uow.py``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _agora() -> datetime:
    return datetime.now(UTC)


def inserir_pendente(
    engine: Engine,
    *,
    tipo: str = "DiagnosticoIniciadoEvent",
    proxima: datetime | None = None,
    agregado_id: UUID | None = None,
    marcador: str | None = None,
) -> int:
    """Insere uma linha ``pendente`` e retorna o ``id``.

    ``marcador`` (quando dado) vai no payload como ``marcador``, permitindo
    correlacionar a ordem observada pelo handler ao ``id`` esperado (F7) sem
    depender de ``ORDER BY id`` nos dois lados.
    """
    payload: dict[str, Any] = {"agregado_id": str(agregado_id or uuid4())}
    if marcador is not None:
        payload["marcador"] = marcador
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox "
                "(agregado_id, tipo, payload, status, tentativas, "
                " proxima_tentativa_em, criado_em) "
                "VALUES (:aid, :tipo, CAST(:payload AS JSONB), 'pendente', 0, "
                " :prox, :agora) RETURNING id"
            ),
            {
                "aid": agregado_id or uuid4(),
                "tipo": tipo,
                "payload": json.dumps(payload),
                "prox": proxima or _agora(),
                "agora": _agora(),
            },
        ).first()
        return int(row.id)


def inserir_pendente_com_id(
    engine: Engine,
    outbox_id: int,
    *,
    tipo: str = "DiagnosticoIniciadoEvent",
    marcador: str,
) -> None:
    """Insere uma linha ``pendente`` com ``id`` EXPLICITO (bigserial aceita).

    Permite atribuir ids fora da ordem de insercao para discriminar
    ``ORDER BY id`` de FIFO/heap (F7). O ``marcador`` (= o proprio id como
    string) vai no payload para correlacionar a ordem observada ao id.
    """
    payload = json.dumps({"agregado_id": str(uuid4()), "marcador": marcador})
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO outbox "
                "(id, agregado_id, tipo, payload, status, tentativas, "
                " proxima_tentativa_em, criado_em) "
                "VALUES (:id, :aid, :tipo, CAST(:payload AS JSONB), 'pendente', 0, "
                " :agora, :agora)"
            ),
            {
                "id": outbox_id,
                "aid": uuid4(),
                "tipo": tipo,
                "payload": payload,
                "agora": _agora(),
            },
        )


def inserir_dead(
    engine: Engine,
    *,
    agregado_id: UUID | None = None,
    tipo: str = "DiagnosticoIniciadoEvent",
    tentativas: int = 5,
) -> int:
    """Insere uma linha ``dead`` (DLQ) com ``ultimo_erro='boom'`` e retorna o id."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em, ultimo_erro) "
                "VALUES (:aid, :tipo, CAST(:p AS JSONB), 'dead', :t, :agora, "
                ":agora, 'boom') RETURNING id"
            ),
            {
                "aid": agregado_id or uuid4(),
                "tipo": tipo,
                "p": '{"agregado_id": "x"}',
                "t": tentativas,
                "agora": _agora(),
            },
        ).first()
    return int(row.id)


def status_tentativas(engine: Engine, outbox_id: int) -> tuple[str, int]:
    """Retorna ``(status, tentativas)`` da linha."""
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT status, tentativas FROM outbox WHERE id = :id"),
            {"id": outbox_id},
        ).first()
    return row.status, row.tentativas


def contar_processed(engine: Engine, outbox_id: int) -> int:
    """Quantos ``processed_events`` existem para a linha (idempotencia)."""
    with engine.begin() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM processed_events WHERE outbox_id = :id"),
                {"id": outbox_id},
            ).scalar()
        )


def antecipar(engine: Engine, outbox_id: int) -> None:
    """Puxa ``proxima_tentativa_em`` para o passado (re-elegibiliza no claim).

    Sobrescreve tanto o backoff quanto o lease aplicado no claim — em
    producao o tempo passa; nos testes aceleramos.
    """
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE outbox SET proxima_tentativa_em = :p WHERE id = :id"),
            {"id": outbox_id, "p": _agora() - timedelta(seconds=1)},
        )


def limpar_outbox(engine: Engine) -> None:
    """Zera ``processed_events`` + ``outbox`` (ordem respeita a FK)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM processed_events"))
        conn.execute(text("DELETE FROM outbox"))
