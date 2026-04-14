from __future__ import annotations

import os
from uuid import uuid4

import structlog
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

_CSP_DEFAULT = "default-src 'none'"
# Paths that serve Swagger UI / ReDoc / OpenAPI schema. The default CSP blocks
# the inline scripts and styles those tools rely on, so we skip CSP there.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Anexa headers de seguranca em toda resposta e propaga um request_id unico.

    Vincula o request_id ao contexto do structlog para correlacionar logs dentro
    do mesmo request. Os headers aplicados estao listados no metodo dispatch.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Cache-Control"] = "no-store"
        if not any(request.url.path.startswith(p) for p in _DOCS_PATHS):
            response.headers["Content-Security-Policy"] = _CSP_DEFAULT
        response.headers["X-Request-ID"] = request_id
        return response


def configurar_cors(app: FastAPI) -> None:
    """Configura CORS a partir da variavel CORS_ORIGINS (lista separada por virgulas).

    Vazio significa nenhuma origem permitida. O wildcard `*` combinado com
    credenciais e proibido pela especificacao CORS e rejeitado em startup.
    """
    origens = os.environ.get("CORS_ORIGINS", "")
    lista_origens = [o.strip() for o in origens.split(",") if o.strip()]
    if "*" in lista_origens:
        msg = (
            "CORS_ORIGINS='*' nao e suportado com allow_credentials=True. "
            "Defina origens explicitas."
        )
        raise ValueError(msg)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=lista_origens,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
    )


def configurar_rate_limiting(app: FastAPI) -> None:
    """Instala o SlowAPIMiddleware com limite padrao configuravel via RATE_LIMIT.

    Padrao `60/minute` por IP. O storage e em memoria, portanto cada replica tem
    seu proprio contador; para producao multi-instancia configure um backend
    compartilhado (Redis).
    """
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    default_limit = os.environ.get("RATE_LIMIT", "60/minute")
    limiter = Limiter(key_func=get_remote_address, default_limits=[default_limit])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
