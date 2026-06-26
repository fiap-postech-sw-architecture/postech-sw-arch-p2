from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

_mapeamentos_registrados = False


def _registrar_todos_mapeamentos() -> None:
    global _mapeamentos_registrados
    if _mapeamentos_registrados:
        return
    _mapeamentos_registrados = True

    import src.compartilhado.infraestrutura.outbox_mapping  # noqa: F401
    from src.autenticacao.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_autenticacao,
    )
    from src.catalogo_servicos.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_catalogo,
    )
    from src.cliente_veiculo.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_cliente_veiculo,
    )
    from src.estoque.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_estoque,
    )
    from src.ordem_servico.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_ordem_servico,
    )

    iniciar_autenticacao()
    iniciar_cliente_veiculo()
    iniciar_catalogo()
    iniciar_estoque()
    iniciar_ordem_servico()


@pytest.fixture(scope="session")
def engine() -> Generator[Engine]:
    from src.compartilhado.infraestrutura.database import criar_engine, metadata

    _registrar_todos_mapeamentos()

    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if database_url:
        eng = criar_engine(database_url)
        metadata.create_all(eng)
        yield eng
        metadata.drop_all(eng)
        eng.dispose()
    else:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16") as postgres:
            eng = criar_engine(postgres.get_connection_url())
            metadata.create_all(eng)
            yield eng
            eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session]:
    from sqlalchemy.orm import Session as SASession

    # Each test gets a fresh connection + transaction. The session uses
    # join_transaction_mode="create_savepoint" so that session.commit()
    # releases a SAVEPOINT instead of committing the outer transaction.
    # On teardown, the outer transaction is rolled back, undoing all
    # changes including any committed SAVEPOINTs.
    connection = engine.connect()
    transaction = connection.begin()
    sess = SASession(bind=connection, join_transaction_mode="create_savepoint")

    yield sess

    sess.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
