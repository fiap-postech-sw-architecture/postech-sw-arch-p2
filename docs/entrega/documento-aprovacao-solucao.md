# Documento de Aprovação da Solução (DAS)

> [↑ Raiz do projeto](../../README.md) · [↑ Entrega](README.md)

> **Versão**: 1.0 — Fase 1 MVP.

Consolidação dos artefatos de arquitetura e engenharia do projeto PytStop.

---

## 1. Identificação do Projeto

| Campo | Valor |
|-------|-------|
| **Nome** | PytStop — Sistema de Gestão de Oficina Mecânica |
| **Versão** | 1.0-MVP (Fase 1) |
| **Data** | 2026-03-29 |
| **Grupo** | PytStop (15SOAT) |
| **Responsável** | João Amaral |

## 2. Contexto do Projeto

Oficina mecânica de médio porte que opera com fichas em papel e planilhas. O processo manual gera erros de transcrição, retrabalho e falta de rastreabilidade.

MVP back-end que digitaliza o ciclo da Ordem de Serviço — do recebimento do veículo até a entrega — com DDD. Abrange cadastro de clientes e veículos, catálogo de serviços, controle de estoque com reserva automática e acompanhamento público por placa.

## 3. Requisitos e Restrições

**Documento completo**: [requisitos.md](../requisitos/requisitos.md)

19 requisitos funcionais, 16 não-funcionais e 17 regras de negócio.

**Restrições do projeto**:

- Prazo de 8 semanas para entrega do MVP
- Equipe solo (desenvolvimento individual)
- Python 3.12 como versão mínima obrigatória
- Cobertura de testes acima de 80% nos domínios críticos

## 4. Diagramas de Arquitetura

Modelo C4 complementado por diagramas de domínio DDD:

| Diagrama | Descrição | Documento |
|----------|-----------|-----------|
| C4 — Contexto | Sistema, atores e sistemas externos | [c4-contexto.md](../arquitetura/c4/c4-contexto.md) |
| C4 — Container | Blocos de deploy e comunicação | [c4-container.md](../arquitetura/c4/c4-container.md) |
| C4 — Componentes | Agregados e serviços por bounded context | [c4-componentes.md](../arquitetura/c4/c4-componentes.md) |
| Mapa de Contextos | 5 bounded contexts e padrões de integração | [mapa-contextos.md](../arquitetura/mapa-contextos.md) |
| Modelo de Domínio | Diagramas de classes por agregado | [modelo-dominio.md](../arquitetura/modelo-dominio.md) |

## 5. Decisões Arquiteturais

ADRs no [diretório de ADRs](../arquitetura/adr/).

| ADR | Título | Status |
|-----|--------|--------|
| [000](../arquitetura/adr/000-template.md) | Template de ADR | Template |
| [001](../arquitetura/adr/001-framework-fastapi.md) | Usar FastAPI como framework web | Aceita |
| [002](../arquitetura/adr/002-banco-postgresql.md) | Usar PostgreSQL 16 como banco de dados | Aceita |
| [003](../arquitetura/adr/003-arquitetura-ddd-onion.md) | Usar DDD com Arquitetura Onion | Aceita |
| [004](../arquitetura/adr/004-autenticacao-jwt.md) | Usar JWT HS256 para autenticação | Aceita |
| [005](../arquitetura/adr/005-estrategia-testes.md) | Estratégia de testes com cobertura realista | Aceita |
| [006](../arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo do SQLAlchemy para entidades de domínio | Aceita |
| [007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) | Organização dos contextos delimitados do domínio | Aceita |
| [008](../arquitetura/adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista para reserva de estoque | Aceita |
| [009](../arquitetura/adr/009-decisao-de-idioma.md) | Modelo híbrido de idioma para código e documentação | Aceita |
| [010](../arquitetura/adr/010-validacao-documentos-brutils.md) | Usar brutils para validação de CPF, CNPJ e Placa | Aceita |
| [011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de Segurança e Análise Estática | Aceita |
| [012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Licenciamento de Software e SBOM | Aceita |
| [013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd e Gherkin | Proposta |
| [014](../arquitetura/adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes uv | Aceita |

## 6. Plano de Testes e Monitoramento

**Documento completo**: [Estratégia de Testes](../qualidade/estrategia-testes.md)
**Decisão relacionada**: [ADR-005 — Estratégia de testes](../arquitetura/adr/005-estrategia-testes.md)

pytest como framework de testes, testcontainers para integração com PostgreSQL real. Metas de cobertura:

- **Domínio**: 90% de cobertura (regras de negócio, agregados, value objects)
- **Aplicação**: 80% de cobertura (use cases, serviços de aplicação)
- **Infraestrutura/Interfaces**: 65% de cobertura (repositórios, controllers)

TDD para o domínio. BDD com pytest-bdd proposto para cenários de aceitação ([ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md)).

## 7. Modelo de Dados

**Documento completo**: [Modelo de Domínio](../arquitetura/modelo-dominio.md)

5 bounded contexts, 5 aggregate roots:

- **Cliente + Veículo**: `Cliente` como raiz, `Veiculo` como entidade filha
- **Catálogo de Serviços**: `Servico` como raiz
- **Estoque**: `ItemEstoque` como raiz
- **Ordem de Serviço**: `OrdemDeServico` como raiz (contexto principal)
- **Autenticação**: `Usuario` como raiz (contexto genérico)

Persistência via SQLAlchemy com mapeamento imperativo ([ADR-006](../arquitetura/adr/006-mapeamento-imperativo-sqlalchemy.md)). PostgreSQL 16 ([ADR-002](../arquitetura/adr/002-banco-postgresql.md)).

## 8. Documentação de API

**Acesso**: Swagger UI gerado automaticamente pelo FastAPI em `/docs`

47 endpoints sob `/api/v1/`. Paginação offset-based em listagens.

Recursos expostos por contexto:

- `/api/v1/clientes` e `/api/v1/clientes/{id}/veiculos` — cadastro e consulta
- `/api/v1/servicos` — catálogo de serviços
- `/api/v1/estoque` — gestão de peças e insumos
- `/api/v1/ordens-de-servico` — ciclo completo da OS
- `/api/v1/auth` — autenticação JWT
- `/api/v1/acompanhamento` — consulta pública por placa

Ver [inventário de endpoints](../requisitos/requisitos.md#inventário-de-endpoints-api) para a lista completa.

## 9. Manual de Instalação e Configuração

**Documento completo**: [README.md](../../README.md)

Execução via Docker Compose (CLI v2, subcomando `docker compose`):

```
docker compose up
```

12 variáveis de ambiente (banco, JWT, CORS, etc.) com valores padrão para desenvolvimento local. Migrações via Alembic na inicialização do container.

## 10. Plano de Continuidade e Backup

Prioriza reprodutibilidade e reversibilidade:

- **Reprodutibilidade**: Docker garante ambiente idêntico em qualquer máquina. Imagens versionadas no registry.
- **Migrações reversíveis**: Alembic permite rollback de migrações de banco com `alembic downgrade`.
- **Backup de dados**: PostgreSQL com `pg_dump` para snapshots periódicos. Restauração via `pg_restore`.
- **Monitoramento**: Logging estruturado via structlog ([RNF-013](../requisitos/requisitos.md)) com rastreabilidade por request_id.

## 11. Plano de Segurança e Conformidade

**Documentos completos**:
- [Plano de Segurança](../seguranca/plano-seguranca.md)
- [Relatório de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)

**Decisão relacionada**: [ADR-011 — Pipeline de Segurança](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)

Riscos do OWASP API Security Top 10 mapeados com mitigações por categoria. LGPD: encriptação de PII (RF-011) e consentimento explícito (RF-019) implementados no MVP.

Pipeline de segurança: análise estática (bandit), verificação de dependências (pip-audit) e auditoria de licenças ([ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md)).

## 12. Referências

### Documentos do Projeto

- [RFC-001: Design do Sistema](../arquitetura/rfc/rfc-001-design-do-sistema.md)
- [Requisitos](../requisitos/requisitos.md)
- [Estratégia de Testes](../qualidade/estrategia-testes.md)
- [Mapa de Contextos](../arquitetura/mapa-contextos.md)
- [Modelo de Domínio](../arquitetura/modelo-dominio.md)
- [Plano de Segurança](../seguranca/plano-seguranca.md)
- [Relatório de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)
- [Guia de Documentação de Arquitetura](../arquitetura/README.md)

### ADRs

- [ADR-001](../arquitetura/adr/001-framework-fastapi.md) a [ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md) — 14 decisões técnicas documentadas

### Diagramas C4

- [Contexto](../arquitetura/c4/c4-contexto.md) | [Container](../arquitetura/c4/c4-container.md) | [Componentes](../arquitetura/c4/c4-componentes.md)

### Disciplinas de Referência

- Doc-Arq-Solucoes Aula 01-02 — Classificação HLD/LLD
- Doc-Arq-Solucoes Aula 03 — Modelo C4
- Doc-Arq-Solucoes Aula 05 — ADRs e ciclo de vida
- Doc-Arq-Solucoes Aula 06 — Documento de Aprovação da Solução (DAS)

> [↑ Raiz do projeto](../../README.md) · [↑ Entrega](README.md)
