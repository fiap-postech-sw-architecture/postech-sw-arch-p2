"""Migration 005 (indice em itens_da_ordem.item_estoque_id) ida-e-volta (TD-025).

``alembic upgrade head`` percorre 001->...->005; apos o 005 existe o indice
``ix_itens_da_ordem_item_estoque_id``. ``downgrade`` para 004 o remove. Roda via
``alembic.command`` programatico contra um Postgres DEDICADO (testcontainer
proprio), NAO o ``engine`` da sessao. ``env.py`` le a URL de ``DATABASE_URL``.
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
_INDICE = "ix_itens_da_ordem_item_estoque_id"


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


def _indice_existe(url: str) -> bool:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                        "WHERE tablename = 'itens_da_ordem' AND indexname = :nome)"
                    ),
                    {"nome": _INDICE},
                ).scalar_one()
            )
    finally:
        engine.dispose()


def _indice_cobre_item_estoque_id(url: str) -> bool:
    """Confirma que o indice e sobre a coluna ``item_estoque_id`` (nao so o nome).

    Trava contra uma regressao onde a migration seja editada para indexar outra
    coluna mantendo o mesmo nome de indice.
    """
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                        "WHERE indexname = :nome "
                        "AND indexdef LIKE '%item_estoque_id%')"
                    ),
                    {"nome": _INDICE},
                ).scalar_one()
            )
    finally:
        engine.dispose()


def test_upgrade_cria_indice_e_downgrade_remove(postgres_url: str) -> None:
    from alembic import command

    cfg = _config(postgres_url)

    # Estado limpo (caso o banco seja reusado).
    command.downgrade(cfg, "base")

    # upgrade head: a cadeia chega ao 005 e o indice e criado sobre a coluna certa.
    command.upgrade(cfg, "head")
    assert _indice_existe(postgres_url) is True
    assert _indice_cobre_item_estoque_id(postgres_url) is True

    # downgrade para 004: so o 005 e revertido -> indice removido.
    command.downgrade(cfg, "004")
    assert _indice_existe(postgres_url) is False

    # Limpa o ambiente do banco efemero/reusado.
    command.downgrade(cfg, "base")
