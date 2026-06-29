<p align="center">
  <img src="logo-pytstop.png" width="512" alt="PytStop">
</p>

# PytStop -- Tech Challenge Fase 2

<p align="center">
  <a href="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/workflows/ci.yml"><img src="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/workflows/cd.yml"><img src="https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/workflows/cd.yml/badge.svg" alt="CD"></a>
  <img src="https://img.shields.io/badge/coverage-%E2%89%A595%25-brightgreen" alt="coverage >= 95%">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <img src="https://img.shields.io/badge/mypy-checked-2a6db2" alt="mypy checked">
  <img src="https://img.shields.io/badge/architecture-Clean%20%C2%B7%20import--linter-success" alt="Clean Architecture (import-linter)">
</p>

Sistema de gestão de ordens de serviço de uma oficina mecânica de médio porte (clientes, veículos, OS, estoque, orçamentos), construído com Domain-Driven Design na fase 1 e evoluído na fase 2 para qualidade, resiliência e escalabilidade.

**Objetivos da fase 2** ([enunciado](docs/requisitos/fase2/desafio-tech-fase-2.md) · [gap analysis](docs/requisitos/fase2/gap-analysis-fase-2.md)):

- **Clean Architecture verificada**: camadas formalizadas e contratos de dependência garantidos por import-linter na CI ([ADR-015](docs/arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md));
- **Kubernetes com HPA**: manifests completos (Deployment, Service, ConfigMap, Secret, HPA por CPU/memória) em [`k8s/`](k8s/README.md) ([ADR-016](docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md));
- **Infraestrutura como código**: Terraform provisiona cluster kind + PostgreSQL num único apply em [`infra/`](infra/README.md) ([ADR-017](docs/arquitetura/adr/fase2/017-provisionamento-banco.md));
- **CD real**: push na main publica imagem por SHA no GHCR e implanta do zero em cluster efêmero com smoke test ([ADR-019](docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md));
- **Evolução da API**: abertura de OS com serviços e peças, situação no vocabulário do challenge, decisão externa de orçamento, listagem ordenada por prioridade e notificação de status por e-mail ([ADR-018](docs/arquitetura/adr/fase2/018-notificacao-email.md), [ADR-021](docs/arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md));
- **Observabilidade**: traces OpenTelemetry (FastAPI + SQLAlchemy) no Jaeger ([ADR-020](docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)) e métricas do relay no Prometheus ([ADR-024](docs/arquitetura/adr/fase2/024-metricas-prometheus.md)).

Como qualidade além do escopo, o grupo amortizou parte da dívida técnica: entrega de eventos por **Transactional Outbox + relay** ([ADR-022](docs/arquitetura/adr/fase2/022-transactional-outbox-relay.md)) e rate limiter com **storage compartilhado (Redis)** sob HPA ([ADR-023](docs/arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md)).

O desenho integrado está na [RFC-002](docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md); o índice da entrega, em [`docs/entrega/fase2/`](docs/entrega/fase2/README.md).

## Arquitetura da fase 2

Pipeline de deploy, infraestrutura provisionada e workloads no cluster ([RFC-002 §3](docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md)):

<!-- fonte: RFC-002 §3 — manter em sincronia -->
```mermaid
flowchart TB
    push_main(["Push na main"]) --> ci_stage

    subgraph gha["GitHub Actions — pipeline de CI/CD (ADR-019)"]
        ci_stage["CI herdada<br/>ruff · mypy · bandit ·<br/>testes com gate de 95%"] --> build_img["Build da<br/>imagem Docker"]
        build_img --> publish["Push no GHCR<br/>tag = SHA do commit"]
        publish --> cd_job["Job de CD<br/>terraform apply · kind load ·<br/>kubectl apply · smoke test"]
    end

    ghcr[("GHCR<br/>imagem versionada por SHA")]
    publish --> ghcr

    cd_job -->|"terraform apply"| infra_tf
    cd_job -->|"kubectl apply -f k8s/"| k8s_app
    ghcr -.->|"kind load — imagem injetada<br/>nos nós, sem pull do registry"| app

    subgraph cluster["Cluster kind (ADR-016) — dev local, vídeo e CI efêmero"]
        subgraph infra_tf["/infra — Terraform (ADR-016, ADR-017)"]
            pg[("PostgreSQL 16<br/>StatefulSet + PVC")]
            ms["metrics-server"]
        end
        subgraph k8s_app["/k8s — manifests da aplicação"]
            svc["Service"]
            app["PytStop API — Deployment<br/>Clean Architecture (ADR-015):<br/>Entidades · Casos de Uso ·<br/>Adaptadores de Interface ·<br/>Frameworks & Drivers"]
            cfg["ConfigMap + Secret"]
            hpa["HPA — CPU e memória"]
            mailpit["Mailpit (ADR-018)<br/>Deployment + Service ClusterIP"]
            jaeger["Jaeger all-in-one (ADR-020)<br/>onda final condicional"]
            relay["Relay de eventos (ADR-022)<br/>Deployment — outbox→SMTP"]
            redis["Redis (ADR-023)<br/>Deployment + Service — rate limit"]
            prometheus["Prometheus (ADR-024)<br/>Deployment + Service — métricas do relay"]
        end
    end

    svc --> app
    cfg -.->|"env vars"| app
    hpa -->|"escala réplicas"| app
    ms -.->|"métricas de CPU e memória"| hpa
    app -->|"SQL via DATABASE_URL"| pg
    app -->|"grava outbox + NOTIFY"| pg
    relay -->|"LISTEN/NOTIFY + claim outbox"| pg
    relay -->|"SMTP"| mailpit
    app -.->|"rate limit"| redis
    app -.->|"traces OTLP"| jaeger
    prometheus -.->|"scrape /metrics"| relay
```

A aplicação é um monolito modular: cada contexto delimitado segue as camadas da Clean Architecture (Entidades, Casos de Uso, Adaptadores de Interface, Frameworks & Drivers), mapeadas sobre as pastas `dominio/`, `aplicacao/`, `interfaces/` e `infraestrutura/` de cada módulo. A regra de dependência é verificada em todo build por `make lint-arch` (import-linter). Convenção de idioma híbrida ([ADR-009](docs/arquitetura/adr/009-decisao-de-idioma.md)): termos de negócio em português, padrões técnicos em inglês.

### Contextos Delimitados

| Contexto | Classificação | Descrição |
|---|---|---|
| Ordem de Serviço | Principal | Ciclo de vida da OS, orçamentos, máquina de estados |
| Cliente + Veículo | Suporte | Cadastro de clientes e veículos vinculados |
| Catálogo de Serviços | Suporte | Serviços oferecidos pela oficina |
| Estoque | Principal | Peças e insumos com controle de quantidade |
| Autenticação | Genérico | JWT, controle de acesso por papel |

## Execução local (docker-compose)

> **Setup do zero?** Guias passo a passo por plataforma:
> [**Windows**](docs/setup/windows.md) - [**macOS**](docs/setup/macos.md) - [**Linux**](docs/setup/linux.md)

Pré-requisitos para quem já tem o ambiente pronto: Python 3.12+, [uv](https://docs.astral.sh/uv/) ([ADR-014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md)), Docker 24+ com Compose v2 e Git.

```bash
git clone https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2.git
cd postech-sw-arch-p2
make reset-db                          # postgres + backend + mailpit + UI + seed completo
open http://localhost:8080/login       # atalhos Admin / Atendente / Mecanico
```

`make reset-db` derruba qualquer stack anterior, apaga o volume do postgres,
rebuilda imagens, aguarda o backend ficar saudável (healthcheck em
`/api/v1/saude` — RNF-019) e popula usuários + dados de demo (7 clientes,
10 veículos, 8 serviços, 14 itens, 8 OS em estados variados). **Apaga todos
os dados do DB local.**

Para pular o seed de demo: `SKIP_DEMO=1 make reset-db`. Derrubar tudo:
`make down`. Após `git pull`, prefira `make rebuild`. Para subir só
backend + banco (sem UI): `make up-backend`. Traces locais (opcional):
`OTEL_ENABLED=true docker compose --profile otel up -d` sobe também o Jaeger.

> Se aparecer `failed to connect to the docker API ...docker.sock`, veja
> [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md).

### URLs

| Serviço | URL |
|---|---|
| UI NiceGUI | http://localhost:8080 |
| Backend Swagger | http://localhost:8000/docs |
| Health probe | http://localhost:8000/api/v1/saude |
| Mailpit (caixa de e-mails da demo — RF-024) | http://localhost:8025 |
| Jaeger UI (só com `--profile otel`) | http://localhost:16686 |

### Credenciais seed (dev-only -- abertas por design)

| Papel | E-mail | Senha |
|---|---|---|
| admin | `admin@pytstop.dev` | `admin-dev-pass-2026` |
| atendente | `atendente@pytstop.dev` | `atendente-dev-pass-2026` |
| mecanico | `mecanico@pytstop.dev` | `mecanico-dev-pass-2026` |

Na tela `/login`, os atalhos `ADMIN` / `ATENDENTE` / `MECANICO` logam
automaticamente. Pares **(placa, CPF/CNPJ)** das OS do seed (úteis na tela
pública `/acompanhamento`): [`ui/seed-users.md`](ui/seed-users.md).

## Deploy em Kubernetes (kind)

Caminho recomendado — ciclo completo local, o mesmo que o CD executa ([ADR-019](docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)):

```bash
make cd-local    # terraform apply + build da imagem + kind load + metrics-server + manifests + rollout + smoke
make k8s-down    # terraform destroy — remove cluster, banco e app
```

Pré-requisitos: [Terraform >= 1.7](https://developer.hashicorp.com/terraform/install), [kind](https://kind.sigs.k8s.io/) e kubectl, além do Docker (no Colima, reserve 4 GiB: `colima start --memory 4`).

Passo a passo manual equivalente (provisionar, carregar imagem, aplicar manifests, conferir e acessar — incluindo a validação do HPA sob carga e os traces no Jaeger): [`k8s/README.md`](k8s/README.md).

```bash
kubectl --context kind-pytstop -n pytstop port-forward svc/pytstop-api 18000:8000   # Swagger: http://localhost:18000/docs
kubectl --context kind-pytstop -n pytstop port-forward svc/mailpit 8025:8025        # Mailpit UI
kubectl --context kind-pytstop -n pytstop port-forward svc/jaeger 16686:16686       # Jaeger UI
kubectl --context kind-pytstop -n pytstop port-forward svc/prometheus 9090:9090     # Prometheus UI (métricas do relay)
```

Admin de demo do cluster (seed no boot): `admin@pytstop.dev` / `pytstop-admin-demo-2026` (valores de demonstração comitados — [`k8s/secret.yaml`](k8s/secret.yaml)).

## Provisionamento com Terraform

Um único `terraform apply` cria o cluster kind e o PostgreSQL 16 (StatefulSet + PVC + Service + Secret) no namespace `pytstop-infra` (RNF-021):

```bash
terraform -chdir=infra init
terraform -chdir=infra plan
terraform -chdir=infra apply
```

Recursos criados, variáveis, fluxo integrado e troubleshooting: [`infra/README.md`](infra/README.md). A fronteira `/infra` (infraestrutura-base, Terraform) × `/k8s` (artefatos de implantação, kubectl) está na [RFC-002 §2](docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md).

## CI/CD

| Workflow | Trigger | O que faz |
|---|---|---|
| [`ci.yml`](.github/workflows/ci.yml) | PRs e push na main | lint (ruff), contratos de camadas (import-linter), mypy, bandit, testes com gate de cobertura de 95% |
| [`cd.yml`](.github/workflows/cd.yml) | push na main + `workflow_dispatch` | build e push da imagem no GHCR (tag por SHA) → cluster kind efêmero no runner via Terraform → `kind load` → manifests de `k8s/` → rollout → smoke test |
| [`full-test-ci.yml`](.github/workflows/full-test-ci.yml) | nightly | E2E concorrente contra a stack compose completa |

Execuções verdes do CD na main: [27450493913](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27450493913) (primeiro deploy) e [27451618014](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27451618014) (com OTel/Jaeger). O fluxo local `make cd-local` espelha o workflow passo a passo.

## API

Documentação interativa no Swagger UI: `http://localhost:8000/docs` no compose, `http://localhost:18000/docs` via port-forward do cluster. Collection completa (gerada do contrato OpenAPI, 46 requisições): [`docs/entrega/fase2/postman_collection.json`](docs/entrega/fase2/postman_collection.json).

| Grupo | Prefixo | Operações |
|---|---|---|
| Clientes | /api/v1/clientes | CRUD + veículos + LGPD (dados pessoais, consentimento) |
| Serviços | /api/v1/servicos | CRUD catálogo |
| Estoque | /api/v1/estoque | CRUD + ajuste de quantidade |
| Ordens de Serviço | /api/v1/ordens-de-servico | Criação com serviços e peças (RF-020), listagem ordenada (RF-023), ciclo completo da OS |
| Autenticação | /api/v1/autenticacao | Login, registro, refresh, logout |
| Público | /api/v1/acompanhamento · /api/v1/publico/.../decisao-orcamento | Acompanhamento por placa + documento (RF-021) e decisão externa de orçamento via `X-Webhook-Token` (RF-022) |
| Saúde | /api/v1/saude | Health check (probes do Kubernetes) |

## Vídeo de demonstração

**Vídeo de demonstração:** _link será adicionado após a gravação_ <!-- VIDEO-LINK-FASE-2 -->

Roteiro de gravação (deploy, CI/CD, APIs, HPA, traces): [`docs/entrega/fase2/roteiro-video.md`](docs/entrega/fase2/roteiro-video.md).

## Desenvolvimento

| Tópico | Onde ler |
|---|---|
| Setup do zero (instalar uv, Docker, etc.) | [`docs/setup/`](docs/setup/) (Windows / macOS / Linux) |
| Loop de dev rápido (uvicorn hot-reload), checks locais, atualizar deps | [`docs/desenvolvimento.md`](docs/desenvolvimento.md) |
| Troubleshooting Docker (socket, Compose v2) e conflito uv/venv | [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md) |
| Debugging do dev loop (Colima, JWT_SECRET, 500s comuns) | [`docs/debugging-guide.md`](docs/debugging-guide.md) |
| Manifests Kubernetes e validação do HPA | [`k8s/README.md`](k8s/README.md) |
| Terraform (recursos, variáveis, troubleshooting) | [`infra/README.md`](infra/README.md) |
| UI NiceGUI (sandbox dev-only) | [`ui/README.md`](ui/README.md) |
| Worktrees paralelos (rodar 2+ branches sem conflito de portas) | [`docs/setup/worktrees-paralelos.md`](docs/setup/worktrees-paralelos.md) |

## UI de Simulação

Sandbox em Python puro (NiceGUI) para testes manuais integrados da API.
**Dev-only** -- não entra no Dockerfile do backend nem recebe manifest K8s.
Coexiste com o Swagger UI (`/docs`): Swagger é referência crua da API, a UI
de simulação é sandbox integrado. Guia completo: [`ui/README.md`](ui/README.md).

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| DATABASE_URL | URL de conexão PostgreSQL | postgresql://pytstop:pytstop@postgres:5432/pytstop |
| JWT_SECRET | Chave secreta para tokens JWT (>= 32 bytes) | change-this-in-production |
| JWT_EXPIRATION_MINUTES | Tempo de expiração do token | 30 |
| ENCRYPTION_KEY | Chave Fernet da PII em repouso (estável entre réplicas) | -- |
| ENVIRONMENT | Ambiente (development/production) | development |
| CORS_ORIGINS | Origens permitidas para CORS | http://localhost:3000 |
| RUN_MIGRATIONS_ON_STARTUP | Executar migrations ao iniciar o app | false (true no cluster) |
| RUN_SEED_ON_STARTUP | Criar admin inicial no boot (best-effort) | false (true no cluster) |
| SMTP_HOST / SMTP_PORT / SMTP_FROM | Servidor SMTP das notificações de status (RF-024) | mailpit / 1025 / oficina@pytstop.local |
| ORCAMENTO_WEBHOOK_TOKEN | Token do canal externo de decisão de orçamento (RF-022) | valor de demo no compose e no cluster |
| OTEL_ENABLED | Liga a instrumentação OpenTelemetry (ADR-020) | false (true no cluster de demo) |
| OTEL_EXPORTER_OTLP_ENDPOINT | Endpoint OTLP/gRPC do backend de traces | http://jaeger:4317 |
| RATE_LIMIT_STORAGE_URI | Store compartilhado do rate limiter sob HPA (ADR-023); ausente, cai para `memory://` | memory:// local / redis://redis:6379 no cluster |
| OUTBOX_POLL_SEGUNDOS / OUTBOX_LOTE / OUTBOX_LEASE_SEGUNDOS | Poll de segurança, tamanho do lote e lease do relay da Transactional Outbox (ADR-022) | 5 / 10 / 60 |
| RELAY_HEARTBEAT | Caminho do arquivo de heartbeat do relay (liveness) | /tmp/relay-heartbeat |
| RELAY_METRICS_ENABLED / RELAY_METRICS_PORT | Liga o `/metrics` do relay para o Prometheus scrapear (ADR-024) | false / 9100 (true no cluster de demo) |
| DB_POOL_SIZE / DB_MAX_OVERFLOW | Pool de conexões por réplica, dimensionado para o pior caso do HPA (RNF-024) | 5 / 10 |
| BACKEND_URL | URL do backend consumida pela UI | http://localhost:8001 local / http://app:8000 docker |
| UI_PORT | Porta da UI NiceGUI | 8080 |

Mapa completo variável → ConfigMap/Secret no cluster: [RFC-002 §6](docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) e [`k8s/configmap.yaml`](k8s/configmap.yaml) / [`k8s/secret.yaml`](k8s/secret.yaml).

## Stack

- **Linguagem**: Python 3.12
- **Framework**: FastAPI
- **Banco de dados**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (mapeamento imperativo)
- **Autenticação**: JWT (HS256)
- **E-mail**: adapter SMTP + Mailpit (demo)
- **Mensageria/eventos**: Transactional Outbox + processo relay (LISTEN/NOTIFY)
- **Rate limiting**: slowapi com storage compartilhado em Redis (sob HPA)
- **Observabilidade**: OpenTelemetry — traces (FastAPI + SQLAlchemy) no Jaeger + métricas do relay no Prometheus
- **Testes**: pytest, testcontainers, polyfactory
- **Linting**: ruff, mypy (strict), import-linter, bandit
- **Containerização**: Docker, Docker Compose
- **Orquestração e IaC**: Kubernetes (kind), HPA, Terraform
- **CI/CD**: GitHub Actions + GHCR

## Testes

```bash
make test           # unitarios com cobertura (95%+ obrigatorio; configurado em .coveragerc)
make test-coverage  # unitarios com relatorio terminal e coverage.xml para CI/Sonar
make test-integ     # integracao com testcontainers + PostgreSQL
make test-all       # tudo (unitarios + integracao + e2e)
make lint-arch      # contratos de camadas Clean (import-linter, ADR-015)
```

Cobertura atual na main: **95,34%** (gate de 95%, [run 28299121351](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/28299121351)). Detalhes do workflow de dev
(lint, mypy, bandit, atualizar dependências): [`docs/desenvolvimento.md`](docs/desenvolvimento.md).

## Code review automatizado pelo Claude

O repositório tem um workflow GitHub Actions que roda o
[Claude Code Action](https://github.com/anthropics/claude-code-action)
oficial usando o secret `CLAUDE_CODE_OAUTH_TOKEN`:

| Workflow | Arquivo | Trigger | Perfil | Quando usar |
|---|---|---|---|---|
| **Claude On-Demand** | `.github/workflows/claude-on-demand.yml` | `issue_comment`, `pull_request_review_comment`, `workflow_dispatch` | **Profundo**: `opus` + `--effort max` + `--max-turns 50` | Review sob demanda, pedir tarefa específica, ou rodar em PRs entre branches de feature |

O auto-review em PR (`claude-code-review.yml`, perfil rápido `sonnet`) foi
removido na fase 2: review é sob demanda. Os defaults ficam centralizados em
[`.github/actions/claude/action.yml`](.github/actions/claude/action.yml) e o
`claude-on-demand.yml` sobrescreve via inputs.

### Acionar manualmente

**Opção A -- Comentar `@claude` no PR ou issue** (mais comum):

```
@claude faca code review novamente focando em seguranca de auth
```

```
@claude tem alguma race condition em ui/cliente_api.py::_request?
```

A action detecta `@claude` no body do comentário e responde inline. Funciona
em PRs, em issues, e em comments de review (linha específica). **Só funciona
quando o workflow já está na branch `main`** (limitação do GitHub: events
`issue_comment` sempre executam o workflow do default branch).

**Opção B -- Run workflow manual via GitHub UI**:

1. Repo -> aba **Actions** -> **Claude On-Demand** (sidebar esquerda)
2. Clique em **Run workflow** (canto direito)
3. Em "Use workflow from", selecione a branch
4. Em "Instrução para o Claude", digite o que quer (ex.: `review PR #15 focando em LGPD`)
5. **Run workflow**

**Opção C -- `gh` CLI**:

```bash
gh workflow run claude-on-demand.yml \
  --ref feat/minha-branch \
  --field prompt="review este PR e foque em performance"
```

> ⚠️ **Limitação do GitHub Actions**: tanto a Opção B quanto a Opção C
> precisam que o arquivo `claude-on-demand.yml` já exista **na default
> branch (main)**. O `--ref` (ou o seletor "Use workflow from") só muda
> o checkout durante a execução -- o lookup do workflow em si é sempre na
> main.

### Custos e limites

- Cada run consome créditos do plano Claude Max do owner do token.
- O perfil profundo usa `--max-turns 50` pra dar folga a sub-agents
  (`Task` tool) em PR grande. Se um run ficar batendo no limite, suba o
  `max_turns` na chamada do composite ao invés de subir o default global.

## Decisões de Arquitetura (ADRs e RFCs)

### Fase 2

| Artefato | Título | Status |
|---|---|---|
| [RFC-002](docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) | Infraestrutura e deploy da fase 2 (desenho integrado) | Aceita |
| [ADR-015](docs/arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) | Clean Architecture como arquitetura alvo | Aceita |
| [ADR-016](docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md) | kind como plataforma Kubernetes | Aceita |
| [ADR-017](docs/arquitetura/adr/fase2/017-provisionamento-banco.md) | PostgreSQL StatefulSet via Terraform | Aceita |
| [ADR-018](docs/arquitetura/adr/fase2/018-notificacao-email.md) | Notificação de status por e-mail (SMTP + Mailpit) | Aceita |
| [ADR-019](docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md) | Pipeline de CI/CD com deploy em kind efêmero | Aceita |
| [ADR-020](docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md) | Observabilidade OpenTelemetry mínima | Aceita |
| [ADR-021](docs/arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md) | Aprovação/recusa externa de orçamento | Aceita |
| [ADR-022](docs/arquitetura/adr/fase2/022-transactional-outbox-relay.md) | Transactional Outbox + relay para entrega de eventos de integração | Aceita |
| [ADR-023](docs/arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md) | Rate limiter com storage compartilhado (Redis) sob HPA | Aceita |
| [ADR-024](docs/arquitetura/adr/fase2/024-metricas-prometheus.md) | Métricas de observabilidade com Prometheus e OpenTelemetry no relay | Aceita |

### Fase 1

| ADR | Título | Status |
|---|---|---|
| [000](docs/arquitetura/adr/000-template.md) | Template MADR | -- |
| [001](docs/arquitetura/adr/001-framework-fastapi.md) | Framework FastAPI | Aceito |
| [002](docs/arquitetura/adr/002-banco-postgresql.md) | Banco PostgreSQL | Aceito |
| [003](docs/arquitetura/adr/003-arquitetura-ddd-onion.md) | Arquitetura DDD + Onion | Parcialmente substituído pelo [ADR-015](docs/arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) |
| [004](docs/arquitetura/adr/004-autenticacao-jwt.md) | Autenticação JWT HS256 | Aceito |
| [005](docs/arquitetura/adr/005-estrategia-testes.md) | Estratégia de testes | Aceito |
| [006](docs/arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo SQLAlchemy | Aceito |
| [007](docs/arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organização dos contextos delimitados | Aceito |
| [008](docs/arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista de estoque | Aceito |
| [009](docs/arquitetura/adr/009-decisao-de-idioma.md) | Modelo híbrido de idioma | Aceito |
| [010](docs/arquitetura/adr/010-validacao-documentos-brutils.md) | Validação CPF/CNPJ (brutils) e Placa (regex) | Aceita |
| [011](docs/arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de segurança e análise estática | Aceito |
| [012](docs/arquitetura/adr/012-licenciamento-software-sbom.md) | Licenciamento de software e SBOM | Aceito |
| [013](docs/arquitetura/adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd | Proposta |
| [014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes uv | Aceita |

## Documentação

| Artefato | Descrição |
|---|---|
| [Entrega Fase 2](docs/entrega/fase2/entrega-fase-2.md) | Índice mestre da entrega — rastreabilidade requisito → evidência |
| [Roteiro do vídeo](docs/entrega/fase2/roteiro-video.md) | Blocos cronometrados com comandos e evidências |
| [Gap Analysis Fase 2](docs/requisitos/fase2/gap-analysis-fase-2.md) | Challenge × código da fase 1 → RF-020–024, RNF-017–024, RN-018–020 |
| [Domain Storytelling](docs/arquitetura/domain-storytelling/) | 5 cenários no egon.io + entrevistas com especialistas de domínio |
| [Event Storming](docs/arquitetura/event-storming/) | 2 fluxos detalhados (ciclo da OS e gestão de estoque) |
| [Mapa de Contextos](docs/arquitetura/mapa-contextos.md) | 5 contextos delimitados com padrões de integração |
| [Modelo de Domínio](docs/arquitetura/modelo-dominio.md) | Diagramas de classes por agregado |
| [Glossário](docs/requisitos/glossario.md) | Linguagem Ubíqua -- termos de domínio |
| [Entrega Fase 1](docs/entrega/entrega-fase-1.md) | Índice dos entregáveis do MVP |

## Equipe

| Nome | RM | Discord |
|---|---|---|
| Joao Amaral | RM373448 | joao_13997 |
| Allan Aurelio | RM372116 | all66_ |
| Carlos Silva | RM374191 | carlossilva156 |
| Guilherme Sousa | RM373609 | romen0 |
| Nicolas Gerbi | RM372644 | sethiiz_gerbi |

## Curso

- **FIAP Pos Tech** -- Arquitetura de Software (15SOAT)
- **Fase 2 do Tech Challenge** -- vale 60% da nota de todas as disciplinas da fase
