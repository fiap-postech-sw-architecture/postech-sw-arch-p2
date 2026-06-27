from __future__ import annotations

import os
from uuid import uuid4

import structlog
from fastapi import FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address
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


def _resolver_storage_uri() -> str | None:
    """Resolve o backend de storage do rate limiter a partir do ambiente.

    Retorna o valor de ``RATE_LIMIT_STORAGE_URI`` quando definido (ex.:
    ``redis://host:6379``), habilitando um contador COMPARTILHADO entre
    replicas. Retorna ``None`` quando ausente ou vazio — o SlowAPI faz
    fallback para ``memory://`` (contador por-processo).
    """
    return os.environ.get("RATE_LIMIT_STORAGE_URI") or None


# Singleton compartilhado entre todos os routers que queiram aplicar
# rate limits por endpoint via ``@limiter.limit("...")``.
#
# CRITICO: o decorator do SlowAPI (``@limiter.limit(...)``) precisa
# usar a MESMA instancia de ``Limiter`` que o ``SlowAPIMiddleware`` le
# de ``app.state.limiter``. Caso contrario os contadores ficam em
# instancias diferentes e o limite nunca e enforcado. Por isso
# expomos este ``limiter`` em escopo de modulo e
# ``configurar_rate_limiting`` apenas o anexa ao app + registra o
# middleware/handler.
#
# O limite padrao e lido do env var ``RATE_LIMIT`` em tempo de
# import — o processo ja deve ter as env vars setadas antes de
# importar este modulo, o que e verdade no fluxo ``criar_app`` ->
# ``configurar_rate_limiting``.
_default_limit = os.environ.get("RATE_LIMIT", "60/minute")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_default_limit],
    storage_uri=_resolver_storage_uri(),
)


def configurar_rate_limiting(app: FastAPI) -> None:
    """Anexa o ``limiter`` compartilhado ao app e instala o SlowAPIMiddleware.

    O storage do contador e configuravel e compartilhado entre replicas:
    quando ``RATE_LIMIT_STORAGE_URI`` esta definido (ex.: ``redis://...``),
    o backend Redis fica ativo e o limite e enforcado de forma agregada
    entre os processos. Sem a variavel, o fallback e ``memory://``
    (por-processo).
    """
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
