<p align="center">
  <img src="logo-pytstop.png" width="512" alt="PytStop">
</p>

# PytStop -- Tech Challenge Fase 1

MVP de back-end para sistema de oficina mecanica, aplicando Domain-Driven Design (DDD).

Sistema de gestao de ordens de servico para uma oficina mecanica de medio porte. Permite cadastro de clientes e veiculos, criacao e acompanhamento de ordens de servico, gestao de estoque de pecas e insumos, e geracao de orcamentos.

## Pre-requisitos

- Python 3.12+
- Docker 24+ e Docker Compose v2
- Git

## Quick Start

```bash
git clone https://github.com/soat-architecture/postech-sw-arch-p1.git
cd postech-sw-arch-p1
docker compose up -d
# Aguardar o banco inicializar (~10s)
# Acessar: http://localhost:8000/docs (Swagger UI)
```

## Desenvolvimento Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

### Checks locais (espelham o CI)

```bash
make check      # lint + mypy + bandit + testes unitarios
make test-integ # testes de integracao (requer Docker)
make test-all   # todos os 900+ testes
make format     # auto-formata codigo
make all        # format + check + integracao
```

Ao rodar `pytest` diretamente, ruff/mypy/bandit executam automaticamente antes dos testes. Para pular os pre-checks: `pytest --no-lint`.

### Docker no macOS com Colima

Se usa [Colima](https://github.com/abersheeky/colima) como runtime Docker, configure no `~/.zshrc`:

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_RYUK_DISABLED=true
```

Essas variaveis sao necessarias para o testcontainers (testes de integracao) encontrar o socket do Docker. Abra um novo terminal ou execute `source ~/.zshrc` para aplicar.

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
