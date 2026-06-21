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
#
# `GIT_SHA`/`GIT_DATE` sao injetados em toda invocacao do compose pra que
# qualquer build local (`make up`, `make rebuild`, `make reset-db`) embuta
# a SHA do HEAD nas imagens app/ui (via build args) e exponha pro
# entrypoint do postgres (via environment) — todos os 3 servicos logam a
# SHA no startup, batendo com a embutida nas imagens GHCR. SHA e auto-
# computada do git: nunca commitada em arquivo. Fallback "unknown" no
# compose cobre invocacao manual (`docker compose up` sem make).
GIT_SHA  := $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
GIT_DATE := $(shell git show -s --format=%cI HEAD 2>/dev/null || echo unknown)
DOCKER_COMPOSE := GIT_SHA=$(GIT_SHA) GIT_DATE=$(GIT_DATE) docker compose --env-file .env.dev

.PHONY: lint lint-arch format typecheck security test test-coverage test-integ test-all check all up down seed ui seed-users seed-users-docker seed-demo up-backend env-dev rebuild reset-db

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

# Contratos de arquitetura (ADR-015 / RNF-017): camadas Clean por contexto +
# proibicao dominio -> infraestrutura. Config em [tool.importlinter] no
# pyproject.toml.
lint-arch:
	$(PY)lint-imports

format:
	$(PY)ruff format src/ ui/ tests/
	$(PY)ruff check src/ ui/ tests/ --fix

typecheck:
	$(PY)mypy src/ ui/

security:
	$(PY)bandit -r src/ ui/ -c pyproject.toml --severity-level high

test:
	$(PY)pytest tests/unitarios/ -x -q --no-lint --cov=src -m "not lento"

test-coverage:
	$(PY_UI_TEST)pytest tests/unitarios/ -x -q --no-lint --cov=src -m "not lento" --cov-report=term-missing --cov-report=xml:coverage.xml

test-integ:
	$(PY)pytest tests/integracao/ -x -q --no-lint --tb=short

test-all:
	$(PY)pytest tests/ -x -q --no-lint -m "not lento"

test-lento:
	$(PY_UI_TEST)pytest tests/ -q --no-lint -m "lento"

check: lint lint-arch typecheck security test
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

# ---- GHCR (imagens db + app + ui pra fast-check via compose standalone) ----
# Pipeline pra publicar 3 imagens no GitHub Container Registry de uma vez,
# permitindo que examinador rode `db-image/docker-compose.yml` (que puxa
# tudo do GHCR) sem precisar do source. Cada imagem embute SHA do HEAD
# como LABEL OCI + ENV var, e loga no startup pra validacao.
#
# Imagens publicadas (uma versao por package, sem historico — `ghcr-prune`
# limpa orfaos a cada `update-ghcr`):
#   - <prefix>-db   (postgres:16 + dump seedado)         tags: seeded, latest
#   - <prefix>-app  (FastAPI backend)                    tags: latest
#   - <prefix>-ui   (NiceGUI sandbox)                    tags: latest
#
# Variaveis sobrescritiveis (ex.: `make update-ghcr GHCR_USER=fulano`):
GHCR_REGISTRY ?= ghcr.io
GHCR_USER     ?= jbamaral
GHCR_PREFIX   ?= postech-sw-arch-p1
GHCR_DB       := $(GHCR_REGISTRY)/$(GHCR_USER)/$(GHCR_PREFIX)-db
GHCR_APP      := $(GHCR_REGISTRY)/$(GHCR_USER)/$(GHCR_PREFIX)-app
GHCR_UI       := $(GHCR_REGISTRY)/$(GHCR_USER)/$(GHCR_PREFIX)-ui
GHCR_REPOS    := $(GHCR_PREFIX)-db $(GHCR_PREFIX)-app $(GHCR_PREFIX)-ui

.PHONY: ghcr-dump ghcr-build ghcr-push ghcr-prune update-ghcr

# Dump do postgres rodando para `db-image/00-init.sql`. Pre-condicao: stack
# up & seedada (rode `make reset-db` antes ou use `make update-ghcr` que
# encadeia). `--no-owner --no-acl` deixa o dump portavel (qualquer user
# postgres consegue restaurar).
ghcr-dump: .env.dev
	@bash -c 'source scripts/docker-check.sh && \
		set -a && . ./.env.dev && set +a && \
		echo ">> dumping seeded DB to db-image/00-init.sql..." && \
		mkdir -p db-image && \
		$(DOCKER_COMPOSE) exec -T postgres pg_dump \
			-U $${POSTGRES_USER:-pytstop} \
			-d $${POSTGRES_DB:-pytstop} \
			--no-owner --no-acl > db-image/00-init.sql && \
		echo ">> dump done ($$(wc -l < db-image/00-init.sql) lines)"'

# Build das 3 imagens com a mesma SHA/data do HEAD. Build args viram LABELs
# OCI (`org.opencontainers.image.revision`/`.created`) e ENV vars
# (`PYTSTOP_GIT_SHA`/`PYTSTOP_GIT_DATE`) embutidas. Cada container loga a
# SHA no startup (entrypoint do app, CMD wrapper da ui, initdb script da
# db). `--provenance=false --sbom=false`: desliga attestation/SBOM
# manifests pra cada push virar 1 versao no GHCR (sem isso cada push
# criaria 3 manifests, e o prune simples quebraria referencias).
ghcr-build: ghcr-dump
	@echo ">> building 3 images with SHA=$(shell echo $(GIT_SHA) | cut -c1-12) ($(GIT_DATE))"
	docker build --provenance=false --sbom=false \
		--build-arg GIT_SHA=$(GIT_SHA) --build-arg GIT_DATE=$(GIT_DATE) \
		-t $(GHCR_DB):seeded -t $(GHCR_DB):latest db-image/
	docker build --provenance=false --sbom=false \
		--build-arg GIT_SHA=$(GIT_SHA) --build-arg GIT_DATE=$(GIT_DATE) \
		-t $(GHCR_APP):latest .
	docker build --provenance=false --sbom=false \
		--build-arg GIT_SHA=$(GIT_SHA) --build-arg GIT_DATE=$(GIT_DATE) \
		-t $(GHCR_UI):latest -f ui/Dockerfile .

# Push das tags. Pre-condicao: `docker login ghcr.io -u $(GHCR_USER)`
# (PAT com escopo `write:packages`) ja executado nesta sessao.
ghcr-push:
	@for img in $(GHCR_DB):seeded $(GHCR_DB):latest $(GHCR_APP):latest $(GHCR_UI):latest; do \
		if ! docker image inspect $$img >/dev/null 2>&1; then \
			echo "!! imagem $$img nao existe — rode 'make ghcr-build' antes."; exit 1; \
		fi; \
	done
	docker push $(GHCR_DB):seeded
	docker push $(GHCR_DB):latest
	docker push $(GHCR_APP):latest
	docker push $(GHCR_UI):latest
	@echo ">> publicadas: $(GHCR_DB):seeded $(GHCR_APP):latest $(GHCR_UI):latest"

# Apaga versoes "untagged" dos 3 packages GHCR (digests orfaos deixados
# por pushes anteriores que sobrescreveram tags). Mantem apenas as versoes
# tagueadas correntes. Pre-condicao:
#   gh auth refresh -s read:packages,delete:packages
# Requer `jq` no PATH.
#
# `set -e -o pipefail`: garante que falha em qualquer comando do pipe
# (gh api / jq) faz o target falhar visivelmente, em vez de reportar
# ">> prune done." apos um erro silencioso.
#
# API path `/users/$(GHCR_USER)/packages/...`: vincula explicitamente o
# alvo ao GHCR_USER configurado, em vez de `/user/...` (que opera no
# usuario autenticado, podendo divergir em forks). Validacao auth-user
# vs GHCR_USER mantida pra falhar rapido com mensagem amigavel antes
# do primeiro DELETE retornar 403.
#
# `MSYS_NO_PATHCONV=1`: no Git Bash do Windows, MSYS reescreve args que
# parecem path Unix (`/user`, `/users/...`) pra path Windows
# (`C:/Program Files/Git/user`) antes de passar pra `gh.exe` (binario
# nativo Windows). Resultado: `gh api /user` falha com "invalid API
# endpoint: C:/Program Files/Git/user". Setar a env var desliga a
# conversao pra todas as chamadas do bloco. Mesmo padrao ja usado nos
# `docker compose cp/exec` deste Makefile -- ver MEMORY.md "Discovered
# conventions" 2026-04-26.
#
# `tr -d "\r"` no pipe: gh.exe e jq.exe (Windows builds) emitem CRLF
# em stdout. Sem o strip, `read -r id` no while loop captura `<id>\r`,
# que o `gh api` subsequente passa pra URL como `.../versions/<id>%0D`
# e a Go net/url rejeita ("invalid control character in URL").
ghcr-prune:
	@MSYS_NO_PATHCONV=1 bash -c 'set -e -o pipefail; \
		auth_user=$$(gh api /user --jq .login 2>/dev/null); \
		if [ -z "$$auth_user" ]; then \
			echo "!! gh nao esta autenticado. Rode: gh auth login"; exit 1; \
		fi; \
		if [ "$$auth_user" != "$(GHCR_USER)" ]; then \
			echo "!! gh autenticado como $$auth_user, mas GHCR_USER=$(GHCR_USER)."; \
			echo "!! prune opera no usuario autenticado -- alinhe os dois antes (gh auth login -u $(GHCR_USER))."; \
			exit 1; \
		fi; \
		for repo in $(GHCR_REPOS); do \
			echo ">> pruning $$repo..."; \
			gh api /users/$(GHCR_USER)/packages/container/$$repo/versions --paginate \
				| jq -r ".[] | select((.metadata.container.tags // []) | length == 0) | .id" \
				| tr -d "\r" \
				| while read -r id; do \
					[ -z "$$id" ] && continue; \
					gh api -X DELETE /users/$(GHCR_USER)/packages/container/$$repo/versions/$$id >/dev/null \
						&& echo ">>   deleted version id=$$id from $$repo"; \
				done; \
		done; \
		echo ">> prune done."'

# Pipeline completo: rotaciona ENCRYPTION_KEY -> reset-db (DESTRUTIVO --
# dropa volume) -> build das 3 imagens -> push das 4 tags -> patcha
# db-image/docker-compose.yml com a nova key -> prune historico (best-effort).
#
# Por que rotaciona: a key cifra CPF/CNPJ no dump seedado. Rotacionar a
# cada publicacao garante que (1) a key commitada so vale para o snapshot
# atual no GHCR, (2) leak da key historica nao decifra snapshots futuros,
# e (3) o `.env.dev` local fica com key DIFERENTE da committada, evitando
# reuso acidental do valor publico em ambiente nao-demo.
#
# Comportamento:
#   1. Backup da OLD_KEY de .env.dev. Geracao de NEW_KEY (Fernet).
#   2. .env.dev recebe NEW_KEY temporariamente (trap restaura no final).
#   3. reset-db reseed local com NEW_KEY (dump capturara cipher c/ NEW_KEY).
#   4. ghcr-build/push publicam o snapshot.
#   5. db-image/docker-compose.yml e patchado com NEW_KEY -- ANTES do prune,
#      pra garantir contrato consistente compose<->GHCR mesmo se prune falhar.
#      Precisa commit + push manual depois (target imprime os comandos).
#   6. ghcr-prune e BEST-EFFORT (precisa jq + gh com read:packages/delete:packages
#      no PATH/scopes; falha so deixa versoes untagged orphas no GHCR -- inocuo
#      pro fast-check, sao limpaveis depois com `make ghcr-prune`).
#   7. .env.dev e restaurada para OLD_KEY (via trap, mesmo em falha).
#
# Recovery se push parcial: trap printa NEW_KEY full quando o exit status nao
# e 0, pra voce poder patchar compose.yml manualmente se precisar.
#
# Efeito colateral: apos o target, sua DB local fica seedada com NEW_KEY
# mas .env.dev volta pra OLD_KEY -- listar clientes vai falhar localmente
# ate voce rodar `make reset-db` (reseed com OLD_KEY).
#
# Pre-condicoes:
#   - `docker login ghcr.io` (PAT com write:packages) -- HARD requirement
#   - `gh auth refresh -s read:packages,delete:packages` + `jq` no PATH --
#     so pro prune (best-effort). Sem isso pipeline ainda completa, prune skipa.
update-ghcr: .env.dev
	@bash -c 'set -e; \
		echo ">> gerando NEW_KEY rotacionada para esta publicacao..."; \
		NEW_KEY=$$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
		OLD_KEY=$$(grep "^ENCRYPTION_KEY=" .env.dev | cut -d= -f2-); \
		if [ -z "$$OLD_KEY" ]; then \
			echo "!! .env.dev sem ENCRYPTION_KEY -- abort"; exit 1; \
		fi; \
		echo ">> OLD_KEY=$${OLD_KEY:0:8}... NEW_KEY=$${NEW_KEY:0:8}..."; \
		\
		trap "rc=\$$?; sed \"s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$$OLD_KEY|\" .env.dev > .env.dev.tmp && mv .env.dev.tmp .env.dev; echo \">> .env.dev restaurada para OLD_KEY\"; if [ \$$rc -ne 0 ]; then echo \"\"; echo \"!! pipeline FALHOU (rc=\$$rc). NEW_KEY full pra recovery manual:\"; echo \"!! NEW_KEY=$$NEW_KEY\"; echo \"!! Se push das 3 imagens completou, patche db-image/docker-compose.yml manualmente:\"; echo \"!!   sed -i \\\"s|^      ENCRYPTION_KEY:.*|      ENCRYPTION_KEY: $$NEW_KEY|\\\" db-image/docker-compose.yml\"; fi" EXIT; \
		\
		sed "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$$NEW_KEY|" .env.dev > .env.dev.tmp && mv .env.dev.tmp .env.dev; \
		\
		$(MAKE) reset-db; \
		$(MAKE) ghcr-build; \
		$(MAKE) ghcr-push; \
		\
		echo ">> patchando db-image/docker-compose.yml com NEW_KEY (antes do prune pra garantir consistencia)..."; \
		sed "s|^      ENCRYPTION_KEY:.*|      ENCRYPTION_KEY: $$NEW_KEY|" db-image/docker-compose.yml > db-image/docker-compose.yml.tmp && \
			mv db-image/docker-compose.yml.tmp db-image/docker-compose.yml; \
		\
		$(MAKE) ghcr-prune || echo "!! ghcr-prune falhou (best-effort -- imagens publicadas + compose.yml ja consistentes). Cheque jq + gh scopes (read:packages,delete:packages) e rode \"make ghcr-prune\" depois pra limpar versoes untagged."; \
		\
		echo ""; \
		echo "============================================================"; \
		echo ">> 3 imagens atualizadas no GHCR (db/app/ui) com NEW_KEY rotacionada."; \
		echo ">> db-image/docker-compose.yml atualizado -- COMMIT antes de divulgar:"; \
		echo ">>   git add db-image/docker-compose.yml"; \
		echo ">>   git commit -m \"chore(ghcr): rotate ENCRYPTION_KEY for new snapshot\""; \
		echo ">>   git push"; \
		echo ""; \
		echo ">> Local: DB seedada com NEW_KEY, mas .env.dev volta pra OLD_KEY."; \
		echo ">> Pra restaurar consistencia local rode: make reset-db"; \
		echo "============================================================"'

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

# ---- SBOM (TD-012; ADR-012) ----
# Gera o SBOM CycloneDX localmente, igual ao job `sbom` do CI. Artefato
# gitignorado (muda a cada lockfile); o CI publica como artefato de build.
.PHONY: sbom
sbom:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt > sbom-requirements.txt
	uvx --from cyclonedx-bom cyclonedx-py requirements sbom-requirements.txt --output-format JSON > sbom.cdx.json
	@rm -f sbom-requirements.txt
	@echo ">> SBOM gerado em sbom.cdx.json"

# ---- k8s / CD local (RNF-022; ADR-019) ----
# Espelho local do workflow de CD (.github/workflows/cd.yml): o pipeline
# executa o que o desenvolvedor executa (DevOps, Aula 03). Mesmos passos,
# mesma ordem -- terraform apply (cluster kind + postgres), build da imagem
# com tag por SHA, kind load, metrics-server, manifests de k8s/, set image
# e rollout. Diferencas deliberadas vs o runner:
#   - a imagem nao passa pelo GHCR: build local + `kind load` direto
#     (mesmo racional do ADR-019 -- sem PAT pessoal);
#   - todo kubectl usa `--context kind-$(K8S_CLUSTER)` explicito, sem
#     mudar o current-context da sua maquina (o runner e descartavel e
#     usa `kubectl config use-context`).
# A tag repete o SHA do HEAD: alteracoes NAO commitadas reusam a tag e o
# set image vira no-op -- commite, ou force com
# `kubectl --context kind-pytstop -n pytstop rollout restart deployment/pytstop-api`.
# `K8S_CLUSTER` alimenta tambem o `-var cluster_name` do terraform, entao
# `make k8s-up K8S_CLUSTER=foo` cria cluster/contexto proprios (branches
# irmas coexistem -- ver infra/README.md).
K8S_CLUSTER ?= pytstop
K8S_NS      ?= pytstop
K8S_APP_IMAGE ?= $(GHCR_REGISTRY)/$(GHCR_USER)/postech-sw-arch-p2-app
K8S_TAG     = $(K8S_APP_IMAGE):$(GIT_SHA)
KUBECTL     = kubectl --context kind-$(K8S_CLUSTER)
TF_INFRA    = terraform -chdir=infra
METRICS_SERVER_MANIFEST = https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

.PHONY: k8s-up k8s-smoke k8s-down cd-local

k8s-up:
	@echo ">> provisionando cluster kind '$(K8S_CLUSTER)' + postgres via terraform (infra/)..."
	$(TF_INFRA) init -input=false
	$(TF_INFRA) apply -auto-approve -input=false -var cluster_name=$(K8S_CLUSTER)
	@echo ">> build da imagem $(K8S_TAG)..."
	docker build -t $(K8S_TAG) --build-arg GIT_SHA=$(GIT_SHA) --build-arg GIT_DATE=$(GIT_DATE) .
	kind load docker-image $(K8S_TAG) --name $(K8S_CLUSTER)
	@echo ">> instalando metrics-server (pre-requisito do HPA)..."
	$(KUBECTL) apply -f $(METRICS_SERVER_MANIFEST)
	$(KUBECTL) -n kube-system get deployment metrics-server -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q kubelet-insecure-tls || \
		$(KUBECTL) patch deployment metrics-server -n kube-system --type json \
			-p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	@echo ">> aplicando manifests do app (k8s/)..."
	$(KUBECTL) apply -f k8s/namespace.yaml
	$(KUBECTL) apply -f k8s/
	$(KUBECTL) -n $(K8S_NS) set image deployment/pytstop-api api=$(K8S_TAG)
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-api --timeout=300s
	@echo ">> deploy concluido: $(K8S_TAG) no cluster kind-$(K8S_CLUSTER)."

# Porta local 18000 (nao 8000) para nao colidir com a stack compose, que
# publica o app em APP_PORT (default 8000) -- senao o smoke poderia passar
# contra o container do compose em vez do cluster.
k8s-smoke:
	@bash -c 'set -e; \
		$(KUBECTL) -n $(K8S_NS) port-forward svc/pytstop-api 18000:8000 >/dev/null & \
		pf=$$!; \
		trap "kill $$pf 2>/dev/null || true" EXIT; \
		echo ">> smoke: aguardando GET /api/v1/saude responder em 127.0.0.1:18000..."; \
		for i in $$(seq 1 20); do \
			if curl -fsS http://127.0.0.1:18000/api/v1/saude; then \
				echo; echo ">> smoke OK ($$i tentativa(s))."; exit 0; \
			fi; \
			sleep 2; \
		done; \
		echo "!! smoke falhou apos 40s -- ultimos logs do deploy:"; \
		$(KUBECTL) -n $(K8S_NS) logs deploy/pytstop-api --tail=50; \
		exit 1'

k8s-down:
	$(TF_INFRA) destroy -auto-approve -input=false -var cluster_name=$(K8S_CLUSTER)
	@echo ">> cluster kind-$(K8S_CLUSTER) destruido (app, banco e dados inclusos)."

# Ciclo completo do CD em maquina local: provisiona, implanta e valida do
# zero -- o mesmo que o workflow executa na main (roteiro do video).
cd-local: k8s-up k8s-smoke
	@echo ">> cd-local completo: cluster kind-$(K8S_CLUSTER) no ar com a API saudavel."
	@echo ">> derrube com 'make k8s-down' quando terminar."
