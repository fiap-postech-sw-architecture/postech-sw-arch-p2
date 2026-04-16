from __future__ import annotations

import os
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from importlib.metadata import version

import uvicorn
from fastapi import FastAPI

from src.compartilhado.interfaces.error_handler import registrar_error_handlers
from src.compartilhado.interfaces.middleware import (
    SecurityHeadersMiddleware,
    configurar_cors,
    configurar_rate_limiting,
)
from src.compartilhado.interfaces.router_publico import router as router_publico


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida do app: inicializa logging + mappings no startup."""
    from src.compartilhado.infraestrutura.logging import configurar_logging

    configurar_logging()

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
    yield


def criar_app() -> FastAPI:
    """Fabrica o FastAPI com middleware de seguranca, CORS, rate limiting e handlers.

    Docs (`/docs`, `/redoc`) sao desabilitados quando `ENVIRONMENT=production`.
    """
    environment = os.environ.get("ENVIRONMENT", "development")
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

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104
