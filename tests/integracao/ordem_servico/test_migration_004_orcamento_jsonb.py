"""Migration 004 (orcamento_json Text -> jsonb) ida-e-volta (TD-005).

``alembic upgrade head`` percorre a cadeia 001->...->004; apos o 004 a coluna
``ordens_de_servico.orcamento_json`` e ``jsonb``. ``downgrade`` para 003 a
reverte para ``text``. Roda via ``alembic.command`` programatico contra um
Postgres DEDICADO (testcontainer proprio) — NAO o ``engine`` da sessao, cujo
``metadata.create_all`` ja teria criado a tabela e colidiria com o ``upgrade``.
``env.py`` le a URL de ``DATABASE_URL`` (``get_url``).
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

# Raiz do repo (este arquivo: tests/integracao/ordem_servico/) — necessario
# para o alembic localizar ``migrations/`` independente do cwd do pytest.
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


def _tipo_coluna(url: str) -> str:
    """Tipo de dado de ``ordens_de_servico.orcamento_json`` via information_schema."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = 'ordens_de_servico' "
                    "AND column_name = 'orcamento_json'"
                )
            ).scalar_one()
    finally:
        engine.dispose()


def test_upgrade_converte_para_jsonb_e_downgrade_volta_para_text(
    postgres_url: str,
) -> None:
    from alembic import command

    cfg = _config(postgres_url)

    # Estado limpo (caso o banco seja reusado).
    command.downgrade(cfg, "base")

    # upgrade head: a cadeia chega ao 004 e a coluna vira jsonb.
    command.upgrade(cfg, "head")
    assert _tipo_coluna(postgres_url) == "jsonb"

    # downgrade para 003: a coluna volta a text (so o 004 e revertido).
    command.downgrade(cfg, "003")
    assert _tipo_coluna(postgres_url) == "text"

    # Limpa o ambiente do banco efemero/reusado para nao afetar outros testes.
    command.downgrade(cfg, "base")
