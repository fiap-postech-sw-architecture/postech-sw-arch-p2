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

# ---- full-test ----
.PHONY: full-test full-test-up full-test-seed full-test-run full-test-ci full-test-teardown

# PYTHONPATH=full-test: torna o pacote `full_test` importavel via `python -m`
# quando rodado a partir da raiz do repo (pytest ja resolve por conftest).
FULL_TEST_PY := PYTHONPATH=full-test uv run python -m full_test

full-test-up:
	@echo ">>> docker compose up -d + health-wait"
	docker compose up -d
	$(FULL_TEST_PY) healthwait --timeout 120

full-test-seed: full-test-up
	@echo ">>> seed_completo (reset + usuarios + catalogo + estoque)"
	$(FULL_TEST_PY) seed

full-test-run: full-test-seed
	@echo ">>> executa plano full (roda SLOW + SLOWEST)"
	$(FULL_TEST_PY) run --plano full

full-test-ci: full-test-seed
	@echo ">>> executa plano ci (exclui slowest)"
	$(FULL_TEST_PY) run --plano ci

full-test-teardown:
	@echo ">>> docker compose down + limpa reports"
	docker compose down -v
	rm -rf full-test/reports

full-test: full-test-up full-test-seed full-test-run full-test-teardown
