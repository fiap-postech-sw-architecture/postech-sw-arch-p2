from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

_mapeamentos_registrados = False

# Sinaliza para o resumo final que a integração foi pulada por falta de Docker.
_pulou_por_docker = False

# Aviso destacado impresso no fim da sessão quando os testes de integração são
# pulados por Docker indisponível — orienta a ação manual (NÃO é erro).
_AVISO_DOCKER_LINHAS = (
    "Os testes de INTEGRAÇÃO sobem um Postgres efêmero via testcontainers e",
    "precisam de um daemon Docker acessível — que NÃO está respondendo agora.",
    "",
    "  ->  Foram PULADOS (não falharam). Para rodá-los, suba o Docker e repita:",
    "        colima start          # se usa Colima",
    "        # ou abra o Docker Desktop",
    "      depois:  make test-integ",
    "",
    "  ->  Sem Docker, aponte para um Postgres externo:",
    "        TEST_DATABASE_URL=postgresql://usuario:senha@host:5432/banco",
    "",
    "  Os testes UNITÁRIOS não precisam de Docker e rodaram normalmente.",
)


def _usa_docker() -> bool:
    """A integração usa testcontainers (Docker) salvo se um DB externo for dado."""
    return not (os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL"))


def _docker_disponivel() -> bool:
    """True se o daemon Docker responde ao ping (testcontainers precisa dele)."""
    try:
        import docker

        cliente = docker.from_env(timeout=5)
        try:
            cliente.ping()
        finally:
            cliente.close()
        return True
    except Exception:
        return False


def _registrar_todos_mapeamentos() -> None:
    global _mapeamentos_registrados
    if _mapeamentos_registrados:
        return
    # codeql[py/unused-global-variable] -- flag guard init-once
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
        if not _docker_disponivel():
            global _pulou_por_docker
            _pulou_por_docker = True
            pytest.skip(
                "Docker indisponível — testes de integração pulados "
                "(veja o aviso destacado no fim da sessão)."
            )
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16") as postgres:
            eng = criar_engine(postgres.get_connection_url())
            metadata.create_all(eng)
            yield eng
            eng.dispose()


def pytest_terminal_summary(terminalreporter: object) -> None:
    """Imprime um aviso destacado se a integração foi pulada por falta de Docker.

    Roda no fim da sessão, então aparece mesmo com a captura de saída padrão do
    pytest (diferente de um ``print`` dentro do fixture, que fica capturado)."""
    if not _pulou_por_docker:
        return
    tr = terminalreporter
    tr.write_sep("=", "AÇÃO NECESSÁRIA: Docker não está rodando", red=True, bold=True)  # type: ignore[attr-defined]
    for linha in _AVISO_DOCKER_LINHAS:
        tr.write_line("  " + linha, yellow=True)  # type: ignore[attr-defined]
    tr.write_sep("=", "", red=True, bold=True)  # type: ignore[attr-defined]


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
