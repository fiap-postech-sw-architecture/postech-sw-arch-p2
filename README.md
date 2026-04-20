<p align="center">
  <img src="logo-pytstop.png" width="512" alt="PytStop">
</p>

# PytStop -- Tech Challenge Fase 1

MVP de back-end para sistema de oficina mecanica, aplicando Domain-Driven Design (DDD).

Sistema de gestao de ordens de servico para uma oficina mecanica de medio porte. Permite cadastro de clientes e veiculos, criacao e acompanhamento de ordens de servico, gestao de estoque de pecas e insumos, e geracao de orcamentos.

## Pre-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gerenciador de dependencias e ambientes virtuais) — veja [ADR-014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) (Proposta, em discussao). Fallback com `venv + pip` documentado na secao Desenvolvimento Local.
- Docker 24+ e Docker Compose v2
- Git

## Quick Start

```bash
git clone https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1.git
cd postech-sw-arch-p1
```

Em seguida, escolha **uma** das alternativas equivalentes para subir o ambiente:

**Automatica** — detecta o socket do Docker e configura `DOCKER_HOST` para voce:

```bash
make up    # derrubar: make down
```

`make up` executa `scripts/docker-check.sh` (Docker Desktop, Colima, `/var/run`) antes de rodar `docker compose up -d`.

**Manual** — se voce prefere controlar `DOCKER_HOST` explicitamente:

```bash
docker compose up -d    # derrubar: docker compose down
```

Se aparecer `failed to connect to the docker API ...docker.sock`, o socket nao esta no caminho padrao; consulte a secao [Troubleshooting: Docker socket](#troubleshooting-docker-socket) abaixo para configurar manualmente.

Apos subir o ambiente:

- Aguarde o banco inicializar (~10s)
- Acesse http://localhost:8000/docs (Swagger UI)

### Troubleshooting: Docker socket

Se ao rodar `docker compose up -d` aparecer o erro:

```
failed to connect to the docker API at unix:///Users/<user>/.docker/run/docker.sock
```

O `docker compose` nao esta encontrando o socket do Docker. O caminho `~/.docker/run/docker.sock` e o padrao que o Docker configura no seu context, mas ele nem sempre existe. Abaixo estao as opcoes de correcao dependendo do seu ambiente.

#### Opcao 1 — Docker Desktop: habilitar o socket padrao

O Docker Desktop (4.13+) so cria o socket em `~/.docker/run/` se uma opcao estiver habilitada. Abra **Docker Desktop > Settings > Advanced** e marque:

> **"Allow the default Docker socket to be used (requires password)"**

Reinicie o Docker Desktop e rode `docker compose up -d` novamente. Essa e a solucao mais simples — nao exige variavel de ambiente nem alteracao no projeto.

#### Opcao 2 — Docker Desktop: apontar para o socket alternativo

Se preferir nao habilitar a opcao acima, o Docker Desktop sempre cria um socket em `~/.docker/desktop/docker.sock`. Basta exportar `DOCKER_HOST` no `~/.zshrc` (ou `~/.bashrc`):

```bash
export DOCKER_HOST="unix://${HOME}/.docker/desktop/docker.sock"
```

Execute `source ~/.zshrc` para aplicar no terminal atual.

#### Opcao 3 — Colima

Se usa [Colima](https://github.com/abiosoft/colima) como runtime Docker em vez do Docker Desktop, configure no `~/.zshrc`:

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_RYUK_DISABLED=true
```

`DOCKER_HOST` e necessario para que `docker compose` e o testcontainers encontrem o socket do Docker. `TESTCONTAINERS_RYUK_DISABLED` evita erros nos testes de integracao. Execute `source ~/.zshrc` ou abra um novo terminal para aplicar.

#### Linux

Verifique se o servico Docker esta ativo: `sudo systemctl start docker`.

## Desenvolvimento Local

Instale o [`uv`](https://docs.astral.sh/uv/getting-started/installation/) uma vez (qualquer uma das alternativas):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
# ou: brew install uv
# ou: pipx install uv
```

Em seguida, instale as dependencias do projeto a partir do lockfile:

```bash
uv sync --extra test --frozen  # usa versoes exatas fixadas em uv.lock
```

`--frozen` garante que a resolucao nao altere `uv.lock`; se o lockfile estiver desatualizado em relacao a `pyproject.toml`, o comando falha e o bump precisa ser feito explicitamente (veja [Atualizando dependencias](#atualizando-dependencias) abaixo). Sem `--frozen`, `uv sync` reconcilia o lockfile automaticamente — util em primeiras instalacoes, mas evite em CI e commits do dia a dia.

Alternativa sem `uv` (pip + venv tradicional, enquanto a [ADR-014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) esta em discussao):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

Este fluxo nao consome `uv.lock` (pip resolve versoes novamente), entao pode divergir do ambiente do CI/producao. Use apenas se `uv` nao estiver disponivel.

### Loop de desenvolvimento rapido (uvicorn com hot reload)

Para iterar rapidamente sem rebuilds do container da aplicacao, rode apenas o Postgres via `docker compose` e o FastAPI local com `--reload`:

```bash
cp .env.dev.example .env.dev           # (opcional) customize credenciais/porta
docker compose up -d postgres          # Postgres na porta 5432
uv run alembic upgrade head            # aplica migrations (so na primeira vez)
./scripts/run-dev.sh                   # uvicorn em http://localhost:8001 com reload
```

`uv run <cmd>` executa no ambiente criado por `uv sync` sem exigir `source .venv/bin/activate`. Se preferir o fluxo tradicional, o equivalente e `.venv/bin/alembic upgrade head`.

Os defaults do `scripts/run-dev.sh` (`DATABASE_URL` apontando para `localhost:5432`, `JWT_SECRET` de dev com ≥32 bytes, etc.) funcionam sem configuracao adicional. Voce so precisa do `.env.dev` se quiser sobrescrever algo (por exemplo, `UVICORN_PORT=9000`) sem editar o script. Ao terminar, `docker compose down -v` encerra o Postgres.

Usuarios com [Claude Code](https://docs.claude.com/en/docs/claude-code) podem iniciar os servidores diretamente via `.claude/launch.json` (`preview_start`):

- `FastAPI (uvicorn dev server)` -- roda `scripts/run-dev.sh` na porta 8001
- `PostgreSQL (docker compose)` -- sobe apenas o Postgres na porta 5432
- `Full stack (docker compose)` -- sobe app + banco juntos na porta 8000

Consulte [`docs/debugging-guide.md`](docs/debugging-guide.md) para troubleshooting (socket Docker no Colima, JWT_SECRET, 500s comuns, verificacao end-to-end).

### Checks locais (espelham o CI)

```bash
make check      # lint + mypy + bandit + testes unitarios
make test-integ # testes de integracao (requer Docker)
make test-all   # todos os 970+ testes
make format     # auto-formata codigo
make all        # format + check + integracao
```

Ao rodar `pytest` diretamente, ruff/mypy/bandit executam automaticamente antes dos testes. Para pular os pre-checks: `pytest --no-lint`.

### Atualizando dependencias

O `uv.lock` fixa versoes exatas e hashes SHA-256 de todas as dependencias (diretas e transitivas). Atualizacoes sao **sempre explicitas** — nunca acontecem durante `uv sync --frozen`. Use os comandos abaixo conforme a intencao:

| Intencao | Comando | O que acontece |
|---|---|---|
| Reinstalar o que esta em `uv.lock` (fluxo diario) | `uv sync --extra test --frozen` | Nenhuma mudanca em `uv.lock`; falha se o lockfile estiver inconsistente com `pyproject.toml` |
| Atualizar **todas** as transitivas dentro dos ranges de `pyproject.toml` | `uv lock --upgrade && uv sync --extra test` | Regenera `uv.lock` no patch/minor mais novo permitido pelos ranges; commita o `uv.lock` junto |
| Atualizar **uma** dependencia especifica | `uv lock --upgrade-package <nome> && uv sync --extra test` | So bumpa `<nome>` (e suas transitivas); util para patches de seguranca pontuais |
| Adicionar nova dependencia de producao | `uv add <pacote>` | Atualiza `pyproject.toml` **e** `uv.lock`; commita ambos |
| Adicionar dependencia so para testes | `uv add --optional test <pacote>` | Atualiza `[project.optional-dependencies].test` + lockfile |
| Remover dependencia | `uv remove <pacote>` | Limpa `pyproject.toml` e `uv.lock` |
| Subir um range (ex.: `fastapi>=0.115` → `>=0.120`) | Edite `pyproject.toml`, depois `uv lock && uv sync --extra test` | Necessario quando o upgrade exige relaxar o range; review manual obrigatorio |
| Ver o que mudaria sem aplicar | `uv lock --upgrade --dry-run` | Mostra o diff de `uv.lock` sem escrever o arquivo |
| Auditoria de vulnerabilidades | `uv run --with pip-audit pip-audit` | Roda `pip-audit` em um ambiente efemero sem poluir o `.venv` |

**Checklist apos qualquer upgrade** (antes de abrir a PR):

1. `uv sync --extra test --frozen` — confirma que `uv.lock` resolve sem tocar nada.
2. `make check` (lint + mypy + bandit + unitarios) — nenhuma regressao de tipo/estilo/segurancia.
3. `make test-integ` — integracao com Postgres real sob as novas versoes.
4. `uv run --with pip-audit pip-audit` — sem CVEs de severidade alta ou critica nas novas versoes.
5. Commite `pyproject.toml` (se mudou) e `uv.lock` juntos, com mensagem do tipo `chore(deps): bump <pacote> to <versao>` ou `chore(deps): monthly lock refresh`.

Para um refresh periodico completo (recomendado mensalmente ou apos qualquer CVE relevante): `uv lock --upgrade && uv sync --extra test && make all && uv run --with pip-audit pip-audit`.

### Docker Compose via Homebrew

O Quick Start usa `docker compose` (Compose v2 como plugin do Docker CLI). Com Docker via Homebrew, se aparecer `unknown command: docker compose`, use **uma** destas opcoes:

1. **Registar o diretorio de plugins do Homebrew** (mantem `brew upgrade docker-compose`): adicione em `~/.docker/config.json` a chave `cliPluginsExtraDirs` com o valor `["$(brew --prefix)/lib/docker/cli-plugins"]` usando o prefixo retornado por `brew --prefix` (`/opt/homebrew` em Apple Silicon, `/usr/local` em Intel; veja `brew info docker-compose`).

2. **Copiar o plugin para o diretorio padrao do usuario** (permite `brew uninstall docker-compose` e nao ter `docker-compose` no PATH): com a formula instalada, execute `mkdir -p ~/.docker/cli-plugins`, copie `$(brew --prefix docker-compose)/bin/docker-compose` para `~/.docker/cli-plugins/docker-compose`, `chmod +x`, confirme com `docker compose version`, e entao `brew uninstall docker-compose` se quiser apenas o subcomando `docker compose`.

Para atualizar o Compose na opcao 2, repita a copia apos `brew install docker-compose` ou baixe o binario em [releases do Compose](https://github.com/docker/compose/releases).

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

## Testes

```bash
make test          # unitarios com cobertura (80%+ obrigatorio)
make test-integ    # integracao com testcontainers + PostgreSQL
make test-all      # tudo (unitarios + integracao + e2e)

# Ou diretamente:
pytest tests/unitarios/ --no-lint -v          # unitarios
pytest tests/integracao/ --no-lint -v         # integracao (requer Docker)
pytest --cov=src --cov-report=html --no-lint  # com relatorio HTML
```

## Stack

- **Linguagem**: Python 3.12
- **Framework**: FastAPI
- **Banco de dados**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (mapeamento imperativo)
- **Autenticacao**: JWT (HS256)
- **Testes**: pytest, testcontainers, polyfactory
- **Linting**: ruff, mypy (strict), import-linter
- **Containerizacao**: Docker, Docker Compose

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
| [014](docs/arquitetura/adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes uv | Proposta |

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
