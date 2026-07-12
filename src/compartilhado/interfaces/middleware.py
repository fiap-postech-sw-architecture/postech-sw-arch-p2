from __future__ import annotations

import os
from uuid import uuid4

import structlog
from fastapi import FastAPI
from limits import parse_many
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_CSP_DEFAULT = "default-src 'none'"
# Paths that serve Swagger UI / ReDoc / OpenAPI schema. The default CSP blocks
# the inline scripts and styles those tools rely on, so we skip CSP there.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _caminho_de_docs(path: str) -> bool:
    """True para o proprio path de docs ou um filho dele (barra obrigatoria).

    Igualdade exata ou prefixo TERMINADO em "/": ``/docs`` e ``/docs/oauth2``
    casam; ``/docsarquivo`` (prefixo acidental) NAO casa e mantem o CSP.
    """
    return any(path == p or path.startswith(p + "/") for p in _DOCS_PATHS)


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
        if not _caminho_de_docs(request.url.path):
            response.headers["Content-Security-Policy"] = _CSP_DEFAULT
        response.headers["X-Request-ID"] = request_id
        return response


# Ambientes que NAO exercem a guarda de segredos (issue #74): dev local,
# docker-compose e a suite de testes sobem deliberadamente com segredos de
# demonstracao. Qualquer outro valor de ENVIRONMENT (notadamente "production")
# e tratado como producao e dispara a validacao -- mesma postura de
# `_obter_database_url` em src/main.py.
_AMBIENTES_SEM_VALIDACAO_DE_SEGREDOS = frozenset({"development", "test"})

# HS256 exige uma chave com no minimo 32 bytes; abaixo disso o segredo e
# trivialmente forjavel (k8s/secret.yaml fala em BYTES -- medimos byte length).
_JWT_SECRET_MIN_BYTES = 32

# Literais de segredo de DEMONSTRACAO publicos no git -- proibidos em producao.
# Fonte de cada valor (paridade dev x cluster):
#   k8s/secret.yaml (JWT_SECRET, ENCRYPTION_KEY, ORCAMENTO_WEBHOOK_TOKEN,
#     ADMIN_PASSWORD)
#   .env.dev / .env.dev.example (JWT_SECRET, ENCRYPTION_KEY, ORCAMENTO_WEBHOOK_TOKEN)
#   docker-compose.yml (ORCAMENTO_WEBHOOK_TOKEN)
# Mantenha em sincronia se algum desses defaults de demo mudar.
_SEGREDOS_DEMO_PROIBIDOS = frozenset(
    {
        # JWT_SECRET demo: k8s/secret.yaml e .env.dev*, respectivamente.
        "demo-jwt-secret-pytstop-fase2-no-minimo-32-bytes",
        "dev-secret-change-me-this-is-at-least-32-bytes-long-for-hs256",
        # ENCRYPTION_KEY demo (chaves Fernet): k8s/secret.yaml e .env.dev*.
        # `gitleaks:allow` -- base64 de 44 chars dispara o generic-api-key.
        "C9I0jOzZ9kJBTY0akV3TvBO2wa1JcuAdR-Wctnzee6I=",  # gitleaks:allow
        "o2PanCXdqDQ87JA2AOA1oNazx5bGwSdUZrHY1rvHnx0=",  # gitleaks:allow
        # ORCAMENTO_WEBHOOK_TOKEN demo (k8s/secret.yaml == docker-compose == .env.dev*).
        "demo-webhook-orcamento-nao-usar-em-producao",
        # ADMIN_PASSWORD demo: so em k8s/secret.yaml (.env.dev* deixa em branco;
        # docker-compose.yml nao define ADMIN_PASSWORD).
        "pytstop-admin-demo-2026",  # gitleaks:allow
    }
)


def validar_segredos_no_startup() -> None:
    """Valida os segredos sensiveis no startup; aborta o boot em producao.

    Fecha dois controles de seguranca que a documentacao (k8s/secret.yaml,
    RFC-001 e RFC-002) afirma existir (issue #74). EM PRODUCAO (qualquer
    ENVIRONMENT que nao seja `development`/`test`):

    1. ``JWT_SECRET`` ausente ou com menos de 32 BYTES -> aborta. HS256 com
       chave curta e trivialmente forjavel.
    2. ``JWT_SECRET`` / ``ENCRYPTION_KEY`` / ``ORCAMENTO_WEBHOOK_TOKEN`` /
       ``ADMIN_PASSWORD`` iguais a um literal de demonstracao publico no git ->
       aborta. Cada um e validado apenas quando presente (ausente -> ignorado).
    3. ``ENCRYPTION_KEY`` ausente -> aborta (issue #73). A chave efemera de
       fallback tornaria os dados cifrados irrecuperaveis apos restart e
       divergiria o ``documento_hash`` entre replicas.

    Espelha o `configurar_cors`: falha o boot (``raise``), nao apenas avisa --
    uma pre-condicao de seguranca nao satisfeita NUNCA deve subir aceitando
    requisicoes. Fora de producao a funcao retorna cedo (no-op), entao dev,
    docker-compose e a suite de testes seguem subindo com os segredos de demo.
    """
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    if environment in _AMBIENTES_SEM_VALIDACAO_DE_SEGREDOS:
        return

    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        msg = (
            "JWT_SECRET nao configurado em producao. HS256 exige uma chave de "
            f">= {_JWT_SECRET_MIN_BYTES} bytes; defina um segredo forte via Secret."
        )
        raise RuntimeError(msg)
    if len(jwt_secret.encode("utf-8")) < _JWT_SECRET_MIN_BYTES:
        msg = (
            f"JWT_SECRET tem menos de {_JWT_SECRET_MIN_BYTES} bytes. HS256 exige "
            f">= {_JWT_SECRET_MIN_BYTES} bytes; gere um segredo forte "
            "(ex.: openssl rand -hex 32)."
        )
        raise RuntimeError(msg)

    if not os.environ.get("ENCRYPTION_KEY"):
        msg = (
            "ENCRYPTION_KEY nao configurada em producao (issue #73). Sem ela o "
            "app sobe com uma chave Fernet efemera -> dados cifrados ficam "
            "irrecuperaveis apos restart e o documento_hash diverge entre "
            "replicas. Injete uma chave real via Secret (gere com "
            "cryptography.fernet.Fernet.generate_key())."
        )
        raise RuntimeError(msg)

    for nome in (
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "ORCAMENTO_WEBHOOK_TOKEN",
        "ADMIN_PASSWORD",
    ):
        valor = os.environ.get(nome)
        if valor and valor in _SEGREDOS_DEMO_PROIBIDOS:
            msg = (
                f"{nome} usa um segredo de demonstracao publico no git -- proibido "
                "em producao. Injete um segredo real via Secret (RFC-002 §6)."
            )
            raise RuntimeError(msg)


def configurar_cors(app: FastAPI) -> None:
    """Configura CORS a partir da variavel CORS_ORIGINS (lista separada por virgulas).

    Vazio significa nenhuma origem permitida. O wildcard `*` e rejeitado em
    startup: a API exige origens explicitas, sem allow-any.

    ``allow_credentials=False``: a API e bearer-only (token no header
    Authorization), sem cookies nem sessao -- nenhum fluxo depende de
    credenciais no CORS, entao mante-las desligadas reduz a superficie.
    """
    origens = os.environ.get("CORS_ORIGINS", "")
    lista_origens = [o.strip() for o in origens.split(",") if o.strip()]
    if "*" in lista_origens:
        msg = "CORS_ORIGINS='*' nao e suportado. Defina origens explicitas."
        raise ValueError(msg)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=lista_origens,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )


def _resolver_trusted_proxies() -> list[str]:
    """Resolve a lista de proxies confiaveis a partir do ambiente.

    Le ``TRUSTED_PROXIES`` (hosts separados por virgula) e devolve a lista de
    tokens nao vazios. Cada token e passado ao ``trusted_hosts`` do
    ``ProxyHeadersMiddleware`` do uvicorn, que aceita IP exato (``10.0.0.5``),
    rede CIDR (``10.0.0.0/8``) ou o wildcard ``*`` (confia em qualquer peer).

    PERIGO: ``*`` confia em QUALQUER peer e usa o XFF mais a esquerda
    (spoofavel) -- so com a app ESTRITAMENTE ClusterIP atras de proxy
    confiavel, nunca exposta direto.

    Vazio (ausente, em branco ou so virgulas) -> lista vazia -> o middleware
    NAO e instalado e o ``X-Forwarded-For`` e ignorado. Default SEGURO: sem
    configuracao explicita nunca se confia no XFF (sem risco de spoof do IP
    do cliente).
    """
    bruto = os.environ.get("TRUSTED_PROXIES", "")
    return [host.strip() for host in bruto.split(",") if host.strip()]


def configurar_proxy_headers(app: FastAPI) -> None:
    """Instala o ``ProxyHeadersMiddleware`` do uvicorn quando ha proxy confiavel.

    Quando ``TRUSTED_PROXIES`` esta definido, o middleware reescreve
    ``scope["client"]`` a partir do ``X-Forwarded-For`` SOMENTE quando o peer
    imediato (o IP da conexao TCP) esta na lista de confianca — entao
    ``get_remote_address`` (chave do rate limiter) passa a devolver o IP real
    do cliente, e nao o IP do proxy/ingress (TD-023). Vazio (default) -> nao
    instala -> comportamento atual preservado (XFF ignorado, sem spoof).

    O servidor uvicorn roda com ``--no-proxy-headers`` (``entrypoint.sh``), o
    que DESLIGA o proxy-headers embutido dele (ligado por padrao com
    ``forwarded_allow_ips="127.0.0.1"``, que confiaria no XFF de peers
    loopback). Assim ``TRUSTED_PROXIES`` -- via este middleware -- e o UNICO
    controle de confianca no ``X-Forwarded-For``, e o default vazio ignora o
    XFF de TODOS os peers (inclusive loopback), batendo com os testes.

    ORDEM (Starlette: o ULTIMO middleware adicionado e o MAIS EXTERNO e roda
    PRIMEIRO no request). Este precisa rodar ANTES do ``SlowAPIMiddleware``
    para que o ``client`` ja esteja reescrito quando o limiter ler
    ``request.client.host``. ``criar_app`` adiciona este middleware DEPOIS de
    ``configurar_rate_limiting`` justamente para coloca-lo por fora do
    SlowAPI. ``SecurityHeadersMiddleware``, adicionado por ultimo, fica ainda
    mais externo (so estampa request_id/headers, nao depende do client).

    PERIGO: ``*`` em ``TRUSTED_PROXIES`` confia em QUALQUER peer e usa o XFF
    mais a esquerda (spoofavel) -- so com a app ESTRITAMENTE ClusterIP atras
    de proxy confiavel, nunca exposta direto.
    """
    trusted = _resolver_trusted_proxies()
    if not trusted:
        return
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)


def _resolver_storage_uri() -> str | None:
    """Resolve o backend de storage do rate limiter a partir do ambiente.

    Retorna o valor de ``RATE_LIMIT_STORAGE_URI`` quando definido (ex.:
    ``redis://host:6379``), habilitando um contador COMPARTILHADO entre
    replicas. Retorna ``None`` quando ausente, vazio ou só com espaços — o
    SlowAPI faz fallback para ``memory://`` (contador por-processo). O
    ``strip()`` evita que um valor em branco chegue a
    ``limits.storage_from_string`` e dispare ``ConfigurationError`` no import.
    """
    return (os.environ.get("RATE_LIMIT_STORAGE_URI") or "").strip() or None


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
# ``configurar_rate_limiting``. A validacao e EAGER (no import): um
# valor malformado aborta o boot com mensagem clara, em vez de virar
# 500 na primeira request rate-limitada (o SlowAPI so parseia o
# limite lazily na avaliacao).
_default_limit = os.environ.get("RATE_LIMIT", "60/minute")
try:
    parse_many(_default_limit)
except ValueError as _exc:
    _pref = f"RATE_LIMIT invalido: {_default_limit!r}"
    _msg = f"{_pref}. Use a notacao do pacote `limits` (ex.: '60/minute', '100/hour')."
    raise RuntimeError(_msg) from _exc
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_default_limit],
    storage_uri=_resolver_storage_uri(),
    # GRACEFUL DEGRADATION (TD-016): sem isto, se o Redis configurado em
    # ``storage_uri`` ficar inalcancavel em runtime o SlowAPI re-raisa o
    # ``ConnectionError`` e TODA request rate-limitada vira 500 — o Redis
    # vira SPOF no hot path. Com a flag, na primeira falha de storage o
    # SlowAPI marca ``_storage_dead`` e cai para um limiter in-memory
    # por-processo que reaproveita os MESMOS ``default_limits`` (o limite
    # SEGUE sendo enforcado, so deixa de ser agregado entre replicas), e
    # auto-recupera quando o backend volta (``slowapi/extension.py``
    # ``_storage_dead``/``_fallback_limiter``). Disponibilidade > contagem
    # exata durante um blip de Redis.
    in_memory_fallback_enabled=True,
)


def handler_rate_limit_excedido(request: Request, exc: Exception) -> Response:
    """429 no envelope de erro do contrato da API (em vez do default do SlowAPI).

    O ``_rate_limit_exceeded_handler`` do SlowAPI responde ``{"error": ...}``,
    fora do envelope ``{erro: {codigo, mensagem, id_requisicao}}`` que todos
    os outros status usam (``error_handler.py``). Este handler devolve o
    envelope do contrato e PRESERVA a injecao de headers do limiter
    (``Retry-After``/``X-RateLimit-*`` quando ``headers_enabled``), fazendo o
    mesmo pos-processamento do handler default.
    """
    detalhe = getattr(exc, "detail", "limite de requisicoes excedido")
    response: Response = JSONResponse(
        status_code=429,
        content={
            "erro": {
                "codigo": "RATE_LIMIT_EXCEDIDO",
                "mensagem": f"Limite de requisicoes excedido: {detalhe}",
                "id_requisicao": getattr(request.state, "request_id", "desconhecido"),
            }
        },
    )
    # Mesmo pos-processamento do handler default do SlowAPI (que tambem chama
    # o metodo privado _inject_headers do limiter).
    com_headers: Response = request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
    return com_headers


def configurar_rate_limiting(app: FastAPI) -> None:
    """Anexa o ``limiter`` compartilhado ao app e instala o SlowAPIMiddleware.

    O storage do contador e configuravel e compartilhado entre replicas:
    quando ``RATE_LIMIT_STORAGE_URI`` esta definido (ex.: ``redis://...``),
    o backend Redis fica ativo e o limite e enforcado de forma agregada
    entre os processos. Sem a variavel, o fallback e ``memory://``
    (por-processo). O 429 responde no envelope de erro do contrato via
    ``handler_rate_limit_excedido``.
    """
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, handler_rate_limit_excedido)
