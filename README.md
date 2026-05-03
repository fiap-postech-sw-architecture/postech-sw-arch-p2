<p align="center">
  <img src="logo-pytstop.png" width="512" alt="PytStop">
</p>

# PytStop -- Tech Challenge Fase 1

MVP de back-end para sistema de oficina mecanica, aplicando Domain-Driven Design (DDD).

Sistema de gestao de ordens de servico para uma oficina mecanica de medio porte. Permite cadastro de clientes e veiculos, criacao e acompanhamento de ordens de servico, gestao de estoque de pecas e insumos, e geracao de orcamentos.

## Pre-requisitos

> **Setup do zero?** Guias passo a passo por plataforma:
> [**Windows**](docs/setup/windows.md) - [**macOS**](docs/setup/macos.md) - [**Linux**](docs/setup/linux.md)

Quem ja tem o ambiente pronto:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gerenciador de dependencias e ambientes virtuais -- [ADR-014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md))
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
rebuilda imagens, aguarda o backend ficar saudavel e popula usuarios + dados
de demo (7 clientes, 10 veiculos, 8 servicos, 14 itens, 8 OS em estados
variados). **Apaga todos os dados do DB local.**

Pra pular o seed de demo (DB so com usuarios): `SKIP_DEMO=1 make reset-db`.
Derrubar tudo depois: `make down`. Apos `git pull`, prefira `make rebuild`
(forca rebuild das imagens sem apagar o DB).

> Se aparecer `failed to connect to the docker API ...docker.sock`, o socket
> nao esta no caminho padrao. Veja
> [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md) para
> configurar manualmente (Docker Desktop, Colima, Linux).

### URLs

| Servico | URL |
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
seed (uteis pra testar a tela publica `/acompanhamento`), veja
[`ui/seed-users.md`](ui/seed-users.md). Definicao em codigo:
`ui/config.py::_USUARIOS_SEED` (espelhada em `scripts/seed_usuarios.py`).

## Desenvolvimento

| Topico | Onde ler |
|---|---|
| Setup do zero (instalar uv, Docker, etc.) | [`docs/setup/`](docs/setup/) (Windows / macOS / Linux) |
| Loop de dev rapido (uvicorn hot-reload), checks locais, atualizar deps | [`docs/desenvolvimento.md`](docs/desenvolvimento.md) |
| Troubleshooting Docker (socket, Compose v2) | [`docs/setup/troubleshooting.md`](docs/setup/troubleshooting.md) |
| Debugging do dev loop (Colima, JWT_SECRET, 500s comuns) | [`docs/debugging-guide.md`](docs/debugging-guide.md) |
| UI NiceGUI (sandbox dev-only) | [`ui/README.md`](ui/README.md) |
| Worktrees paralelos (rodar 2+ branches sem conflito de portas) | [`docs/setup/worktrees-paralelos.md`](docs/setup/worktrees-paralelos.md) |

## UI de Simulacao

Sandbox em Python puro (NiceGUI) para testes manuais integrados da API.
**Dev-only** -- nao entra no Dockerfile do backend, nao e promovida a
entregavel. Coexiste com o Swagger UI (`/docs`): Swagger e referencia crua
da API, a UI de simulacao e sandbox integrado.

> **Nota arquitetural**: o servico `ui` aparece no `docker-compose.yml` mas
> nao no [diagrama C4 Container](docs/arquitetura/c4/c4-container.md), por
> ser componente auxiliar de desenvolvimento. Ver
> [issue #109](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/109)
> para a decisao em discussao sobre como sinalizar isso nos diagramas
> oficiais.

Guia completo de uso da UI (paginas, autenticacao, modo hibrido,
troubleshooting, contribuir): [`ui/README.md`](ui/README.md).

## Arquitetura

Monolito modular com DDD e Onion Architecture. Cada contexto delimitado e um modulo Python com 4 camadas:

```
interfaces/ -> aplicacao/ -> dominio/
     ^
infraestrutura/
```

Regra de dependencia estrita: camadas internas nunca importam camadas externas. Convencao de idioma hibrida (ADR-009): termos de negocio em portugues, padroes tecnicos em ingles.

### Contextos Delimitados

| Contexto | Classificacao | Descricao |
|---|---|---|
| Ordem de Servico | Principal | Ciclo de vida da OS, orcamentos, maquina de estados |
| Cliente + Veiculo | Suporte | Cadastro de clientes e veiculos vinculados |
| Catalogo de Servicos | Suporte | Servicos oferecidos pela oficina |
| Estoque | Principal | Pecas e insumos com controle de quantidade |
| Autenticacao | Generico | JWT, controle de acesso por papel |

## API

Documentacao interativa disponivel em `http://localhost:8000/docs` (Swagger UI).

| Grupo | Prefixo | Operacoes |
|---|---|---|
| Clientes | /api/v1/clientes | CRUD + veiculos |
| Servicos | /api/v1/servicos | CRUD catalogo |
| Estoque | /api/v1/estoque | CRUD + ajuste quantidade |
| Ordens de Servico | /api/v1/ordens-de-servico | Ciclo completo da OS |
| Autenticacao | /api/v1/autenticacao | Login, registro, refresh, logout |
| Saude | /api/v1/saude | Health check |

## Variaveis de Ambiente

| Variavel | Descricao | Padrao |
|---|---|---|
| DATABASE_URL | URL de conexao PostgreSQL | postgresql://pytstop:pytstop@postgres:5432/pytstop |
| JWT_SECRET | Chave secreta para tokens JWT | change-this-in-production |
| JWT_EXPIRATION_MINUTES | Tempo de expiracao do token | 30 |
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
- **Autenticacao**: JWT (HS256)
- **Testes**: pytest, testcontainers, polyfactory
- **Linting**: ruff, mypy (strict), import-linter
- **Containerizacao**: Docker, Docker Compose

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

Detalhes do workflow de dev (lint, mypy, bandit, atualizar dependencias):
[`docs/desenvolvimento.md`](docs/desenvolvimento.md).

## Code review automatizado pelo Claude

O repositorio tem dois workflows GitHub Actions que rodam o
[Claude Code Action](https://github.com/anthropics/claude-code-action)
oficial usando o secret `CLAUDE_CODE_OAUTH_TOKEN`:

| Workflow | Arquivo | Trigger | Perfil | Quando usar |
|---|---|---|---|---|
| **Claude Code Review** | `.github/workflows/claude-code-review.yml` | `pull_request` (`opened` / `reopened`) com **alvo `main`** | **Rapido**: `sonnet` + `--effort medium` + `--max-turns 30` | Review unica e automatica na abertura de PR pra main |
| **Claude On-Demand** | `.github/workflows/claude-on-demand.yml` | `issue_comment`, `pull_request_review_comment`, `workflow_dispatch` | **Profundo**: `opus` + `--effort max` + `--max-turns 50` | Re-revisar apos mudancas, pedir tarefa especifica, ou rodar em PRs entre branches de feature |

**Por que dois perfis**: o auto-review dispara em **todo** PR pra `main` --
otimizar pra latencia/custo (sonnet faz review competente em ~30-60s pra PR
pequeno; benchmark: PR #94 com opus/max levou 2m53s/$0.78 em 32 LOC). Quando
voce **explicitamente** pede review manual, o sinal e claro ("quero revisao
profunda mesmo que demore mais") -- dai o salto pra `opus` em `--effort max`,
que tambem da folga a sub-agents (`Task` tool) em PR grande. Os defaults
ficam centralizados em
[`.github/actions/claude/action.yml`](.github/actions/claude/action.yml) e o
`claude-on-demand.yml` sobrescreve via inputs.

**Politica de auto-review**: roda **uma vez** por PR para `main` (na abertura
ou reabertura). Pushes seguintes **nao** re-disparam -- isso e proposital pra
manter o custo previsivel. Se voce quiser nova review apos mudar codigo,
acione manual (proxima secao).

### Acionar manualmente

**Opcao A -- Comentar `@claude` no PR ou issue** (mais comum):

Cole no comentario do PR/issue:

```
@claude faca code review novamente focando em seguranca de auth
```

```
@claude tem alguma race condition em ui/cliente_api.py::_request?
```

A action detecta `@claude` no body do comentario e responde inline. Funciona
em PRs, em issues, e em comments de review (linha especifica). **So funciona
quando o workflow ja esta na branch `main`** (limitacao do GitHub: events
`issue_comment` sempre executam o workflow do default branch).

**Opcao B -- Run workflow manual via GitHub UI**:

1. Repo -> aba **Actions** -> **Claude On-Demand** (sidebar esquerda)
2. Clique em **Run workflow** (canto direito)
3. Em "Use workflow from", selecione a branch
4. Em "Instrucao para o Claude", digite o que quer (ex.: `review PR #81 focando em LGPD`)
5. **Run workflow**

**Opcao C -- `gh` CLI**:

```bash
gh workflow run claude-on-demand.yml \
  --ref feat/minha-branch \
  --field prompt="review este PR e foque em performance"
```

> ⚠️ **Limitacao do GitHub Actions**: tanto a Opcao B quanto a Opcao C
> precisam que o arquivo `claude-on-demand.yml` ja exista **na default
> branch (main)**. O `--ref` (ou o seletor "Use workflow from") so muda
> o checkout durante a execucao -- o lookup do workflow em si e sempre na
> main. Se a action ainda nao foi mergeada, o comando retorna `HTTP 404
> workflow not found on the default branch`.
>
> **Workaround antes do merge inicial**: re-acionar o auto-review fechando
> e reabrindo o PR (dispara o trigger `reopened`):
>
> ```bash
> gh pr close <numero> && gh pr reopen <numero>
> ```

### Custos e limites

- Cada run consome creditos do plano Claude Max do owner do token.
- Auto-review dispara **uma vez por PR para main** (na abertura/reabertura).
  Pushes seguintes nao re-disparam -- pra revisar de novo, use a secao
  "Acionar manualmente" acima.
- PRs entre branches de feature (target != main) nao disparam auto-review;
  use Run workflow manual ou `@claude` mention quando quiser.
- **Profundidade vs custo**: auto-review usa `--max-turns 30` (suficiente
  pra `track_progress` + 4 eixos do prompt em PR tipico); on-demand usa
  `--max-turns 50` pra dar folga a sub-agents (`Task` tool) em PR grande.
  Se um run ficar batendo no limite, sobe o `max_turns` na chamada do
  composite ao inves de subir o default global.
- Se quiser desabilitar o auto-review temporariamente, comente o bloco
  `on.pull_request` em `claude-code-review.yml` (deixa so quando precisar).

## Decisoes de Arquitetura (ADRs)

| ADR | Titulo | Status |
|---|---|---|
| [000](docs/arquitetura/adr/000-template.md) | Template MADR | -- |
| [001](docs/arquitetura/adr/001-framework-fastapi.md) | Framework FastAPI | Aceito |
| [002](docs/arquitetura/adr/002-banco-postgresql.md) | Banco PostgreSQL | Aceito |
| [003](docs/arquitetura/adr/003-arquitetura-ddd-onion.md) | Arquitetura DDD + Onion | Aceito |
| [004](docs/arquitetura/adr/004-autenticacao-jwt.md) | Autenticacao JWT HS256 | Aceito |
| [005](docs/arquitetura/adr/005-estrategia-testes.md) | Estrategia de testes | Aceito |
| [006](docs/arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo SQLAlchemy | Aceito |
| [007](docs/arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organizacao dos contextos delimitados | Aceito |
| [008](docs/arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista de estoque | Aceito |
| [009](docs/arquitetura/adr/009-decisao-de-idioma.md) | Modelo hibrido de idioma | Aceito |
| [010](docs/arquitetura/adr/010-validacao-documentos-brutils.md) | Validacao CPF/CNPJ/Placa com brutils | Proposta |
| [011](docs/arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de seguranca e analise estatica | Aceito |
| [012](docs/arquitetura/adr/012-licenciamento-software-sbom.md) | Licenciamento de software e SBOM | Aceito |
| [013](docs/arquitetura/adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd | Aceito |
| [014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes uv | Aceita |

## Documentacao

| Artefato | Descricao |
|---|---|
| [Domain Storytelling](docs/arquitetura/domain-storytelling/) | 5 cenarios no egon.io + entrevistas com especialistas de dominio |
| [Event Storming](docs/arquitetura/event-storming/) | 2 fluxos detalhados (ciclo da OS e gestao de estoque) |
| [Mapa de Contextos](docs/arquitetura/mapa-contextos.md) | 5 contextos delimitados com padroes de integracao |
| [Modelo de Dominio](docs/arquitetura/modelo-dominio.md) | Diagramas de classes por agregado |
| [Glossario](docs/requisitos/glossario.md) | Linguagem Ubiqua -- termos de dominio |
| [Entrega Fase 1](docs/entrega/entrega-fase-1.md) | Indice completo dos entregaveis |

## Equipe

| Nome | Discord |
|---|---|
| Joao Amaral | jbamaral |
| Allan Aurelio | [PREENCHER] |
| Carlos Silva | [PREENCHER] |
| Guilherme Sousa | [PREENCHER] |
| Nicolas Gerbi | [PREENCHER] |

## Curso

- **FIAP Pos Tech** -- Arquitetura de Software (15SOAT)
- **Prazo**: 5 de maio de 2026
- **Peso na nota**: 90%
