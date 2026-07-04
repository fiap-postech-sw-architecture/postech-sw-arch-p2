"""Migration 007 (escopo_aprovado_json em ordens_de_servico) ida-e-volta (#111).

``alembic upgrade head`` percorre a cadeia 001->...->007; apos o 007 a coluna
``ordens_de_servico.escopo_aprovado_json`` existe como ``jsonb`` e e nullable.
``downgrade`` para 006 a remove. Roda via ``alembic.command`` programatico contra
um Postgres DEDICADO (testcontainer proprio) — NAO o ``engine`` da sessao, cujo
``metadata.create_all`` ja teria criado a tabela e colidiria com o ``upgrade``.
``env.py`` le a URL de ``DATABASE_URL`` (``get_url``). Espelha o 004.
"""

from __future__ import annotations

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
    # Nao deixar o env.py rodar fileConfig: reconfiguraria o logging global
    # do processo pytest e quebraria asserts de log de testes vizinhos.
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture
def postgres_url(monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    """Sobe um Postgres DEDICADO e exporta DATABASE_URL para o env.py do alembic."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as postgres:
        url = postgres.get_connection_url()
        monkeypatch.setenv("DATABASE_URL", url)
        yield url


def _tipo_coluna(url: str) -> str | None:
    """``data_type`` de ``ordens_de_servico.escopo_aprovado_json`` ou ``None``."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'ordens_de_servico' "
                    "AND column_name = 'escopo_aprovado_json'"
                )
            ).first()
            return None if row is None else (row.data_type, row.is_nullable)
    finally:
        engine.dispose()


def test_upgrade_adiciona_coluna_jsonb_e_downgrade_remove(postgres_url: str) -> None:
    from alembic import command

    cfg = _config(postgres_url)
    command.downgrade(cfg, "base")  # estado limpo (caso o banco seja reusado)

    # upgrade head: a cadeia chega ao 007 e a coluna jsonb NULLABLE passa a existir.
    command.upgrade(cfg, "head")
    assert _tipo_coluna(postgres_url) == ("jsonb", "YES")

    # downgrade para 006: so o 007 e revertido -> a coluna some.
    command.downgrade(cfg, "006")
    assert _tipo_coluna(postgres_url) is None

    command.downgrade(cfg, "base")  # limpa o ambiente do banco efemero/reusado
