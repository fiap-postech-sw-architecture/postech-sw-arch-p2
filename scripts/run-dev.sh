#!/usr/bin/env bash
# Script de execucao do servidor FastAPI em modo de desenvolvimento com hot reload.
#
# Uso:
#   ./scripts/run-dev.sh
#
# Pre-requisitos:
#   - Postgres rodando (veja docker-compose.yml: `docker compose up -d postgres`).
#   - Dependencias instaladas via `uv sync --extra test --frozen` (ou fallback
#     `python -m venv .venv && pip install -e ".[test]"`).
#   - Migrations aplicadas (`uv run alembic upgrade head` ou
#     `RUN_MIGRATIONS_ON_STARTUP=true` + entrypoint.sh).
#   - Arquivo opcional `.env.dev` com overrides (nao versionado).
#
# Todas as variaveis abaixo podem ser sobrescritas pelo ambiente antes de chamar
# o script (ex.: `UVICORN_PORT=9000 ./scripts/run-dev.sh`).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

# Carrega overrides locais se presentes.
if [[ -f .env.dev ]]; then
    # shellcheck disable=SC1091
    set -a
    . .env.dev
    set +a
fi

# Defaults de desenvolvimento.
: "${DATABASE_URL:=postgresql://pytstop:pytstop@localhost:5432/pytstop}"
: "${JWT_SECRET:=dev-secret-change-me-this-is-at-least-32-bytes-long-for-hs256}"
: "${JWT_EXPIRATION_MINUTES:=30}"
: "${ENVIRONMENT:=development}"
: "${CORS_ORIGINS:=http://localhost:3000}"
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT:=8001}"

export DATABASE_URL JWT_SECRET JWT_EXPIRATION_MINUTES ENVIRONMENT CORS_ORIGINS

echo "Iniciando uvicorn em http://${UVICORN_HOST}:${UVICORN_PORT} (reload ativado)"

# Prefere `uv run` (funciona sem ativar venv e garante o ambiente do uv.lock);
# cai para `.venv/bin/uvicorn` se uv nao estiver disponivel (fallback
# documentado na ADR-014).
if command -v uv >/dev/null 2>&1; then
    exec uv run uvicorn src.main:app \
        --reload \
        --host "${UVICORN_HOST}" \
        --port "${UVICORN_PORT}"
fi

if [[ ! -x .venv/bin/uvicorn ]]; then
    echo "ERRO: nem 'uv' nem '.venv/bin/uvicorn' encontrados." >&2
    echo "  Rode 'uv sync --extra test --frozen' (ou 'python -m venv .venv && pip install -e \".[test]\"')." >&2
    exit 1
fi

exec .venv/bin/uvicorn src.main:app \
    --reload \
    --host "${UVICORN_HOST}" \
    --port "${UVICORN_PORT}"
