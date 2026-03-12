# Tech Challenge — Fase 1

MVP de back-end para sistema de oficina mecânica, aplicando Domain-Driven Design (DDD).

## Descrição

Sistema de gestão de ordens de serviço para uma oficina mecânica de médio porte. Permite cadastro de clientes e veículos, criação e acompanhamento de ordens de serviço, gestão de estoque de peças e insumos, e geração de orçamentos.

## Stack

- **Linguagem**: Python 3.12
- **Framework**: FastAPI
- **Banco de dados**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (mapeamento imperativo)
- **Autenticação**: JWT (HS256)
- **Testes**: pytest, testcontainers, polyfactory
- **Linting**: ruff, mypy (strict), import-linter
- **Containerização**: Docker, Docker Compose

## Contextos Delimitados

| Contexto | Classificação | Descrição |
|---|---|---|
| Ordem de Serviço | Principal | Ciclo de vida da OS, orçamentos, máquina de estados |
| Cliente + Veículo | Suporte | Cadastro de clientes e veículos vinculados |
| Catálogo de Serviços | Suporte | Serviços oferecidos pela oficina |
| Estoque | Suporte | Peças e insumos com controle de quantidade |
| Autenticação | Genérico | JWT, controle de acesso por papel |

## Pré-requisitos

- Docker e Docker Compose
- Python 3.12 (para desenvolvimento local)

## Quick Start

```bash
docker-compose up
```

A API estará disponível em `http://localhost:8000/docs` (Swagger UI).

## Decisões de Arquitetura (ADR)

As decisões técnicas significativas do projeto estão registradas como
**Architecture Decision Records (ADR)** — um padrão de documentação que
captura o contexto, as alternativas avaliadas, a decisão tomada e suas
consequências. Usamos o formato [MADR 3.0](https://adr.github.io/madr/).

| ADR | Título | Status |
|---|---|---|
| [000](docs/arquitetura/adr/000-template.md) | Template MADR | — |
| [001](docs/arquitetura/adr/001-framework-fastapi.md) | Framework FastAPI | Aceito |
| [002](docs/arquitetura/adr/002-banco-postgresql.md) | Banco PostgreSQL | Aceito |
| [003](docs/arquitetura/adr/003-arquitetura-ddd-onion.md) | Arquitetura DDD + Onion | Aceito |
| [004](docs/arquitetura/adr/004-autenticacao-jwt.md) | Autenticação JWT HS256 | Aceito |
| [005](docs/arquitetura/adr/005-estrategia-testes.md) | Estratégia de testes | Aceito |
| [006](docs/arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo SQLAlchemy | Aceito |
| [007](docs/arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organização dos contextos delimitados | Aceito |
| [008](docs/arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista de estoque | Aceito |
| [009](docs/arquitetura/adr/009-decisao-de-idioma.md) | Modelo híbrido de idioma | Aceito |
| [010](docs/arquitetura/adr/010-resolver-tech-debt-em-f1.md) | Resolver tech debt em F1 via MVPs | Aceito |

## Documentação

A documentação de planejamento e arquitetura está na pasta [`docs/`](docs/).

## Curso

- **FIAP Pós Tech** — Arquitetura de Software (15SOAT)
- **Prazo**: 5 de maio de 2026
- **Peso na nota**: 90%
