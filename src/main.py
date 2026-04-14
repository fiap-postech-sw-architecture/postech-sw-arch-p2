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
    """Ciclo de vida do app: inicializa logging no startup e libera no shutdown."""
    from src.compartilhado.infraestrutura.logging import configurar_logging

    configurar_logging()
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
