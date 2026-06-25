"""Smoke test: LISTEN/NOTIFY raw-connection path (RF-018).

Valida empiricamente que ``raw.driver_connection`` expoe ``.poll()`` e
``.notifies`` (psycopg2) e que ``executar_relay`` drena uma linha da outbox
ao acordar por NOTIFY. Este e o teste critico documentado como arriscado no
plano da Task 10 — o resultado (qual accessor funcionou) e reportado no log.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao


def test_driver_connection_expoe_notifies_e_poll(engine: Engine) -> None:
    """Confirma que raw.driver_connection e o psycopg2 connection real."""
    raw = engine.raw_connection()
    try:
        raw.autocommit = True  # type: ignore[attr-defined]
        dbapi_conn = raw.driver_connection
        assert dbapi_conn is not None, (
            "raw.driver_connection retornou None — "
            "psycopg2 nao conectado ou accessor errado"
        )
        # psycopg2 connection tem .notifies e .poll()
        assert hasattr(dbapi_conn, "notifies"), (
            "driver_connection nao tem .notifies — "
            "accessor errado (tentar raw.connection?)"
        )
        assert hasattr(dbapi_conn, "poll"), (
            "driver_connection nao tem .poll — accessor errado (tentar raw.connection?)"
        )
    finally:
        raw.close()


def test_executar_relay_drena_linha_pendente(engine: Engine) -> None:
    """Smoke test end-to-end: insere linha, chama executar_relay, confirma entregue."""
    from relay.listener import executar_relay

    agregado_id = uuid.uuid4()
    payload = {"agregado_id": str(agregado_id), "tipo_evento": "smoke"}

    # Insere uma linha pendente diretamente na outbox.
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO outbox
                    (agregado_id, tipo, payload, status, tentativas,
                     proxima_tentativa_em, criado_em)
                VALUES
                    (:agg_id, 'SmokeTipoEvento', :payload, 'pendente', 0,
                     :agora, :agora)
                RETURNING id
                """
            ),
            {
                "agg_id": agregado_id,
                "payload": json.dumps(payload),
                "agora": datetime.now(UTC),
            },
        ).fetchone()
    assert row is not None
    outbox_id = row[0]

    # Handler fake: captura o payload e marca entregue.
    entregues: list[dict] = []

    def handler_smoke(p: dict) -> None:
        entregues.append(p)

    # parar=True na segunda chamada: drena uma vez e para.
    contagem = [0]

    def parar() -> bool:
        # Deixa o primeiro loop completar (a drenagem inicial antes do while),
        # depois para imediatamente na primeira iteracao do while.
        contagem[0] += 1
        return contagem[0] > 1

    executar_relay(
        engine,
        handlers={"SmokeTipoEvento": handler_smoke},
        nome_handler="smoke-handler",
        relogio=lambda: datetime.now(UTC),
        parar=parar,
    )

    # Confirma que a linha foi entregue.
    with engine.connect() as conn:
        status_row = conn.execute(
            text("SELECT status FROM outbox WHERE id = :id"),
            {"id": outbox_id},
        ).fetchone()

    assert status_row is not None
    assert status_row[0] == "entregue", (
        f"Esperado status='entregue', obtido='{status_row[0]}'"
    )
    assert len(entregues) == 1, f"Handler chamado {len(entregues)}x (esperado 1x)"
