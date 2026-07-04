from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from tests.integracao.seed_helpers import criar_usuario

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

    from src.autenticacao.dominio.usuario import Usuario

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

    # APENAS TEST_DATABASE_URL (sem fallback para DATABASE_URL): o teardown
    # faz `drop_all`, e herdar a DATABASE_URL de um ambiente dev apontaria o
    # drop para um banco de trabalho. Quem quer DB externo declara a intencao
    # com a variavel dedicada; sem ela, testcontainers como sempre.
    database_url = os.environ.get("TEST_DATABASE_URL")
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


# ---------------------------------------------------------------------------
# Fixtures de API (TestClient contra o app real) — antes duplicadas em
# test_api_e2e.py e test_admin_outbox.py (issue #173).
# ---------------------------------------------------------------------------

_EMAIL_ADMIN = "admin-integ@test.com"


@pytest.fixture
def session_factory(engine: Engine) -> Generator[sessionmaker[Session]]:
    from sqlalchemy import text

    from src.compartilhado.infraestrutura.database import (
        criar_session_factory,
        metadata,
    )

    factory = criar_session_factory(engine)
    yield factory

    # Testes de API fazem commit REAL atraves do TestClient/Core; o rollback
    # de SAVEPOINT da fixture `session` nao os alcanca. A limpeza trunca TODAS
    # as tabelas do metadata, em ordem reversa de dependencia (dependentes
    # antes de referenciados): a lista manual anterior omitia
    # outbox/processed_events e vazava linhas entre modulos.
    tabelas = ", ".join(t.name for t in reversed(metadata.sorted_tables))
    with factory() as sess:
        sess.execute(text(f"TRUNCATE TABLE {tabelas} CASCADE"))
        sess.commit()


@pytest.fixture
def admin_user(session_factory: sessionmaker[Session]) -> Usuario:
    """Semeia (com commit real) um usuario admin para autenticacao via API."""
    from src.autenticacao.dominio.papel import Papel

    return criar_usuario(session_factory, email=_EMAIL_ADMIN, papel=Papel.ADMIN)


@pytest.fixture(scope="module")
def api_client(engine: Engine) -> Generator[TestClient]:
    """TestClient contra o app REAL apontando para o banco de teste.

    Configura ``DATABASE_URL``/``JWT_SECRET`` antes de instanciar o app; o
    lifespan real cria o engine e registra a session factory — o mesmo wiring
    de ``docker compose up`` (se o bug do session factory voltar, quebra aqui).

    MODULE-scoped: o app e criado uma vez por arquivo (lifespan + pool sao
    caros), enquanto a limpeza segue POR TESTE via teardown de
    ``session_factory`` (os testes que escrevem passam por ``admin_user`` ->
    ``session_factory``). O estado por teste que importa (usuarios, outbox,
    OS...) vive no banco, nao no client: JWTs sao stateless e emitidos por
    login em cada teste; env e re-lido por request nos endpoints que o usam.
    """
    from fastapi.testclient import TestClient

    from src.main import criar_app

    mp = pytest.MonkeyPatch()
    mp.setenv("JWT_SECRET", "test-secret-at-least-32-bytes-long-for-hs256-signing")
    mp.setenv("ENVIRONMENT", "test")
    mp.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    try:
        with TestClient(criar_app()) as client:
            yield client
    finally:
        mp.undo()
