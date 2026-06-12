<p align="center">
  <img src="logo-pytstop.png" width="512" alt="PytStop">
</p>

# PytStop -- Tech Challenge Fase 1

MVP de back-end para sistema de gestão de ordens de serviço de uma oficina mecânica de médio porte (clientes, veículos, OS, estoque, orçamentos), aplicando Domain-Driven Design (DDD).

> ## Fast Check -- só docker
>
> Stack completa (db seedada + backend + UI) puxando do GHCR, sem build local e sem `.env`. Passo a passo (login no GHCR + `docker compose up`): [`db-image/QUICKSTART.md`](db-image/QUICKSTART.md).

## Pré-requisitos

> **Setup do zero?** Guias passo a passo por plataforma:
> [**Windows**](docs/setup/windows.md) - [**macOS**](docs/setup/macos.md) - [**Linux**](docs/setup/linux.md)

Quem já tem o ambiente pronto:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gerenciador de dependências e ambientes virtuais -- [ADR-014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md))
- Docker 24+ e Docker Compose v2
- Git

## Quick Start

```bash
git clone https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1.git
cd postech-sw-arch-p1
make reset-db                          # postgres + backend + UI + seed completo
open http://localhost:8080/login       # atalhos Admin / Atendente / Mecanico
```

`make reset-db` derruba qualquer stack anterior, apaga o volume do postgres,
rebuilda imagens, aguarda o backend ficar saudável e popula usuários + dados
de demo (7 clientes, 10 veículos, 8 serviços, 14 itens, 8 OS em estados
variados). **Apaga todos os dados do DB local.**

Para pular o seed de demo (DB só com usuários): `SKIP_DEMO=1 make reset-db`.
Derrubar tudo depois: `make down`. Após `git pull`, prefira `make rebuild`
(força rebuild das imagens sem apagar o DB).

> Se aparecer `failed to connect to the docker API ...docker.sock`, o socket
> não está no caminho padrão. Veja
> [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md) para
> configurar manualmente (Docker Desktop, Colima, Linux).

### URLs

| Serviço | URL |
|---|---|
| UI NiceGUI | http://localhost:8080 |
| Backend Swagger | http://localhost:8000/docs |
| Health probe | http://localhost:8000/api/v1/saude |

### Credenciais seed (dev-only -- abertas por design)

| Papel | E-mail | Senha |
|---|---|---|
| admin | `admin@pytstop.dev` | `admin-dev-pass-2026` |
| atendente | `atendente@pytstop.dev` | `atendente-dev-pass-2026` |
| mecanico | `mecanico@pytstop.dev` | `mecanico-dev-pass-2026` |

Na tela `/login`, os atalhos `ADMIN` / `ATENDENTE` / `MECANICO` logam
automaticamente. Para os pares **(placa, CPF/CNPJ)** das 8 OS criadas pelo
seed (úteis pra testar a tela pública `/acompanhamento`), veja
[`ui/seed-users.md`](ui/seed-users.md). Definição em código:
`ui/config.py::_USUARIOS_SEED` (espelhada em `scripts/seed_usuarios.py`).

## Desenvolvimento

| Topico | Onde ler |
|---|---|
| Setup do zero (instalar uv, Docker, etc.) | [`docs/setup/`](docs/setup/) (Windows / macOS / Linux) |
| Loop de dev rápido (uvicorn hot-reload), checks locais, atualizar deps | [`docs/desenvolvimento.md`](docs/desenvolvimento.md) |
| Troubleshooting Docker (socket, Compose v2) e conflito uv/venv | [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md) |
| Debugging do dev loop (Colima, JWT_SECRET, 500s comuns) | [`docs/debugging-guide.md`](docs/debugging-guide.md) |
| UI NiceGUI (sandbox dev-only) | [`ui/README.md`](ui/README.md) |
| Worktrees paralelos (rodar 2+ branches sem conflito de portas) | [`docs/setup/worktrees-paralelos.md`](docs/setup/worktrees-paralelos.md) |
| Publicar imagens db+app+ui no GHCR (pipeline `make update-ghcr` + compose standalone do fast-check) | [`db-image/README.md`](db-image/README.md) |

## UI de Simulacao

Sandbox em Python puro (NiceGUI) para testes manuais integrados da API.
**Dev-only** -- não entra no Dockerfile do backend, não é promovida a
entregável. Coexiste com o Swagger UI (`/docs`): Swagger é referência crua
da API, a UI de simulação é sandbox integrado.

> **Nota arquitetural**: o serviço `ui` aparece no `docker-compose.yml` mas
> não no [diagrama C4 Container](docs/arquitetura/c4/c4-container.md), por
> ser componente auxiliar de desenvolvimento. Ver
> [issue #109](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/109)
> para a decisão em discussão sobre como sinalizar isso nos diagramas
> oficiais.

Guia completo de uso da UI (páginas, autenticação, modo híbrido,
troubleshooting, contribuir): [`ui/README.md`](ui/README.md).

## Arquitetura

Monolito modular com DDD e Onion Architecture. Cada contexto delimitado é um módulo Python com 4 camadas:

```
interfaces/ -> aplicacao/ -> dominio/
     ^
infraestrutura/
```

Regra de dependência estrita: camadas internas nunca importam camadas externas. Convenção de idioma híbrida (ADR-009): termos de negócio em português, padrões técnicos em inglês.

### Contextos Delimitados

| Contexto | Classificação | Descrição |
|---|---|---|
| Ordem de Serviço | Principal | Ciclo de vida da OS, orçamentos, máquina de estados |
| Cliente + Veículo | Suporte | Cadastro de clientes e veículos vinculados |
| Catálogo de Serviços | Suporte | Serviços oferecidos pela oficina |
| Estoque | Principal | Pecas e insumos com controle de quantidade |
| Autenticação | Genérico | JWT, controle de acesso por papel |

## API

Documentação interativa disponível em `http://localhost:8000/docs` (Swagger UI).

| Grupo | Prefixo | Operações |
|---|---|---|
| Clientes | /api/v1/clientes | CRUD + veiculos |
| Serviços | /api/v1/servicos | CRUD catálogo |
| Estoque | /api/v1/estoque | CRUD + ajuste quantidade |
| Ordens de Serviço | /api/v1/ordens-de-servico | Ciclo completo da OS |
| Autenticação | /api/v1/autenticacao | Login, registro, refresh, logout |
| Saude | /api/v1/saude | Health check |

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| DATABASE_URL | URL de conexão PostgreSQL | postgresql://pytstop:pytstop@postgres:5432/pytstop |
| JWT_SECRET | Chave secreta para tokens JWT | change-this-in-production |
| JWT_EXPIRATION_MINUTES | Tempo de expiração do token | 30 |
| ENVIRONMENT | Ambiente (development/production) | development |
| CORS_ORIGINS | Origens permitidas para CORS | http://localhost:3000 |
| RUN_MIGRATIONS_ON_STARTUP | Executar migrations ao iniciar o app | false |
| BACKEND_URL | URL do backend consumida pela UI | http://localhost:8001 local / http://app:8000 docker |
| UI_PORT | Porta da UI NiceGUI | 8080 |

## Stack

- **Linguagem**: Python 3.12
- **Framework**: FastAPI
- **Banco de dados**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (mapeamento imperativo)
- **Autenticação**: JWT (HS256)
- **Testes**: pytest, testcontainers, polyfactory
- **Linting**: ruff, mypy (strict), import-linter
- **Containerização**: Docker, Docker Compose

## Testes

```bash
make test           # unitarios com cobertura (95%+ obrigatorio; configurado em .coveragerc)
make test-coverage  # unitarios com relatorio terminal e coverage.xml para CI/Sonar
make test-integ     # integracao com testcontainers + PostgreSQL
make test-all       # tudo (unitarios + integracao + e2e)

# Ou diretamente:
pytest tests/unitarios/ --no-lint -v                                        # unitarios
pytest tests/integracao/ --no-lint -v                                       # integracao (requer Docker)
uv run --extra test --extra ui pytest tests/unitarios/ --no-lint --cov=src  # cobertura local
```

Detalhes do workflow de dev (lint, mypy, bandit, atualizar dependências):
[`docs/desenvolvimento.md`](docs/desenvolvimento.md).

## Code review automatizado pelo Claude

O repositorio tem um workflow GitHub Actions que roda o
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

Cole no comentario do PR/issue:

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
4. Em "Instrução para o Claude", digite o que quer (ex.: `review PR #81 focando em LGPD`)
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
> main. Se a action ainda não foi mergeada, o comando retorna `HTTP 404
> workflow not found on the default branch`.
>
> **Workaround antes do merge inicial**: re-acionar o auto-review fechando
> e reabrindo o PR (dispara o trigger `reopened`):
>
> ```bash
> gh pr close <numero> && gh pr reopen <numero>
> ```

### Custos e limites

- Cada run consome créditos do plano Claude Max do owner do token.
- Auto-review dispara **uma vez por PR para main** (na abertura/reabertura).
  Pushes seguintes não re-disparam -- pra revisar de novo, use a seção
  "Acionar manualmente" acima.
- PRs entre branches de feature (target != main) não disparam auto-review;
  use Run workflow manual ou `@claude` mention quando quiser.
- **Profundidade vs custo**: auto-review usa `--max-turns 30` (suficiente
  pra `track_progress` + 4 eixos do prompt em PR típico); on-demand usa
  `--max-turns 50` pra dar folga a sub-agents (`Task` tool) em PR grande.
  Se um run ficar batendo no limite, sobe o `max_turns` na chamada do
  composite ao invés de subir o default global.
- Se quiser desabilitar o auto-review temporariamente, comente o bloco
  `on.pull_request` em `claude-code-review.yml` (deixa só quando precisar).

## Decisões de Arquitetura (ADRs)

| ADR | Título | Status |
|---|---|---|
| [000](docs/arquitetura/adr/000-template.md) | Template MADR | -- |
| [001](docs/arquitetura/adr/001-framework-fastapi.md) | Framework FastAPI | Aceito |
| [002](docs/arquitetura/adr/002-banco-postgresql.md) | Banco PostgreSQL | Aceito |
| [003](docs/arquitetura/adr/003-arquitetura-ddd-onion.md) | Arquitetura DDD + Onion | Aceito |
| [004](docs/arquitetura/adr/004-autenticacao-jwt.md) | Autenticacao JWT HS256 | Aceito |
| [005](docs/arquitetura/adr/005-estrategia-testes.md) | Estratégia de testes | Aceito |
| [006](docs/arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo SQLAlchemy | Aceito |
| [007](docs/arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organização dos contextos delimitados | Aceito |
| [008](docs/arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista de estoque | Aceito |
| [009](docs/arquitetura/adr/009-decisao-de-idioma.md) | Modelo híbrido de idioma | Aceito |
| [010](docs/arquitetura/adr/010-validacao-documentos-brutils.md) | Validação CPF/CNPJ/Placa com brutils | Proposta |
| [011](docs/arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de segurança e análise estática | Aceito |
| [012](docs/arquitetura/adr/012-licenciamento-software-sbom.md) | Licenciamento de software e SBOM | Aceito |
| [013](docs/arquitetura/adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd | Aceito |
| [014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes uv | Aceita |

## Documentação

| Artefato | Descrição |
|---|---|
| [Domain Storytelling](docs/arquitetura/domain-storytelling/) | 5 cenários no egon.io + entrevistas com especialistas de domínio |
| [Event Storming](docs/arquitetura/event-storming/) | 2 fluxos detalhados (ciclo da OS e gestão de estoque) |
| [Mapa de Contextos](docs/arquitetura/mapa-contextos.md) | 5 contextos delimitados com padrões de integração |
| [Modelo de Dominio](docs/arquitetura/modelo-dominio.md) | Diagramas de classes por agregado |
| [Glossário](docs/requisitos/glossario.md) | Linguagem Ubíqua -- termos de domínio |
| [Entrega Fase 1](docs/entrega/entrega-fase-1.md) | Índice completo dos entregáveis |

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
- **Prazo**: 5 de maio de 2026
- **Peso na nota**: 90%
