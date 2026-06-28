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

.PHONY: lint lint-arch format typecheck security codeql-quality test test-coverage test-integ test-all check all up down seed ui seed-users seed-users-docker seed-demo up-backend env-dev rebuild reset-db

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
	$(PY)ruff check src/ ui/ relay/ scripts/ tests/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py
	$(PY)ruff format --check src/ ui/ relay/ scripts/ tests/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py

# Contratos de arquitetura (ADR-015 / RNF-017): camadas Clean por contexto +
# proibicao dominio -> infraestrutura. Config em [tool.importlinter] no
# pyproject.toml.
lint-arch:
	$(PY)lint-imports

format:
	$(PY)ruff format src/ ui/ relay/ scripts/ tests/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py
	$(PY)ruff check src/ ui/ relay/ scripts/ tests/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py --fix

typecheck:
	$(PY)mypy src/ ui/ relay/ scripts/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py

security:
	$(PY)bandit -r src/ ui/ relay/ scripts/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py -c pyproject.toml --severity-level high

# DAST local (TD-011; ADR-011): paridade com o job "DAST — OWASP ZAP baseline"
# do .github/workflows/full-test-ci.yml. Sobe a stack compose, aguarda
# /api/v1/saude e roda o MESMO OWASP ZAP baseline contra o OpenAPI vivo, com as
# mesmas regras (.zap/rules.tsv). Sem `-I`: e um gate (os 2 warnings aceitos da
# fase 1 estao como IGNORE nas regras; achado NOVO falha). Relatorios em .zap/
# (gitignorados; nunca tocam os relatorios versionados em docs/seguranca/).
# FORA do agregado `check`: precisa de Docker e e lento. macOS+Colima exige
# `export DOCKER_HOST=unix://$$HOME/.colima/default/docker.sock` antes.
.PHONY: dast
dast: .env.dev
	@bash -c 'source scripts/docker-check.sh && \
		echo ">> subindo stack (app + postgres) para o ZAP baseline..." && \
		$(DOCKER_COMPOSE) up -d && \
		APP_PORT_EFFECTIVE=$${APP_PORT:-8000} && \
		echo ">> aguardando http://localhost:$${APP_PORT_EFFECTIVE}/api/v1/saude responder 200..." && \
		for i in $$(seq 1 60); do \
			if curl -fsS http://localhost:$${APP_PORT_EFFECTIVE}/api/v1/saude >/dev/null 2>&1; then \
				echo ">> backend saudavel em $$i tentativa(s)."; break; \
			fi; \
			if [ $$i -eq 60 ]; then \
				echo "!! backend nao respondeu em 120s — veja docker compose logs app"; exit 1; \
			fi; \
			sleep 2; \
		done && \
		mkdir -p .zap && \
		echo ">> rodando OWASP ZAP baseline contra http://localhost:$${APP_PORT_EFFECTIVE}/openapi.json ..." && \
		docker run --rm --network host \
			-v "$$(pwd)/.zap:/zap/wrk:rw" \
			-t zaproxy/zap-stable zap-baseline.py \
			-t http://localhost:$${APP_PORT_EFFECTIVE}/openapi.json \
			-c rules.tsv \
			-J zap-report.json \
			-r zap-report.html \
			-w zap-report.md; \
		rc=$$?; \
		echo ">> resumo do ZAP (.zap/zap-report.md):"; \
		[ -f .zap/zap-report.md ] && cat .zap/zap-report.md || echo "(sem report — o scan nao chegou a gravar)"; \
		echo ">> relatorios em .zap/zap-report.{json,html,md}. Derrube a stack com '\''make down'\''."; \
		exit $$rc'

# Roda o CodeQL "Code Quality" suite localmente (mesmas queries do GitHub Code
# Quality). On-demand: a 1a execucao baixa o bundle do CodeQL (~1GB); nao entra
# em `check`/CI por ser pesado. Detalhes em scripts/codeql_quality.sh.
codeql-quality:
	@bash scripts/codeql_quality.sh

# Args comuns da suite unitaria, compartilhados por `test` e `test-coverage`.
PYTEST_UNIT_ARGS := tests/unitarios/ -x -q --no-lint --cov=src -m "not lento"

# Usa PY_UI_TEST (extras test+ui): tests/unitarios/ inclui tests/unitarios/ui/,
# cujos imports puxam nicegui/httpx (optional-dependencies do extra `ui`). Sem os
# extras, fresh venvs dao ERROR de coleta nesses arquivos. Espelha o CI, que faz
# `uv sync --extra test --extra ui` antes de rodar a suite.
test:
	$(PY_UI_TEST)pytest $(PYTEST_UNIT_ARGS)

test-coverage:
	$(PY_UI_TEST)pytest $(PYTEST_UNIT_ARGS) --cov-report=term-missing --cov-report=xml:coverage.xml

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
# Fonte unica do SBOM CycloneDX: o job `sbom` do CI roda este mesmo alvo
# (`make sbom`), entao versao do gerador + comandos + validacao vivem so aqui
# (paridade CI<->local por construcao). Artefato gitignorado (muda a cada
# lockfile); o CI o publica como artefato de build.
CYCLONEDX_VERSION ?= 7.3.0
.PHONY: sbom
sbom:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt > sbom-requirements.txt
	uvx --from cyclonedx-bom==$(CYCLONEDX_VERSION) cyclonedx-py requirements sbom-requirements.txt --output-format JSON > sbom.cdx.json
	grep -q '"bomFormat": "CycloneDX"' sbom.cdx.json || { rm -f sbom.cdx.json sbom-requirements.txt; exit 1; }
	@rm -f sbom-requirements.txt
	@echo ">> SBOM CycloneDX gerado em sbom.cdx.json ($$(grep -c '"bom-ref"' sbom.cdx.json) refs)."

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
K8S_APP_IMAGE ?= ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app
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
	@echo ">> migracao via Job dedicado antes do rollout (TD-015)..."
	# Migracao via Job dedicado antes do rollout (TD-015): resolve a corrida com N replicas
	$(KUBECTL) -n $(K8S_NS) delete job pytstop-migrate --ignore-not-found
	sed "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev|$(K8S_TAG)|" k8s/jobs/migration-job.yaml | $(KUBECTL) -n $(K8S_NS) apply -f -
	$(KUBECTL) -n $(K8S_NS) wait --for=condition=complete --timeout=180s job/pytstop-migrate || { echo ">> ERRO: migracao (pytstop-migrate) falhou ou expirou; abortando o deploy antes do rollout."; $(KUBECTL) -n $(K8S_NS) logs job/pytstop-migrate --tail=50 || true; exit 1; }
	$(KUBECTL) -n $(K8S_NS) set image deployment/pytstop-api api=$(K8S_TAG)
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-api --timeout=300s
	$(KUBECTL) -n $(K8S_NS) set image deployment/pytstop-relay relay=$(K8S_TAG)
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-relay --timeout=300s
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
