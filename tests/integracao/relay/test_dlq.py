from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from relay.dlq import listar_dead, reenfileirar

pytestmark = pytest.mark.integracao


def _inserir_dead(engine, *, tentativas: int = 5) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox "
                "(agregado_id, tipo, payload, status, tentativas, "
                " proxima_tentativa_em, criado_em, ultimo_erro) "
                "VALUES (:aid, 'DiagnosticoIniciadoEvent', "
                " CAST(:payload AS JSONB), 'dead', :t, :agora, :agora, 'boom') "
                "RETURNING id"
            ),
            {
                "aid": uuid4(),
                "payload": '{"agregado_id": "x"}',
                "t": tentativas,
                "agora": datetime.now(UTC),
            },
        ).first()
        return int(row.id)


def test_listar_dead_retorna_linhas_mortas(engine) -> None:
    outbox_id = _inserir_dead(engine)
    mortos = listar_dead(engine)
    ids = {m["id"] for m in mortos}
    assert outbox_id in ids
    alvo = next(m for m in mortos if m["id"] == outbox_id)
    assert alvo["status"] == "dead"
    assert alvo["tipo"] == "DiagnosticoIniciadoEvent"
    # sem sucessor pendente do mesmo agregado (agregado_id unico por insercao)
    assert alvo["tem_sucessores_pendentes"] is False


def test_listar_dead_sinaliza_sucessor_pendente(engine) -> None:
    # dead (id menor) + pendente (id maior) do MESMO agregado -> gap (F4).
    agregado_id = uuid4()
    agora = datetime.now(UTC)
    with engine.begin() as conn:
        dead_id = conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em, ultimo_erro) "
                "VALUES (:aid, 'DiagnosticoIniciadoEvent', CAST(:p AS JSONB), "
                "'dead', 5, :agora, :agora, 'boom') RETURNING id"
            ),
            {"aid": agregado_id, "p": '{"agregado_id": "x"}', "agora": agora},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em) "
                "VALUES (:aid, 'OrcamentoGeradoEvent', CAST(:p AS JSONB), "
                "'pendente', 0, :agora, :agora)"
            ),
            {"aid": agregado_id, "p": '{"agregado_id": "x"}', "agora": agora},
        )
    alvo = next(m for m in listar_dead(engine) if m["id"] == dead_id)
    assert alvo["tem_sucessores_pendentes"] is True


def test_reenfileirar_volta_para_pendente_e_zera_tentativas(engine) -> None:
    outbox_id = _inserir_dead(engine)
    assert reenfileirar(engine, outbox_id) is True
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT status, tentativas FROM outbox WHERE id = :id"),
            {"id": outbox_id},
        ).first()
    assert row.status == "pendente"
    assert row.tentativas == 0


def test_reenfileirar_id_inexistente_retorna_false(engine) -> None:
    assert reenfileirar(engine, 99999999) is False
