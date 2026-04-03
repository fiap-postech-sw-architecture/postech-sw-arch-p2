# Documento de Aprovacao da Solucao (DAS)

> **Status**: DRAFT — documento em elaboracao, sujeito a revisao pela equipe PytStop.

Consolidacao dos artefatos de arquitetura e engenharia do projeto PytStop.

---

## 1. Identificacao do Projeto

| Campo | Valor |
|-------|-------|
| **Nome** | PytStop — Sistema de Gestao de Oficina Mecanica |
| **Versao** | 1.0-MVP (Fase 1) |
| **Data** | 2026-03-29 |
| **Grupo** | PytStop (15SOAT) |
| **Responsavel** | Joao Amaral |

## 2. Contexto do Projeto

Oficina mecanica de medio porte que opera com fichas em papel e planilhas. O processo manual gera erros de transcricao, retrabalho e falta de rastreabilidade.

MVP back-end que digitaliza o ciclo da Ordem de Servico — do recebimento do veiculo ate a entrega — com DDD. Abrange cadastro de clientes e veiculos, catalogo de servicos, controle de estoque com reserva automatica e acompanhamento publico por placa.

## 3. Requisitos e Restricoes

**Documento completo**: [requisitos.md](../requisitos/requisitos.md)

19 requisitos funcionais, 16 nao-funcionais e 17 regras de negocio.

**Restricoes do projeto**:

- Prazo de 8 semanas para entrega do MVP
- Equipe solo (desenvolvimento individual)
- Python 3.12 como versao minima obrigatoria
- Cobertura de testes acima de 80% nos dominios criticos

## 4. Diagramas de Arquitetura

Modelo C4 complementado por diagramas de dominio DDD:

| Diagrama | Descricao | Documento |
|----------|-----------|-----------|
| C4 — Contexto | Sistema, atores e sistemas externos | [c4-contexto.md](../arquitetura/c4/c4-contexto.md) |
| C4 — Container | Blocos de deploy e comunicacao | [c4-container.md](../arquitetura/c4/c4-container.md) |
| C4 — Componentes | Agregados e servicos por bounded context | [c4-componentes.md](../arquitetura/c4/c4-componentes.md) |
| Mapa de Contextos | 5 bounded contexts e padroes de integracao | [mapa-contextos.md](../arquitetura/mapa-contextos.md) |
| Modelo de Dominio | Diagramas de classes por agregado | [modelo-dominio.md](../arquitetura/modelo-dominio.md) |

## 5. Decisoes Arquiteturais

ADRs no [diretorio de ADRs](../arquitetura/adr/).

| ADR | Titulo | Status |
|-----|--------|--------|
| [000](../arquitetura/adr/000-template.md) | Template de ADR | Template |
| [001](../arquitetura/adr/001-framework-fastapi.md) | Usar FastAPI como framework web | Aceita |
| [002](../arquitetura/adr/002-banco-postgresql.md) | Usar PostgreSQL 16 como banco de dados | Aceita |
| [003](../arquitetura/adr/003-arquitetura-ddd-onion.md) | Usar DDD com Arquitetura Onion | Aceita |
| [004](../arquitetura/adr/004-autenticacao-jwt.md) | Usar JWT HS256 para autenticacao | Aceita |
| [005](../arquitetura/adr/005-estrategia-testes.md) | Estrategia de testes com cobertura realista | Aceita |
| [006](../arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo do SQLAlchemy para entidades de dominio | Aceita |
| [007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organizacao dos contextos delimitados do dominio | Aceita |
| [008](../arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista para reserva de estoque | Aceita |
| [009](../arquitetura/adr/009-decisao-de-idioma.md) | Modelo hibrido de idioma para codigo e documentacao | Aceita |
| [010](../arquitetura/adr/010-validacao-documentos-brutils.md) | Usar brutils para validacao de CPF, CNPJ e Placa | Aceita |
| [011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de Seguranca e Analise Estatica | Aceita |
| [012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Licenciamento de Software e SBOM | Aceita |
| [013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd e Gherkin | Proposta |

## 6. Plano de Testes e Monitoramento

**Documento completo**: [Estrategia de Testes](../qualidade/estrategia-testes.md)
**Decisao relacionada**: [ADR-005 — Estrategia de testes](../arquitetura/adr/005-estrategia-testes.md)

pytest como framework de testes, testcontainers para integracao com PostgreSQL real. Metas de cobertura:

- **Dominio**: 90% de cobertura (regras de negocio, agregados, value objects)
- **Aplicacao**: 80% de cobertura (use cases, servicos de aplicacao)
- **Infraestrutura/Interfaces**: 65% de cobertura (repositorios, controllers)

TDD para o dominio. BDD com pytest-bdd proposto para cenarios de aceitacao ([ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md)).

## 7. Modelo de Dados

**Documento completo**: [Modelo de Dominio](../arquitetura/modelo-dominio.md)

5 bounded contexts, 5 aggregate roots:

- **Cliente + Veiculo**: `Cliente` como raiz, `Veiculo` como entidade filha
- **Catalogo de Servicos**: `Servico` como raiz
- **Estoque**: `ItemEstoque` como raiz
- **Ordem de Servico**: `OrdemDeServico` como raiz (contexto principal)
- **Autenticacao**: `Usuario` como raiz (contexto generico)

Persistencia via SQLAlchemy com mapeamento imperativo ([ADR-006](../arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md)). PostgreSQL 16 ([ADR-002](../arquitetura/adr/002-banco-postgresql.md)).

## 8. Documentacao de API

**Acesso**: Swagger UI gerado automaticamente pelo FastAPI em `/docs`

47 endpoints sob `/api/v1/`. Paginacao offset-based em listagens.

Recursos expostos por contexto:

- `/api/v1/clientes` e `/api/v1/clientes/{id}/veiculos` — cadastro e consulta
- `/api/v1/servicos` — catalogo de servicos
- `/api/v1/estoque` — gestao de pecas e insumos
- `/api/v1/ordens-de-servico` — ciclo completo da OS
- `/api/v1/auth` — autenticacao JWT
- `/api/v1/acompanhamento` — consulta publica por placa

Ver [inventario de endpoints](../requisitos/requisitos.md#inventário-de-endpoints-api) para a lista completa.

## 9. Manual de Instalacao e Configuracao

**Documento completo**: [README.md](../../README.md)

Execucao via Docker Compose:

```
docker-compose up
```

12 variaveis de ambiente (banco, JWT, CORS, etc.) com valores padrao para desenvolvimento local. Migracoes via Alembic na inicializacao do container.

## 10. Plano de Continuidade e Backup

Prioriza reprodutibilidade e reversibilidade:

- **Reprodutibilidade**: Docker garante ambiente identico em qualquer maquina. Imagens versionadas no registry.
- **Migracoes reversiveis**: Alembic permite rollback de migracoes de banco com `alembic downgrade`.
- **Backup de dados**: PostgreSQL com `pg_dump` para snapshots periodicos. Restauracao via `pg_restore`.
- **Monitoramento**: Logging estruturado via structlog ([RNF-013](../requisitos/requisitos.md)) com rastreabilidade por request_id.

## 11. Plano de Seguranca e Conformidade

**Documentos completos**:
- [Plano de Seguranca](../seguranca/plano-seguranca.md)
- [Relatorio de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)

**Decisao relacionada**: [ADR-011 — Pipeline de Seguranca](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)

Riscos do OWASP API Security Top 10 mapeados com mitigacoes por categoria. LGPD: encriptacao de PII (RF-011) implementada; consentimento deferido (TD-001).

Pipeline de seguranca: analise estatica (bandit), verificacao de dependencias (pip-audit) e auditoria de licencas ([ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md)).

## 12. Referencias

### Documentos do Projeto

- [RFC-001: Design do Sistema](../arquitetura/rfc/rfc-001-design-do-sistema.md)
- [Requisitos](../requisitos/requisitos.md)
- [Estrategia de Testes](../qualidade/estrategia-testes.md)
- [Mapa de Contextos](../arquitetura/mapa-contextos.md)
- [Modelo de Dominio](../arquitetura/modelo-dominio.md)
- [Plano de Seguranca](../seguranca/plano-seguranca.md)
- [Relatorio de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)
- [Guia de Documentacao de Arquitetura](../arquitetura/README.md)

### ADRs

- [ADR-001](../arquitetura/adr/001-framework-fastapi.md) a [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md) — 13 decisoes tecnicas documentadas

### Diagramas C4

- [Contexto](../arquitetura/c4/c4-contexto.md) | [Container](../arquitetura/c4/c4-container.md) | [Componentes](../arquitetura/c4/c4-componentes.md)

### Disciplinas de Referencia

- Doc-Arq-Solucoes Aula 01-02 — Classificacao HLD/LLD
- Doc-Arq-Solucoes Aula 03 — Modelo C4
- Doc-Arq-Solucoes Aula 05 — ADRs e ciclo de vida
- Doc-Arq-Solucoes Aula 06 — Documento de Aprovacao da Solucao (DAS)
