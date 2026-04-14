.PHONY: lint format typecheck security test test-integ test-all check all

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check src/ tests/ --fix

typecheck:
	mypy src/

security:
	bandit -r src/ -c pyproject.toml --severity-level high

test:
	pytest tests/unitarios/ -x -q --no-lint --cov=src --cov-fail-under=80

test-integ:
	pytest tests/integracao/ -x -q --no-lint --tb=short

test-all:
	pytest tests/ -x -q --no-lint

check: lint typecheck security test
	@echo "All checks passed"

all: format check test-integ
	@echo "Full pipeline passed"
