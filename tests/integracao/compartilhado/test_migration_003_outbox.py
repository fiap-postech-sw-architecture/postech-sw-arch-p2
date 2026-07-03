"""Migration 003 (outbox) ida-e-volta contra Postgres efemero (RF-018).

``alembic upgrade head`` cria ``outbox`` + ``processed_events``;
``downgrade`` para 002 as remove. Roda via ``alembic.command`` programatico
contra um Postgres dedicado (testcontainer proprio) — NAO o ``engine`` da
sessao, cujo ``metadata.create_all`` ja teria criado as tabelas e colidiria
com o ``upgrade``. ``env.py`` le a URL de ``DATABASE_URL`` (``get_url``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, inspect

if TYPE_CHECKING:
    from collections.abc import Generator

    from alembic.config import Config

pytestmark = [pytest.mark.integracao, pytest.mark.lento]

# Raiz do repo (este arquivo: tests/integracao/compartilhado/) — necessario
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
    """Sobe um Postgres DEDICADO e exporta DATABASE_URL para o env.py do alembic.

    Sempre um container proprio (nunca o banco compartilhado): este teste faz
    ``downgrade base``, que apagaria as tabelas que o ``engine`` da sessao cria
    via ``create_all`` se rodasse no mesmo banco — exatamente o tipo de
    contaminacao que evitamos isolando o estado. ``monkeypatch.setenv``
    restaura o ambiente no teardown (depois do container encerrar).
    """
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16") as postgres:
        url = postgres.get_connection_url()
        monkeypatch.setenv("DATABASE_URL", url)
        yield url


def _tabelas(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_cria_e_downgrade_remove_tabelas_da_outbox(postgres_url: str) -> None:
    from alembic import command

    cfg = _config(postgres_url)

    # Garante estado limpo (caso o banco seja reusado): volta tudo a base.
    command.downgrade(cfg, "base")
    assert not ({"outbox", "processed_events"} & _tabelas(postgres_url))

    # upgrade head: a cadeia 001->002->003 cria as tabelas da outbox.
    command.upgrade(cfg, "head")
    tabelas_apos_upgrade = _tabelas(postgres_url)
    assert "outbox" in tabelas_apos_upgrade
    assert "processed_events" in tabelas_apos_upgrade

    # downgrade para 002: SO as tabelas da 003 saem (002 e anteriores ficam).
    command.downgrade(cfg, "002")
    tabelas_apos_downgrade = _tabelas(postgres_url)
    assert "outbox" not in tabelas_apos_downgrade
    assert "processed_events" not in tabelas_apos_downgrade

    # Limpa o ambiente do banco efemero/reusado para nao afetar outros testes.
    command.downgrade(cfg, "base")
