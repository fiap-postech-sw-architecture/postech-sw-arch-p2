# Prefixo de execucao Python. Preferencia: `uv run` (resolve no ambiente do
# uv.lock sem exigir venv ativo). Fallback: `.venv/bin/` se existir. Ultimo
# recurso: PATH atual (exige venv ativo). Veja ADR-014 para o racional uv-first.
# Sobrescreva com `PY="uv run "` ou `PY=".venv/bin/"` se quiser forcar.
PY := $(shell \
  if command -v uv >/dev/null 2>&1; then printf 'uv run '; \
  elif [ -x .venv/bin/python ]; then printf '.venv/bin/'; \
  else printf ''; \
  fi)

# Variante com extras da UI (nicegui + httpx + selenium). Usada por targets que rodam
# codigo de `ui/*` direto: `make ui`, `make seed-demo`, e o passo de
# seed-demo dentro de `make reset-db`. Sem o `--extra ui`, fresh venvs
# nao tem nicegui/httpx (sao optional-dependencies em pyproject) e os
# imports explodem com ModuleNotFoundError.
PY_UI := $(shell \
  if command -v uv >/dev/null 2>&1; then printf 'uv run --extra ui '; \
  elif [ -x .venv/bin/python ]; then printf '.venv/bin/'; \
  else printf ''; \
  fi)

# Variante para testes que dependem da UI e de pytest em ambientes fresh.
PY_UI_TEST := $(shell \
  if command -v uv >/dev/null 2>&1; then printf 'uv run --extra test --extra ui '; \
  elif [ -x .venv/bin/python ]; then printf '.venv/bin/'; \
  else printf ''; \
  fi)

# Wrapper do docker compose com --env-file .env.dev. Necessario porque
# `env_file:` no compose so afeta env do container -- nao alimenta a
# interpolacao de ${APP_PORT}/${DB_PORT}/${UI_PORT} em ports:. Para que
# a parametrizacao via .env.dev funcione (worktrees paralelos), o
# `--env-file` precisa estar nas chamadas que sobem stack. Targets que
# nao publicam porta (down, exec, cp) tambem usam o wrapper para manter
# project name consistente e evitar drift entre invocacoes.
DOCKER_COMPOSE := docker compose --env-file .env.dev

.PHONY: lint format typecheck security test test-integ test-all check all up down seed ui seed-users seed-users-docker seed-demo up-backend env-dev rebuild reset-db

# Bootstrap do .env.dev a partir do example. `.env.dev` e gitignored
# porque pode conter secrets reais; o `.env.dev.example` tem defaults
# dev-only seguros para subir a stack local. Se o dev nao tiver o
# arquivo, copiamos automaticamente antes de qualquer `docker compose`
# que dependa dele (ver env_file em docker-compose.yml).
.env.dev: .env.dev.example
	@if [ ! -f .env.dev ]; then \
		cp .env.dev.example .env.dev; \
		echo ">> .env.dev criado a partir de .env.dev.example (dev defaults)."; \
		echo ">> Edite o arquivo antes de promover para qualquer ambiente nao-local."; \
	fi

env-dev: .env.dev

up: .env.dev
	@bash -c 'source scripts/docker-check.sh && bash scripts/kill-stale-ui.sh && $(DOCKER_COMPOSE) up -d'

down: .env.dev
	@bash -c 'source scripts/docker-check.sh && $(DOCKER_COMPOSE) down'

seed:
	@bash -c 'set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; python scripts/seed_admin.py'

lint:
	$(PY)ruff check src/ ui/ tests/
	$(PY)ruff format --check src/ ui/ tests/

format:
	$(PY)ruff format src/ ui/ tests/
	$(PY)ruff check src/ ui/ tests/ --fix

typecheck:
	$(PY)mypy src/ ui/

security:
	$(PY)bandit -r src/ ui/ -c pyproject.toml --severity-level high

test:
	$(PY)pytest tests/unitarios/ -x -q --no-lint --cov=src -m "not lento"

test-integ:
	$(PY)pytest tests/integracao/ -x -q --no-lint --tb=short

test-all:
	$(PY)pytest tests/ -x -q --no-lint -m "not lento"

test-lento:
	$(PY_UI_TEST)pytest tests/ -q --no-lint -m "lento"

check: lint typecheck security test
	@echo "All checks passed"

all: format check test-integ
	@echo "Full pipeline passed"

ui:
	$(PY_UI)python -m ui

seed-users:
	@bash -c 'set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; $(PY)python scripts/seed_usuarios.py'

# seed-users-docker nao depende de o script existir na imagem. Copia o
# `scripts/seed_usuarios.py` do worktree atual pra dentro do container em
# runtime e roda dali. Isso evita que uma imagem stale (buildada antes do
# script existir ou de alteracoes recentes) precise ser rebuilded so para
# popular usuarios de seed. Se a imagem estiver muito stale pra outras
# razoes, rode `make rebuild` separadamente.
# MSYS_NO_PATHCONV=1: no Git Bash (MSYS2) o argumento `/tmp/...` passado
# pra docker.exe (binario Windows nativo) seria traduzido pra um path
# Windows tipo C:/Users/.../Temp/seed_usuarios.py antes de chegar no
# container — o python no container nao acha o arquivo. A flag desliga
# essa traducao so pra esses comandos. No-op em macOS/Linux.
seed-users-docker: .env.dev
	MSYS_NO_PATHCONV=1 $(DOCKER_COMPOSE) cp scripts/seed_usuarios.py app:/tmp/seed_usuarios.py
	MSYS_NO_PATHCONV=1 $(DOCKER_COMPOSE) exec app python /tmp/seed_usuarios.py

# Popula dados de demo (7 clientes, 10 veiculos, 8 servicos, 14 itens, 8 OS
# em 7 estados) via API HTTP do host. Roda com uv local — nao precisa
# container. Precisa do admin seed criado antes (seed-users / seed-users-docker)
# e do backend respondendo em BACKEND_URL (default http://localhost:8000).
# Idempotente: reexecutar nao duplica (chave natural por nome/placa). Usa
# PY_UI porque seed_demo.py importa ui/cliente_api (httpx + nicegui).
seed-demo: .env.dev
	@bash -c 'set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; $(PY_UI)python scripts/seed_demo.py'

# Rebuild forcado: re-build imagens e recria containers. Use quando houver
# mudancas em Dockerfile, pyproject.toml, src/, ou qualquer arquivo que
# entre no build context (ex.: acabei de dar `git pull`).
rebuild: .env.dev
	@bash -c 'source scripts/docker-check.sh && bash scripts/kill-stale-ui.sh && $(DOCKER_COMPOSE) up -d --build --force-recreate'

up-backend: .env.dev
	@bash -c 'source scripts/docker-check.sh && $(DOCKER_COMPOSE) up -d postgres app'

# "Nuke e repopula" — single-command pra voltar pro zero. Faz tudo:
#   1. down -v        (containers + volume postgres_data apagados)
#   2. up -d --build  (rebuild se o codigo mudou; cacheado se nao mudou)
#   3. poll /saude    (aguarda migrations no entrypoint + uvicorn UP)
#   4. seed-users     (admin/atendente/mecanico)
#   5. seed-demo      (7 clientes + 10 veiculos + 8 servicos + 14 itens + 8 OS)
# Use quando:
# - ENCRYPTION_KEY mudou entre restarts e CPFs/CNPJs cifrados ficaram
#   ilegiveis (listar clientes retornava 500 no bug historico).
# - Quer testar em DB limpo, sem residuos da sessao anterior, MAS com dados
#   realistas (nao um banco vazio — o seed-demo popula OS em 7 estados).
# - Quer conferir que migrations novas rodam em DB virgem.
# - Acabou de dar `git pull` e quer garantir que o codigo novo esta rodando
#   com DB limpo (inclui o rebuild — nao precisa rodar `make rebuild` antes).
# Pular demo seed: rode `make reset-db SKIP_DEMO=1` (so cria admin/atendente/
# mecanico). Util quando quer popular manualmente via UI pra testar o fluxo
# de cadastro.
# NAO USAR EM PRODUCAO — perda garantida de dados.
reset-db: .env.dev
	@bash -c 'source scripts/docker-check.sh && \
		echo ">> derrubando stack e apagando volume postgres_data..." && \
		$(DOCKER_COMPOSE) down -v && \
		bash scripts/kill-stale-ui.sh && \
		echo ">> rebuildando imagens e subindo stack do zero..." && \
		$(DOCKER_COMPOSE) up -d --build && \
		echo ">> aguardando /api/v1/saude responder 200..." && \
		APP_PORT_EFFECTIVE=$${APP_PORT:-8000} && \
		UI_PORT_EFFECTIVE=$${UI_PORT:-8080} && \
		for i in $$(seq 1 30); do \
			if curl -fsS http://localhost:$${APP_PORT_EFFECTIVE}/api/v1/saude >/dev/null 2>&1; then \
				echo ">> backend respondendo em $$i tentativa(s)."; break; \
			fi; \
			if [ $$i -eq 30 ]; then \
				echo "!! backend nao respondeu em 60s — verifique docker compose logs app"; \
				exit 1; \
			fi; \
			sleep 2; \
		done && \
		echo ">> populando usuarios seed..." && \
		MSYS_NO_PATHCONV=1 $(DOCKER_COMPOSE) cp scripts/seed_usuarios.py app:/tmp/seed_usuarios.py && \
		MSYS_NO_PATHCONV=1 $(DOCKER_COMPOSE) exec -T app python /tmp/seed_usuarios.py && \
		if [ -z "$(SKIP_DEMO)" ]; then \
			echo ">> populando dados de demo (clientes/OS/catalogo/estoque)..." && \
			set -a && [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a && \
			$(PY_UI)python scripts/seed_demo.py; \
		else \
			echo ">> SKIP_DEMO=1: pulando seed de demo (banco so com usuarios)."; \
		fi && \
		echo ">> pronto. Abra http://localhost:$${UI_PORT_EFFECTIVE}/ e faca login como admin."'

# ---- full-test ----
.PHONY: full-test full-test-up full-test-seed full-test-run full-test-ci full-test-teardown

# PYTHONPATH=full-test: torna o pacote `full_test` importavel via `python -m`
# quando rodado a partir da raiz do repo (pytest ja resolve por conftest).
FULL_TEST_PY := PYTHONPATH=full-test uv run python -m full_test
FULL_TEST_ENV := full-test/.env

$(FULL_TEST_ENV): full-test/.env.example
	@if [ ! -f $(FULL_TEST_ENV) ]; then \
		cp full-test/.env.example $(FULL_TEST_ENV); \
		echo ">> full-test/.env criado a partir de full-test/.env.example."; \
	fi

full-test-up: .env.dev $(FULL_TEST_ENV)
	@echo ">>> docker compose up -d + health-wait"
	$(DOCKER_COMPOSE) up -d
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

full-test-teardown: .env.dev
	@echo ">>> docker compose down + limpa reports"
	$(DOCKER_COMPOSE) down -v
	rm -rf full-test/reports

full-test: full-test-up full-test-seed full-test-run full-test-teardown
