from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao


def test_tabelas_outbox_existem(engine: Engine) -> None:
    nomes = set(inspect(engine).get_table_names())
    assert "outbox" in nomes
    assert "processed_events" in nomes


def test_outbox_tem_colunas_esperadas(engine: Engine) -> None:
    colunas = {c["name"] for c in inspect(engine).get_columns("outbox")}
    assert colunas == {
        "id",
        "agregado_id",
        "tipo",
        "payload",
        "status",
        "tentativas",
        "proxima_tentativa_em",
        "criado_em",
        "entregue_em",
        "ultimo_erro",
    }
