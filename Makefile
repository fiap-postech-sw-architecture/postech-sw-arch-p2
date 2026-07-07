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

.PHONY: lint lint-arch format typecheck security codeql-quality test test-coverage test-integ test-all test-lento check all up down ui seed-users seed-users-docker seed-demo up-backend rebuild reset-db

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

up: .env.dev
	@bash -c 'source scripts/docker-check.sh && bash scripts/kill-stale-ui.sh && $(DOCKER_COMPOSE) up -d'

down: .env.dev
	@bash -c 'source scripts/docker-check.sh && $(DOCKER_COMPOSE) down'

# Alvos Python dos gates, em variavel unica (antes eram 6 listas repetidas,
# com drift real CI<->Makefile). PY_PATHS: todo o codigo executavel (app, UI,
# relay, scripts operacionais e o script da skill de entrega) — mypy/bandit.
# PY_PATHS_COM_TESTS acrescenta tests/ — so o ruff lida com a suite.
PY_PATHS := src/ ui/ relay/ scripts/ .claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py
PY_PATHS_COM_TESTS := $(PY_PATHS) tests/

# Gates usam PY_UI_TEST (extras test+ui): em clone fresco sem sync manual,
# `uv run` puro nao teria ruff/mypy/bandit no ambiente (finding devops).
lint:
	$(PY_UI_TEST)ruff check $(PY_PATHS_COM_TESTS)
	$(PY_UI_TEST)ruff format --check $(PY_PATHS_COM_TESTS)

# Contratos de arquitetura (ADR-015 / RNF-017): camadas Clean por contexto +
# proibicao dominio -> infraestrutura. Config em [tool.importlinter] no
# pyproject.toml.
lint-arch:
	$(PY_UI_TEST)lint-imports

format:
	$(PY_UI_TEST)ruff format $(PY_PATHS_COM_TESTS)
	$(PY_UI_TEST)ruff check $(PY_PATHS_COM_TESTS) --fix

typecheck:
	$(PY_UI_TEST)mypy $(PY_PATHS)

security:
	$(PY_UI_TEST)bandit -r $(PY_PATHS) -c pyproject.toml --severity-level high

# DAST local (TD-011; ADR-011): paridade com o job "DAST — OWASP ZAP baseline"
# do .github/workflows/full-test-ci.yml. Sobe a stack compose, aguarda
# /api/v1/saude e roda o MESMO OWASP ZAP baseline contra o OpenAPI vivo, com as
# mesmas regras (.zap/rules.tsv). Sem `-I`: e um gate (os 2 warnings aceitos da
# fase 1 estao como IGNORE nas regras; achado NOVO falha). Relatorios em .zap/
# (gitignorados; nunca tocam os relatorios versionados em docs/seguranca/).
# FORA do agregado `check`: precisa de Docker e e lento. macOS+Colima exige
# `export DOCKER_HOST=unix://$$HOME/.colima/default/docker.sock` antes.
# APP_PORT vem de .env/.env.dev (worktrees paralelos): o recipe sourceia os
# arquivos antes de calcular APP_PORT_EFFECTIVE (idioma de seed-users/seed-demo)
# — senao o ZAP miraria a 8000 default mesmo com a stack publicada em outra porta.
.PHONY: dast
dast: .env.dev
	@bash -c 'source scripts/docker-check.sh && \
		echo ">> subindo stack (app + postgres) para o ZAP baseline..." && \
		$(DOCKER_COMPOSE) up -d && \
		{ set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; } && \
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
PYTEST_UNIT_ARGS := tests/unitarios/ -x -q --cov=src -m "not lento"

# Usa PY_UI_TEST (extras test+ui): tests/unitarios/ inclui tests/unitarios/ui/,
# cujos imports puxam nicegui/httpx (optional-dependencies do extra `ui`). Sem os
# extras, fresh venvs dao ERROR de coleta nesses arquivos. Espelha o CI, que faz
# `uv sync --extra test --extra ui` antes de rodar a suite.
test:
	$(PY_UI_TEST)pytest $(PYTEST_UNIT_ARGS)

test-coverage:
	$(PY_UI_TEST)pytest $(PYTEST_UNIT_ARGS) --cov-report=term-missing --cov-report=xml:coverage.xml

test-integ:
	$(PY)pytest tests/integracao/ -x -q --tb=short

test-all:
	$(PY)pytest tests/ -x -q -m "not lento"

test-lento:
	$(PY_UI_TEST)pytest tests/ -q -m "lento"

check: lint lint-arch typecheck security test
	@echo "All checks passed"

# `codeql-quality` entra no pipeline completo (não no `check` do inner-loop, por
# ser pesado): é o SAST autoritativo do repo. O default setup do CodeQL no
# GitHub NÃO aplica os filtros do .github/codeql/codeql-config.yml nem as
# supressões `# codeql[...]`, então lá aparecem warnings que não dá pra desligar;
# a política local (scripts/codeql_quality.py) trata os FPs e é o gate real.
all: format check test-integ codeql-quality
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
		{ set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; } && \
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

# Encadeado via $(MAKE) no recipe, NAO via lista de pre-requisitos: sob
# `make -j` os pre-requisitos rodam em paralelo e o teardown (que nao
# depende do run) podia derrubar a stack no meio dos testes. Linhas de
# recipe sao sequenciais por construcao; full-test-run ja puxa up+seed pela
# cadeia linear de dependencias (que o -j respeita).
full-test:
	$(MAKE) full-test-run
	$(MAKE) full-test-teardown

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
# com tag por SHA, kind load, metrics-server, manifests de k8s/ aplicados
# ja com a tag do SHA (sed, mesmo padrao do Job de migracao) e rollout.
# Diferencas deliberadas vs o runner:
#   - a imagem nao passa pelo GHCR: build local + `kind load` direto
#     (mesmo racional do ADR-019 -- sem PAT pessoal);
#   - todo kubectl usa `--context kind-$(K8S_CLUSTER)` explicito, sem
#     mudar o current-context da sua maquina (o runner e descartavel e
#     usa `kubectl config use-context`).
# A tag repete o SHA do HEAD: alteracoes NAO commitadas reusam a tag e o
# apply nao gera rollout novo -- commite, ou force com
# `kubectl --context kind-pytstop -n pytstop rollout restart deployment/pytstop-api`.
# `K8S_CLUSTER` alimenta tambem o `-var cluster_name` do terraform, entao
# `make k8s-up K8S_CLUSTER=foo` cria cluster/contexto proprios (branches
# irmas coexistem -- ver infra/README.md).
K8S_CLUSTER ?= pytstop
K8S_NS      ?= pytstop
K8S_APP_IMAGE ?= ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app
K8S_TAG     = $(K8S_APP_IMAGE):$(GIT_SHA)
K8S_UI_IMAGE ?= ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-ui
K8S_UI_TAG  = $(K8S_UI_IMAGE):$(GIT_SHA)
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
	@echo ">> build da imagem da UI $(K8S_UI_TAG)..."
	docker build -f ui/Dockerfile -t $(K8S_UI_TAG) --build-arg GIT_SHA=$(GIT_SHA) --build-arg GIT_DATE=$(GIT_DATE) .
	kind load docker-image $(K8S_UI_TAG) --name $(K8S_CLUSTER)
	@echo ">> instalando metrics-server (pre-requisito do HPA)..."
	$(KUBECTL) apply -f $(METRICS_SERVER_MANIFEST)
	$(KUBECTL) -n kube-system get deployment metrics-server -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q kubelet-insecure-tls || \
		$(KUBECTL) patch deployment metrics-server -n kube-system --type json \
			-p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	@echo ">> aplicando manifests do app (k8s/) com a tag $(K8S_TAG)..."
	$(KUBECTL) apply -f k8s/namespace.yaml
	# Ordem obrigatoria (ADR-019: schema em head antes de qualquer replica
	# subir). ESTE BLOCO E ESPELHADO no step "Deploy app manifests" do
	# .github/workflows/cd.yml -- altere os dois juntos.
	# (a) Apoio primeiro: tudo MENOS deployment.yaml/relay.yaml (as cargas da
	# app, que so podem subir depois da migracao). Tag do SHA desde o primeiro
	# apply (mesmo sed do Job): deployment/relay nunca passam pela tag `dev`,
	# dispensando o antigo `kubectl set image`. O glob nao desce em k8s/jobs/.
	# O ui-deployment.yaml (grupo de apoio: nao depende da migracao) tambem tem
	# a tag `dev`, com sufixo -ui -- o sed troca as duas tags de uma vez.
	for f in k8s/*.yaml; do \
		case "$$f" in k8s/deployment.yaml|k8s/relay.yaml) continue ;; esac; \
		sed -e "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev|$(K8S_TAG)|" \
			-e "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-ui:dev|$(K8S_UI_TAG)|" "$$f" \
			| $(KUBECTL) apply -f - || exit 1; \
	done
	@echo ">> migracao via Job dedicado antes do rollout (TD-015)..."
	# (b) Migracao via Job dedicado antes do rollout (TD-015): resolve a corrida com N replicas
	$(KUBECTL) -n $(K8S_NS) delete job pytstop-migrate --ignore-not-found
	sed "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev|$(K8S_TAG)|" k8s/jobs/migration-job.yaml | $(KUBECTL) -n $(K8S_NS) apply -f -
	# Espera com falha rapida (espelha o cd.yml): watchers de `complete` e
	# `failed` em paralelo; o primeiro a resolver encerra a espera — um Job
	# que esgota o backoffLimit aborta em segundos, sem segurar os 180s do
	# timeout do `complete`. O arbitro do desfecho e o status real do Job.
	# Poll `kill -0` no lugar do `wait -n` do cd.yml: /bin/sh (dash) e o
	# bash 3.2 do macOS nao tem `wait -n`.
	@$(KUBECTL) -n $(K8S_NS) wait --for=condition=complete --timeout=180s job/pytstop-migrate & ok=$$!; \
	$(KUBECTL) -n $(K8S_NS) wait --for=condition=failed --timeout=180s job/pytstop-migrate 2>/dev/null & bad=$$!; \
	while kill -0 $$ok 2>/dev/null && kill -0 $$bad 2>/dev/null; do sleep 1; done; \
	kill $$ok $$bad 2>/dev/null; \
	if [ "$$($(KUBECTL) -n $(K8S_NS) get job pytstop-migrate -o jsonpath='{.status.succeeded}')" != "1" ]; then \
		echo ">> ERRO: migracao (pytstop-migrate) falhou ou expirou; abortando o deploy antes do rollout."; \
		$(KUBECTL) -n $(K8S_NS) logs job/pytstop-migrate --tail=50 || true; \
		exit 1; \
	fi
	# (c) So agora as cargas da app: schema ja esta em head.
	@echo ">> aplicando deployment.yaml e relay.yaml (schema ja em head)..."
	for f in k8s/deployment.yaml k8s/relay.yaml; do \
		sed "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev|$(K8S_TAG)|" "$$f" | $(KUBECTL) apply -f - || exit 1; \
	done
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-api --timeout=300s
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-relay --timeout=300s
	# A UI e a superficie de demo: aguarda o rollout dela tambem (espelha o cd.yml).
	$(KUBECTL) -n $(K8S_NS) rollout status deployment/pytstop-ui --timeout=300s
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

# ---- Ambiente cloud de demonstracao — AKS (ADR-025; issue #188) ----
# Alvo OPCIONAL e ADITIVO ao kind: da uma URL publica para a banca durante
# julho. `infra/azure-aks/` provisiona o cluster; o overlay `k8s/overlays/cloud/`
# aplica postgres + app com ENVIRONMENT=production (guard de segredos ATIVO)
# e a UI exposta por LoadBalancer (unica superficie publica; API ClusterIP).
# As imagens vem do GHCR (publicas) pela tag do SHA que o CD ja buildou
# (amd64) -- buildar amd64 no Mac (arm64) seria lento; reusamos o artefato.
# Pre-requisito: `az login` na conta Azure for Students. O estado do
# terraform e' local (uma maquina); o CD por OIDC (evolucao) usa backend remoto.
AZ_RESOURCE_GROUP ?= rg-pytstop-demo
AZ_CLOUD_CLUSTER  ?= pytstop-demo
AZ_LOCATION       ?= brazilsouth
# Node: B2als_v2 (2 vCPU/4 GB) cabe UI+API+relay+redis+postgres+jaeger+
# prometheus sob carga de demo. Se algum pod for OOMKilled, suba para
# Standard_B2ms (8 GB, ~2x o custo): `make cloud-aks-up AZ_NODE_SIZE=Standard_B2ms`.
AZ_NODE_SIZE      ?= Standard_B2als_v2
CLOUD_NS           = pytstop
CLOUD_ENV_FILE    ?= .env.cloud
TF_AZURE           = terraform -chdir=infra/azure-aks
CLOUD_KUBECTL      = kubectl --context $(AZ_CLOUD_CLUSTER)

.PHONY: cloud-aks-up cloud-aks-down cloud-aks-url cloud-aks-seed

cloud-aks-up:
	@command -v az >/dev/null 2>&1 || { echo ">> ERRO: Azure CLI (az) nao instalado (brew install azure-cli)."; exit 1; }
	@az account show >/dev/null 2>&1 || { echo ">> ERRO: nao logado no Azure. Rode 'az login'."; exit 1; }
	@echo ">> [pre] verificando imagens no GHCR (tag $(GIT_SHA))..."
	@docker manifest inspect $(K8S_TAG) >/dev/null 2>&1 || { \
		echo ">> ERRO: imagem $(K8S_TAG) nao esta no GHCR."; \
		echo ">>       o CD a publica em push na main; rode num commit ja buildado e"; \
		echo ">>       confirme que os packages -app/-ui estao PUBLICOS no GHCR."; exit 1; }
	@docker manifest inspect $(K8S_UI_TAG) >/dev/null 2>&1 || { echo ">> ERRO: imagem $(K8S_UI_TAG) nao esta no GHCR."; exit 1; }
	@echo ">> [1/7] provisionando AKS (terraform infra/azure-aks)..."
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZURE) init -input=false
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZURE) apply -auto-approve -input=false \
		-var resource_group_name=$(AZ_RESOURCE_GROUP) -var cluster_name=$(AZ_CLOUD_CLUSTER) \
		-var location=$(AZ_LOCATION) -var node_size=$(AZ_NODE_SIZE)
	@echo ">> [2/7] kubeconfig (az aks get-credentials)..."
	az aks get-credentials --resource-group $(AZ_RESOURCE_GROUP) --name $(AZ_CLOUD_CLUSTER) --overwrite-existing
	@echo ">> [3/7] segredos reais ($(CLOUD_ENV_FILE)) -> Secrets do cluster..."
	bash scripts/cloud-secrets.sh $(CLOUD_ENV_FILE)
	@set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	$(CLOUD_KUBECTL) create namespace $(CLOUD_NS) --dry-run=client -o yaml | $(CLOUD_KUBECTL) apply -f -; \
	$(CLOUD_KUBECTL) create namespace pytstop-infra --dry-run=client -o yaml | $(CLOUD_KUBECTL) apply -f -; \
	$(CLOUD_KUBECTL) -n pytstop-infra create secret generic postgres-credentials \
		--from-literal=POSTGRES_DB=pytstop --from-literal=POSTGRES_USER=pytstop \
		--from-literal=POSTGRES_PASSWORD="$$POSTGRES_PASSWORD" \
		--dry-run=client -o yaml | $(CLOUD_KUBECTL) apply -f -; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) create secret generic pytstop-secrets \
		--from-literal=JWT_SECRET="$$JWT_SECRET" \
		--from-literal=ENCRYPTION_KEY="$$ENCRYPTION_KEY" \
		--from-literal=DATABASE_URL="postgresql://pytstop:$$POSTGRES_PASSWORD@postgres.pytstop-infra.svc.cluster.local:5432/pytstop" \
		--from-literal=ADMIN_EMAIL="$$ADMIN_EMAIL" --from-literal=ADMIN_PASSWORD="$$ADMIN_PASSWORD" \
		--from-literal=ORCAMENTO_WEBHOOK_TOKEN="$$ORCAMENTO_WEBHOOK_TOKEN" \
		--dry-run=client -o yaml | $(CLOUD_KUBECTL) apply -f -; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) create secret generic pytstop-ui-secrets \
		--from-literal=UI_SENHA_ATENDENTE="$$ATENDENTE_PASSWORD" \
		--from-literal=UI_SENHA_MECANICO="$$MECANICO_PASSWORD" \
		--dry-run=client -o yaml | $(CLOUD_KUBECTL) apply -f -
	@echo ">> [4/7] overlay (apoio + config + postgres + UI) com tag $(GIT_SHA)..."
	kubectl kustomize --load-restrictor=LoadRestrictionsNone k8s/overlays/cloud | \
		sed -e "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" -e "s|$(K8S_UI_IMAGE):dev|$(K8S_UI_TAG)|" | \
		$(CLOUD_KUBECTL) apply -f -
	@echo ">> [5/7] Job de migracao antes do rollout..."
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) delete job pytstop-migrate --ignore-not-found
	sed "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" k8s/jobs/migration-job.yaml | $(CLOUD_KUBECTL) -n $(CLOUD_NS) apply -f -
	@$(CLOUD_KUBECTL) -n $(CLOUD_NS) wait --for=condition=complete --timeout=300s job/pytstop-migrate & ok=$$!; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) wait --for=condition=failed --timeout=300s job/pytstop-migrate 2>/dev/null & bad=$$!; \
	while kill -0 $$ok 2>/dev/null && kill -0 $$bad 2>/dev/null; do sleep 2; done; \
	kill $$ok $$bad 2>/dev/null; \
	if [ "$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get job pytstop-migrate -o jsonpath='{.status.succeeded}')" != "1" ]; then \
		echo ">> ERRO: migracao falhou/expirou; abortando o deploy."; \
		$(CLOUD_KUBECTL) -n $(CLOUD_NS) logs job/pytstop-migrate --tail=50 || true; exit 1; fi
	@echo ">> [6/7] cargas da app (deployment + relay, schema ja em head)..."
	for f in k8s/deployment.yaml k8s/relay.yaml; do \
		sed "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" "$$f" | $(CLOUD_KUBECTL) apply -f - || exit 1; \
	done
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-api --timeout=300s
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-relay --timeout=300s
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-ui --timeout=300s
	@echo ">> usuarios atendente/mecanico com senha forte (ADR-025 adendo)..."
	-@set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	POD=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get pod -l app=pytstop-api -o jsonpath='{.items[0].metadata.name}'); \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) cp scripts/seed_usuarios.py $$POD:/tmp/seed_usuarios.py; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) exec $$POD -- env SEED_PAPEIS=ATENDENTE,MECANICO \
		SEED_SENHA_ATENDENTE="$$ATENDENTE_PASSWORD" SEED_SENHA_MECANICO="$$MECANICO_PASSWORD" \
		python /tmp/seed_usuarios.py
	@echo ">> [7/7] IPs publicos + CORS + dados de demo..."
	@$(MAKE) cloud-aks-url
	-@$(MAKE) cloud-aks-seed

# Descobre os IPs dos 4 LoadBalancers (UI, API, Jaeger, Prometheus), ajusta o
# CORS_ORIGINS para a URL da UI e imprime os acessos da banca. Idempotente:
# rode de novo se algum LB ainda nao tinha IP.
cloud-aks-url:
	@set -e; \
	echo ">> aguardando IPs dos 4 LoadBalancers (pode levar 1-3 min)..."; \
	UI_IP=""; API_IP=""; JAEGER_IP=""; PROM_IP=""; \
	for i in $$(seq 1 30); do \
		UI_IP=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get svc pytstop-ui -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true); \
		API_IP=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get svc pytstop-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true); \
		JAEGER_IP=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get svc jaeger -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true); \
		PROM_IP=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get svc prometheus -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true); \
		[ -n "$$UI_IP" ] && [ -n "$$API_IP" ] && [ -n "$$JAEGER_IP" ] && [ -n "$$PROM_IP" ] && break; \
		echo "   ... ($$i/30) UI=$$UI_IP API=$$API_IP JAEGER=$$JAEGER_IP PROM=$$PROM_IP"; sleep 10; \
	done; \
	if [ -z "$$UI_IP" ]; then echo ">> LBs ainda sem IP; rode 'make cloud-aks-url' de novo em ~1 min."; exit 1; fi; \
	echo ">> CORS_ORIGINS=http://$$UI_IP:8080 + restart da API..."; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) patch configmap pytstop-config --type merge -p "{\"data\":{\"CORS_ORIGINS\":\"http://$$UI_IP:8080\"}}"; \
	$(CLOUD_KUBECTL) -n $(CLOUD_NS) rollout restart deployment/pytstop-api >/dev/null; \
	echo ""; \
	echo "==================== ACESSOS DA BANCA ===================="; \
	echo "  UI (app)      http://$$UI_IP:8080"; \
	echo "  API (Postman) http://$$API_IP:8000"; \
	echo "  Jaeger        http://$$JAEGER_IP:16686"; \
	echo "  Prometheus    http://$$PROM_IP:9090"; \
	echo "========================================================="; \
	echo ">> preencha CLOUD-URL-FASE-2 (doc de entrega + README) com http://$$UI_IP:8080"

# Popula dados de demo (clientes, veiculos, catalogo, estoque, OS em varios
# estados) na nuvem, via a API publica, logando com o admin FORTE do
# .env.cloud (seed_demo aceita ADMIN_EMAIL/ADMIN_PASSWORD do ambiente).
# Best-effort no cloud-aks-up; rode manualmente se quiser repovoar.
cloud-aks-seed:
	@[ -f $(CLOUD_ENV_FILE) ] || { echo ">> ERRO: $(CLOUD_ENV_FILE) ausente; rode 'make cloud-aks-up' antes."; exit 1; }
	@API_IP=$$($(CLOUD_KUBECTL) -n $(CLOUD_NS) get svc pytstop-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true); \
	if [ -z "$$API_IP" ]; then echo ">> API sem IP publico ainda; rode 'make cloud-aks-url' e tente de novo."; exit 1; fi; \
	echo ">> populando dados de demo via http://$$API_IP:8000 ..."; \
	set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	BACKEND_URL="http://$$API_IP:8000" $(PY_UI)python scripts/seed_demo.py

# Destroi TUDO (cluster + node + LoadBalancer + IP + disco) -> custo zero. O
# delete do namespace do banco antes libera o PVC/disco; o destroy do cluster
# remove o resource group gerenciado (MC_*) com o resto.
cloud-aks-down:
	@command -v az >/dev/null 2>&1 || { echo ">> ERRO: Azure CLI (az) nao instalado."; exit 1; }
	-az aks get-credentials --resource-group $(AZ_RESOURCE_GROUP) --name $(AZ_CLOUD_CLUSTER) --overwrite-existing 2>/dev/null
	-$(CLOUD_KUBECTL) delete namespace pytstop-infra --wait=false 2>/dev/null
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZURE) destroy -auto-approve -input=false \
		-var resource_group_name=$(AZ_RESOURCE_GROUP) -var cluster_name=$(AZ_CLOUD_CLUSTER) -var location=$(AZ_LOCATION)
	@echo ">> ambiente cloud destruido (cluster + node + LB/IP + disco). Custo -> zero."

# ---- Ambiente de demonstracao em VM + k3s (adendo do ADR-025) ----
# Veiculo da demo publica enquanto o AKS esta bloqueado na conta de estudante
# (system pool exige SKU v5-v7, quota zero, pedido negado). Uma VM D2s_v3
# SPOT (~US$0,019/h) roda k3s e recebe o overlay vm-k3s (que herda o cloud
# inteiro). Klipper-lb binda as 4 superficies no MESMO IP publico:
# UI :8080, API :8000, Jaeger :16686, Prometheus :9090.
# SPOT=false troca para on-demand (janela critica da banca) SEM mudar o IP —
# o IP publico e' recurso separado no Terraform e sobrevive ao recreate.
VM_RG        ?= rg-pytstop-vm
VM_LOCATION  ?= northcentralus
VM_SIZE      ?= Standard_D2s_v3
SPOT         ?= true
VM_SSH_KEY    = .vm-demo-ssh
VM_KUBECONF   = .kube-vm-config
TF_AZVM       = terraform -chdir=infra/azure-vm
VM_KUBECTL    = kubectl --kubeconfig $(VM_KUBECONF)

.PHONY: vm-up vm-down vm-url vm-seed

vm-up:
	@command -v az >/dev/null 2>&1 || { echo ">> ERRO: Azure CLI (az) nao instalado (brew install azure-cli)."; exit 1; }
	@az account show >/dev/null 2>&1 || { echo ">> ERRO: nao logado no Azure. Rode 'az login'."; exit 1; }
	@echo ">> [pre] verificando imagens no GHCR (tag $(GIT_SHA))..."
	@docker manifest inspect $(K8S_TAG) >/dev/null 2>&1 || { echo ">> ERRO: imagem $(K8S_TAG) nao esta no GHCR (CD publica no push da main; packages publicos)."; exit 1; }
	@docker manifest inspect $(K8S_UI_TAG) >/dev/null 2>&1 || { echo ">> ERRO: imagem $(K8S_UI_TAG) nao esta no GHCR."; exit 1; }
	@[ -f $(VM_SSH_KEY) ] || { echo ">> gerando chave SSH dedicada ($(VM_SSH_KEY), git-ignored)..."; ssh-keygen -t ed25519 -f $(VM_SSH_KEY) -N "" -C pytstop-vm-demo >/dev/null; }
	@echo ">> [1/7] provisionando VM $(VM_SIZE) (spot=$(SPOT)) em $(VM_LOCATION)..."
	@MY_IP=$$(curl -fsS https://ifconfig.me 2>/dev/null || curl -fsS https://api.ipify.org); \
	[ -n "$$MY_IP" ] || { echo ">> ERRO: nao consegui descobrir seu IP publico (SSH do NSG)."; exit 1; }; \
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZVM) init -input=false >/dev/null; \
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZVM) apply -auto-approve -input=false \
		-var resource_group_name=$(VM_RG) -var location=$(VM_LOCATION) -var vm_size=$(VM_SIZE) \
		-var spot=$(SPOT) -var ssh_allowed_cidr="$$MY_IP/32" \
		-var admin_ssh_pubkey="$$(cat $(VM_SSH_KEY).pub)"
	@echo ">> [2/7] aguardando SSH + k3s subirem na VM..."
	@PUBIP=$$($(TF_AZVM) output -raw public_ip); \
	for i in $$(seq 1 60); do \
		if ssh -i $(VM_SSH_KEY) -o UserKnownHostsFile=.vm-demo-known_hosts -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 pytstop@$$PUBIP 'sudo test -f /etc/rancher/k3s/k3s.yaml' 2>/dev/null; then \
			echo ">> k3s pronto ($$i tentativa/s)."; break; fi; \
		[ $$i -eq 60 ] && { echo ">> ERRO: k3s nao subiu em 5 min; veja cloud-init na VM (ssh -i $(VM_SSH_KEY) pytstop@$$PUBIP)."; exit 1; }; \
		sleep 5; done
	@echo ">> [3/7] exportando kubeconfig ($(VM_KUBECONF), git-ignored)..."
	@PUBIP=$$($(TF_AZVM) output -raw public_ip); \
	ssh -i $(VM_SSH_KEY) -o UserKnownHostsFile=.vm-demo-known_hosts -o StrictHostKeyChecking=accept-new pytstop@$$PUBIP 'sudo cat /etc/rancher/k3s/k3s.yaml' \
		| sed "s/127.0.0.1/$$PUBIP/" > $(VM_KUBECONF); \
	chmod 600 $(VM_KUBECONF); \
	$(VM_KUBECTL) get nodes
	@echo ">> [4/7] segredos reais ($(CLOUD_ENV_FILE)) -> Secrets do cluster..."
	bash scripts/cloud-secrets.sh $(CLOUD_ENV_FILE)
	@set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	$(VM_KUBECTL) create namespace $(CLOUD_NS) --dry-run=client -o yaml | $(VM_KUBECTL) apply -f -; \
	$(VM_KUBECTL) create namespace pytstop-infra --dry-run=client -o yaml | $(VM_KUBECTL) apply -f -; \
	$(VM_KUBECTL) -n pytstop-infra create secret generic postgres-credentials \
		--from-literal=POSTGRES_DB=pytstop --from-literal=POSTGRES_USER=pytstop \
		--from-literal=POSTGRES_PASSWORD="$$POSTGRES_PASSWORD" \
		--dry-run=client -o yaml | $(VM_KUBECTL) apply -f -; \
	$(VM_KUBECTL) -n $(CLOUD_NS) create secret generic pytstop-secrets \
		--from-literal=JWT_SECRET="$$JWT_SECRET" \
		--from-literal=ENCRYPTION_KEY="$$ENCRYPTION_KEY" \
		--from-literal=DATABASE_URL="postgresql://pytstop:$$POSTGRES_PASSWORD@postgres.pytstop-infra.svc.cluster.local:5432/pytstop" \
		--from-literal=ADMIN_EMAIL="$$ADMIN_EMAIL" --from-literal=ADMIN_PASSWORD="$$ADMIN_PASSWORD" \
		--from-literal=ORCAMENTO_WEBHOOK_TOKEN="$$ORCAMENTO_WEBHOOK_TOKEN" \
		--dry-run=client -o yaml | $(VM_KUBECTL) apply -f -; \
	$(VM_KUBECTL) -n $(CLOUD_NS) create secret generic pytstop-ui-secrets \
		--from-literal=UI_SENHA_ATENDENTE="$$ATENDENTE_PASSWORD" \
		--from-literal=UI_SENHA_MECANICO="$$MECANICO_PASSWORD" \
		--dry-run=client -o yaml | $(VM_KUBECTL) apply -f -
	@echo ">> [5/7] overlay vm-k3s (apoio + config + postgres + UI + observabilidade)..."
	kubectl kustomize --load-restrictor=LoadRestrictionsNone k8s/overlays/vm-k3s | \
		sed -e "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" -e "s|$(K8S_UI_IMAGE):dev|$(K8S_UI_TAG)|" | \
		$(VM_KUBECTL) apply -f -
	@echo ">> [6/7] Job de migracao antes do rollout..."
	$(VM_KUBECTL) -n $(CLOUD_NS) delete job pytstop-migrate --ignore-not-found
	sed "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" k8s/jobs/migration-job.yaml | $(VM_KUBECTL) -n $(CLOUD_NS) apply -f -
	@$(VM_KUBECTL) -n $(CLOUD_NS) wait --for=condition=complete --timeout=300s job/pytstop-migrate & ok=$$!; \
	$(VM_KUBECTL) -n $(CLOUD_NS) wait --for=condition=failed --timeout=300s job/pytstop-migrate 2>/dev/null & bad=$$!; \
	while kill -0 $$ok 2>/dev/null && kill -0 $$bad 2>/dev/null; do sleep 2; done; \
	kill $$ok $$bad 2>/dev/null; \
	if [ "$$($(VM_KUBECTL) -n $(CLOUD_NS) get job pytstop-migrate -o jsonpath='{.status.succeeded}')" != "1" ]; then \
		echo ">> ERRO: migracao falhou/expirou; abortando o deploy."; \
		$(VM_KUBECTL) -n $(CLOUD_NS) logs job/pytstop-migrate --tail=50 || true; exit 1; fi
	@echo ">> [7/7] cargas da app (deployment + relay) + URL + seed..."
	for f in k8s/deployment.yaml k8s/relay.yaml; do \
		sed "s|$(K8S_APP_IMAGE):dev|$(K8S_TAG)|" "$$f" | $(VM_KUBECTL) apply -f - || exit 1; \
	done
	$(VM_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-api --timeout=300s
	$(VM_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-relay --timeout=300s
	$(VM_KUBECTL) -n $(CLOUD_NS) rollout status deployment/pytstop-ui --timeout=300s
	@echo ">> usuarios atendente/mecanico com senha forte (ADR-025 adendo)..."
	-@set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	POD=$$($(VM_KUBECTL) -n $(CLOUD_NS) get pod -l app=pytstop-api -o jsonpath='{.items[0].metadata.name}'); \
	$(VM_KUBECTL) -n $(CLOUD_NS) cp scripts/seed_usuarios.py $$POD:/tmp/seed_usuarios.py; \
	$(VM_KUBECTL) -n $(CLOUD_NS) exec $$POD -- env SEED_PAPEIS=ATENDENTE,MECANICO \
		SEED_SENHA_ATENDENTE="$$ATENDENTE_PASSWORD" SEED_SENHA_MECANICO="$$MECANICO_PASSWORD" \
		python /tmp/seed_usuarios.py
	@$(MAKE) vm-url
	-@$(MAKE) vm-seed

# Imprime os acessos (mesmo IP, 4 portas) e ajusta o CORS para a UI.
vm-url:
	@PUBIP=$$($(TF_AZVM) output -raw public_ip); \
	echo ">> CORS_ORIGINS=http://$$PUBIP:8080 + restart da API..."; \
	$(VM_KUBECTL) -n $(CLOUD_NS) patch configmap pytstop-config --type merge -p "{\"data\":{\"CORS_ORIGINS\":\"http://$$PUBIP:8080\"}}" >/dev/null; \
	$(VM_KUBECTL) -n $(CLOUD_NS) rollout restart deployment/pytstop-api >/dev/null; \
	echo ""; \
	echo "==================== ACESSOS DA BANCA ===================="; \
	echo "  UI (app)      http://$$PUBIP:8080"; \
	echo "  API (Postman) http://$$PUBIP:8000"; \
	echo "  Jaeger        http://$$PUBIP:16686"; \
	echo "  Prometheus    http://$$PUBIP:9090"; \
	echo "========================================================="; \
	echo ">> preencha CLOUD-URL-FASE-2 (doc de entrega + README) com http://$$PUBIP:8080"

# Dados de demo via API publica da VM, com o admin FORTE do .env.cloud.
vm-seed:
	@[ -f $(CLOUD_ENV_FILE) ] || { echo ">> ERRO: $(CLOUD_ENV_FILE) ausente; rode 'make vm-up' antes."; exit 1; }
	@PUBIP=$$($(TF_AZVM) output -raw public_ip); \
	echo ">> populando dados de demo via http://$$PUBIP:8000 ..."; \
	set -a; . ./$(CLOUD_ENV_FILE); set +a; \
	BACKEND_URL="http://$$PUBIP:8000" $(PY_UI)python scripts/seed_demo.py

# Destroi a VM inteira (RG + IP + disco) -> custo zero.
vm-down:
	@command -v az >/dev/null 2>&1 || { echo ">> ERRO: Azure CLI (az) nao instalado."; exit 1; }
	# admin_ssh_pubkey precisa ser uma chave SSH2 VALIDA mesmo no destroy: o
	# terraform avalia o bloco do recurso (o azurerm valida o formato de
	# `admin_ssh_key.public_key`) antes de montar o grafo de destroy. Um valor
	# placeholder como "unused" aborta com "is not a complete SSH2 Public Key".
	# Reusa a chave real (git-ignored); se sumiu num clone limpo, gera uma
	# throwaway so pra satisfazer a validacao -- a VM e apagada de qualquer forma.
	@[ -f $(VM_SSH_KEY) ] || ssh-keygen -t ed25519 -f $(VM_SSH_KEY) -N "" -C pytstop-vm-demo >/dev/null
	ARM_SUBSCRIPTION_ID="$$(az account show --query id -o tsv)" $(TF_AZVM) destroy -auto-approve -input=false \
		-var resource_group_name=$(VM_RG) -var location=$(VM_LOCATION) -var vm_size=$(VM_SIZE) \
		-var spot=$(SPOT) -var ssh_allowed_cidr="0.0.0.0/32" -var admin_ssh_pubkey="$$(cat $(VM_SSH_KEY).pub)"
	@/bin/rm -f $(VM_KUBECONF) .vm-demo-known_hosts
	@echo ">> VM de demo destruida (RG + IP + disco). Custo -> zero."
