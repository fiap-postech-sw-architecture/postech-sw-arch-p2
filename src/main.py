from __future__ import annotations

import os
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from importlib.metadata import version
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI

from src.compartilhado.interfaces.error_handler import registrar_error_handlers
from src.compartilhado.interfaces.middleware import (
    SecurityHeadersMiddleware,
    configurar_cors,
    configurar_rate_limiting,
)
from src.compartilhado.interfaces.router_publico import router as router_publico

_AMBIENTES_DEV = {"development", "test"}


def _database_url_por_variaveis_postgres() -> str:
    variaveis_obrigatorias = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    ausentes = [nome for nome in variaveis_obrigatorias if not os.environ.get(nome)]
    if ausentes:
        msg = (
            f"Variaveis obrigatorias ausentes: {ausentes!r}. Configure POSTGRES_DB, "
            "POSTGRES_USER e POSTGRES_PASSWORD, ou defina DATABASE_URL."
        )
        raise RuntimeError(msg)

    postgres_db = quote(os.environ["POSTGRES_DB"], safe="")
    postgres_user = quote(os.environ["POSTGRES_USER"], safe="")
    postgres_password = quote(os.environ["POSTGRES_PASSWORD"], safe="")
    postgres_host = os.environ.get("POSTGRES_HOST", "localhost")
    postgres_port = os.environ.get("POSTGRES_PORT", "5432")
    return (
        f"postgresql://{postgres_user}:{postgres_password}"
        f"@{postgres_host}:{postgres_port}/{postgres_db}"
    )


def _obter_database_url(environment: str) -> str:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url
    if environment in _AMBIENTES_DEV:
        return _database_url_por_variaveis_postgres()

    msg = "DATABASE_URL obrigatoria quando ENVIRONMENT nao for 'development' ou 'test'."
    raise RuntimeError(msg)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Ciclo de vida do app: inicializa logging + mappings no startup."""
    from src.compartilhado.infraestrutura.logging import configurar_logging

    configurar_logging()

    # Banner de boot. SHA/data sao injetadas em todo log structlog pelo
    # processor `adicionar_versao_imagem` (configurar_logging acima) --
    # nao precisa de `bind_contextvars` aqui, que seria limpado pelo
    # SecurityHeadersMiddleware a cada request. `print` garante
    # visibilidade imediata antes do stdlib logging ter handler do
    # uvicorn.
    git_sha = os.environ.get("PYTSTOP_GIT_SHA", "unknown")[:12]
    git_date = os.environ.get("PYTSTOP_GIT_DATE", "unknown")
    print(f">>> pytstop server | commit {git_sha} | {git_date}", flush=True)

    # Registra os imperative mappings de cada bounded context antes de
    # aceitar requisicoes. Cada ``iniciar_mapeamentos`` e idempotente
    # (guard interno via flag booleana), seguro para chamar em warm
    # restarts e em testes. A ORDEM importa: contexts a montante devem
    # vir primeiro porque OS referencia clientes/veiculos via FK, e
    # estoque/catalogo nao podem depender de tabelas ainda ausentes
    # no metadata. Ao adicionar um novo context, posicione seu
    # ``iniciar_*()`` ANTES dos contexts que dependem dele.
    from src.autenticacao.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_auth,
    )
    from src.catalogo_servicos.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_catalogo,
    )
    from src.cliente_veiculo.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_cliente,
    )
    from src.estoque.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_estoque,
    )
    from src.ordem_servico.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_os,
    )

    iniciar_cliente()
    iniciar_catalogo()
    iniciar_estoque()
    iniciar_os()
    iniciar_auth()

    # Configura a session factory global antes de aceitar requisicoes.
    # Sem isso, todo endpoint que depende de ``obter_session`` falha com
    # ``RuntimeError("Session factory nao configurada")``. O engine e
    # descartado no shutdown para liberar o pool de conexoes.
    from src.compartilhado.infraestrutura.database import (
        criar_engine,
        criar_session_factory,
    )
    from src.compartilhado.infraestrutura.observability import configurar_otel
    from src.compartilhado.interfaces.dependencies import (
        configurar_session_factory,
    )

    # DATABASE_URL explicita tem precedencia. Em dev/test, a URL pode ser
    # montada pelas variaveis POSTGRES_* do compose/env local; a senha nunca
    # fica hardcoded no codigo.
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    database_url = _obter_database_url(environment)
    engine = criar_engine(database_url)
    configurar_session_factory(criar_session_factory(engine))

    # Observabilidade OTLP (ADR-020): unico ponto onde app + engine existem
    # juntos. Default OFF (OTEL_ENABLED ausente/false) — no-op sem custo.
    configurar_otel(app, engine)
    try:
        yield
    finally:
        engine.dispose()
        from src.compartilhado.interfaces.router_admin import (
            encerrar_engine_admin,
        )

        encerrar_engine_admin()


def criar_app() -> FastAPI:
    """Fabrica o FastAPI com middleware de seguranca, CORS, rate limiting e handlers.

    Docs (`/docs`, `/redoc`) sao desabilitados quando `ENVIRONMENT=production`.
    """
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    docs_url = "/docs" if environment != "production" else None
    redoc_url = "/redoc" if environment != "production" else None

    application = FastAPI(
        title="PytStop",
        version=version("pytstop"),
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    application.include_router(router_publico)

    from src.compartilhado.interfaces.router_admin import router as router_admin

    application.include_router(router_admin)

    # Importacoes dos routers sao locais (dentro de criar_app) para
    # manter o ciclo de vida do app limpo em tempo de import e evitar
    # instanciacao precoce de dependencias.
    from src.autenticacao.interfaces.router import router as auth_router
    from src.catalogo_servicos.interfaces.router import router as catalogo_router
    from src.cliente_veiculo.interfaces.router import router as cliente_router
    from src.estoque.interfaces.router import router as estoque_router
    from src.ordem_servico.interfaces.router import router as os_router

    application.include_router(cliente_router)
    application.include_router(catalogo_router)
    application.include_router(estoque_router)
    application.include_router(os_router)
    application.include_router(auth_router)

    # Middleware execution order (Starlette "last added runs first" on request,
    # reversed on response). SecurityHeadersMiddleware is added last so it is
    # the OUTERMOST wrapper: it runs first on the request (stamping the
    # request_id) and last on the response (stamping security headers),
    # guaranteeing the headers land on CORS preflight replies and on 429s
    # from the rate limiter.
    configurar_cors(application)
    configurar_rate_limiting(application)
    application.add_middleware(SecurityHeadersMiddleware)
    registrar_error_handlers(application)

    return application


app = criar_app()


def executar_servidor_dev() -> None:
    """Executa o servidor local quando o modulo e chamado como script."""
    uvicorn.run(
        "src.main:app",
        host=os.environ.get("UVICORN_HOST", "127.0.0.1"),
        port=int(os.environ.get("UVICORN_PORT", "8000")),
        reload=True,
    )


if __name__ == "__main__":
    executar_servidor_dev()
