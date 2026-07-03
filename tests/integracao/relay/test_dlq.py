from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from src.compartilhado.infraestrutura.outbox_dlq import listar_dead, reenfileirar
from tests.integracao.outbox_helpers import (
    inserir_dead as _inserir_dead,
)
from tests.integracao.outbox_helpers import (
    inserir_pendente,
)

pytestmark = pytest.mark.integracao


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
    dead_id = _inserir_dead(engine, agregado_id=agregado_id)
    inserir_pendente(engine, tipo="OrcamentoGeradoEvent", agregado_id=agregado_id)
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
