Load `../postech-ai-helper/ai/rules-index.md` (relative to workspace root) for the master index of all canonical rules.

## Context

Phase 1 project — Tech Challenge: mechanical workshop MVP backend using DDD.

- Stack: Python 3.12, FastAPI, SQLAlchemy 2.0 (imperative mapping), PostgreSQL 16
- 5 bounded contexts: Cliente+Veiculo, Catalogo de Servicos, Estoque, Ordem de Servico (core), Autenticacao (generic)
- DDD with Onion Architecture: dominio/, aplicacao/, infraestrutura/, interfaces/
- 80% test coverage on critical domains, JWT, Swagger, Docker

## Language — Hybrid Model (ADR-009)

Business terms (Ubiquitous Language) in **Portuguese** without accents; technical patterns in **English**.

- Domain entities/aggregates: `OrdemDeServico`, `Cliente`, `ItemEstoque` (PT)
- Base classes: `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent` (EN)
- Hybrid naming: `OrdemDeServicoRepository`, `OrcamentoAprovadoEvent`, `EstoquePort` (PT domain + EN suffix)
- Layer folders: `dominio/`, `aplicacao/`, `infraestrutura/`, `interfaces/` (PT)

## Workspace

All repos under `$(HOME)/git/fiap/postech-sw-architecture/`. Canonical rules in `postech-ai-helper/ai/`.
