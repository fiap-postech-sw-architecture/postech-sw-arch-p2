# Prefixo de execucao Python. Preferencia: `uv run` (resolve no ambiente do
# uv.lock sem exigir venv ativo). Fallback: `.venv/bin/` se existir. Ultimo
# recurso: PATH atual (exige venv ativo). Veja ADR-014 para o racional uv-first.
# Sobrescreva com `PY="uv run "` ou `PY=".venv/bin/"` se quiser forcar.
PY := $(shell \
  if command -v uv >/dev/null 2>&1; then printf 'uv run '; \
  elif [ -x .venv/bin/python ]; then printf '.venv/bin/'; \
  else printf ''; \
  fi)

.PHONY: lint format typecheck security test test-integ test-all check all up down seed

up:
	@bash -c 'source scripts/docker-check.sh && docker compose up -d'

down:
	@bash -c 'source scripts/docker-check.sh && docker compose down'

seed:
	@bash -c 'set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; python scripts/seed_admin.py'

lint:
	$(PY)ruff check src/ tests/
	$(PY)ruff format --check src/ tests/

format:
	$(PY)ruff format src/ tests/
	$(PY)ruff check src/ tests/ --fix

typecheck:
	$(PY)mypy src/

security:
	$(PY)bandit -r src/ -c pyproject.toml --severity-level high

test:
	$(PY)pytest tests/unitarios/ -x -q --no-lint --cov=src

test-integ:
	$(PY)pytest tests/integracao/ -x -q --no-lint --tb=short

test-all:
	$(PY)pytest tests/ -x -q --no-lint

check: lint typecheck security test
	@echo "All checks passed"

all: format check test-integ
	@echo "Full pipeline passed"
