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
| Ordem de Serviço | Core | Ciclo de vida da OS, orçamentos, máquina de estados |
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

## Documentação

A documentação de planejamento e arquitetura está na pasta [`docs/`](docs/).

## Curso

- **FIAP Pós Tech** — Arquitetura de Software (15SOAT)
- **Prazo**: 5 de maio de 2026
- **Peso na nota**: 90%
