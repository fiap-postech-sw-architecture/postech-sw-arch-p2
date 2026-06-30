"""Migration 006 (widen veiculos.placa 7->64) ida-e-volta (#72).

``alembic upgrade head`` alarga ``veiculos.placa`` para VARCHAR(64) (cabe o
tombstone LGPD ``ANONIMIZADO:{veiculo_id}``); ``downgrade`` para 005 reverte para
VARCHAR(7). Roda via ``alembic.command`` contra um Postgres DEDICADO.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, text

if TYPE_CHECKING:
    from collections.abc import Generator

    from alembic.config import Config

pytestmark = [pytest.mark.integracao, pytest.mark.lento]

_RAIZ = Path(__file__).resolve().parents[3]


def _config(database_url: str) -> Config:
    from alembic.config import Config

    cfg = Config(str(_RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(_RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture
def postgres_url() -> Generator[str]:
    from testcontainers.postgres import PostgresContainer

    anterior = os.environ.get("DATABASE_URL")
    with PostgresContainer("postgres:16") as postgres:
        url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = url
        try:
            yield url
        finally:
            if anterior is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = anterior


def _tamanho_placa(url: str) -> int:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT character_maximum_length "
                        "FROM information_schema.columns "
                        "WHERE table_name = 'veiculos' AND column_name = 'placa'"
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


def test_upgrade_alarga_placa_e_downgrade_reverte(postgres_url: str) -> None:
    from alembic import command

    cfg = _config(postgres_url)
    command.downgrade(cfg, "base")

    command.upgrade(cfg, "head")
    assert _tamanho_placa(postgres_url) == 64

    command.downgrade(cfg, "005")
    assert _tamanho_placa(postgres_url) == 7

    command.downgrade(cfg, "base")
