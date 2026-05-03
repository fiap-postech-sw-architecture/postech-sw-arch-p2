# syntax=docker/dockerfile:1.7
# Imagem base com Python 3.13 + uv pre-instalado (Astral oficial).
# Ver ADR-014 para justificativa da escolha do uv como gerenciador.
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .

# Re-sync apos COPY instala o proprio projeto.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime

RUN groupadd -r pytstop && useradd -r -g pytstop pytstop

WORKDIR /app

# Copia o venv materializado pelo uv e o codigo da aplicacao.
COPY --from=builder --chown=pytstop:pytstop /app /app

# Adiciona o venv ao PATH para que `uvicorn`, `alembic`, `python` usem as versoes
# resolvidas pelo uv.lock em vez de qualquer binario do sistema.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN chmod +x entrypoint.sh

USER pytstop
EXPOSE 8000
CMD ["./entrypoint.sh"]
