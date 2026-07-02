# syntax=docker/dockerfile:1.7
# Imagem base com Python 3.13 + uv pre-instalado (Astral oficial).
# Ver ADR-014 para justificativa da escolha do uv como gerenciador.
# builder e runtime DEVEM usar a MESMA minor do Python: o venv copiado
# (--from=builder) carrega bytecode/wheels compilados para a versao do builder,
# e a versao efetiva vem do `.python-version` (uv respeita) — nao basta trocar o
# base image. Python 3.14 deferido: `vbuild` (dep transitiva do NiceGUI/UI) usa
# `pkgutil.find_loader`, removido no 3.14.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copia somente os manifests primeiro para maximizar cache: enquanto pyproject/lock
# nao mudam, a layer de dependencias e reutilizada mesmo com o codigo mudando.
COPY pyproject.toml uv.lock ./

# --frozen falha se uv.lock estiver desatualizado em relacao a pyproject.toml;
# --no-dev exclui extras de teste do ambiente de producao.
# --extra otel (ADR-020): imagem unica com o SDK OpenTelemetry disponivel —
# a instrumentacao liga somente por env (OTEL_ENABLED, default off). Custo
# aceito: ~40MB no venv (grpcio e o maior componente) em troca de nao manter
# duas imagens nem rebuildar para a demo de traces.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra otel

COPY . .

# Re-sync apos COPY instala o proprio projeto.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra otel

FROM python:3.13-slim AS runtime

ARG GIT_SHA=unknown
ARG GIT_DATE=unknown

LABEL org.opencontainers.image.title="postech-sw-arch-p2 app" \
      org.opencontainers.image.source="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2" \
      org.opencontainers.image.description="FastAPI backend (PytStop)." \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${GIT_DATE}"

# UID/GID fixos (1001): o securityContext do k8s (TD-024) usa runAsUser/fsGroup
# numericos, e o kubelet so consegue verificar runAsNonRoot com um UID numerico
# (um USER por nome nao e resolvivel no admission). Pinar aqui mantem o dono dos
# arquivos (/app) igual ao runAsUser, compativel com readOnlyRootFilesystem.
RUN groupadd -r -g 1001 pytstop && useradd -r -u 1001 -g pytstop pytstop

WORKDIR /app

# Copia o venv materializado pelo uv e o codigo da aplicacao.
COPY --from=builder --chown=pytstop:pytstop /app /app

# Adiciona o venv ao PATH para que `uvicorn`, `alembic`, `python` usem as versoes
# resolvidas pelo uv.lock em vez de qualquer binario do sistema.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTSTOP_GIT_SHA="${GIT_SHA}" \
    PYTSTOP_GIT_DATE="${GIT_DATE}"

# Healthcheck embutido na imagem (RNF-019): cobre `docker run` standalone e
# tooling que le o HEALTHCHECK do manifest. Probe em Python+urllib porque a
# imagem slim nao tem curl/wget; 127.0.0.1 evita depender da resolucao de
# localhost. O docker-compose.yml define um healthcheck identico (compose
# tem precedencia quando ambos existem); probes K8s (RNF-023) ignoram este
# HEALTHCHECK e apontam direto para GET /api/v1/saude.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/saude', timeout=2).status==200 else 1)"]

RUN chmod +x entrypoint.sh

USER pytstop
EXPOSE 8000
CMD ["./entrypoint.sh"]
