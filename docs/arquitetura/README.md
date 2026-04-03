# Guia de Documentacao de Arquitetura

> **Status**: DRAFT — documento em elaboracao, sujeito a revisao pela equipe PytStop.

Classificacao dos documentos de arquitetura do projeto conforme HLD (High-Level Design) e LLD (Low-Level Design).

## 1. Objetivo

Classificar os artefatos de arquitetura do projeto PytStop em HLD e LLD, facilitando a navegacao por nivel de detalhe. Gestores consultam HLD; desenvolvedores, LLD.

## 2. HLD — Visao Macro

Visao macro do sistema para stakeholders tecnicos e nao-tecnicos: decisoes estruturais, limites e comunicacao entre blocos.

| Documento | Descricao |
|-----------|-----------|
| [RFC-001: Design do Sistema](rfc/rfc-001-design-do-sistema.md) | Visao geral da arquitetura, stack tecnologica e decisoes fundamentais |
| [C4 — Diagrama de Contexto](c4/c4-contexto.md) | Sistema como caixa unica com atores e sistemas externos |
| [C4 — Diagrama de Container](c4/c4-container.md) | Principais blocos (FastAPI, PostgreSQL) e comunicacao entre eles |
| [Mapa de Contextos](mapa-contextos.md) | Bounded contexts e padroes de integracao (OHS, Cliente-Fornecedor) |
| [DAS — Documento de Aprovacao da Solucao](../entrega/documento-aprovacao-solucao.md) | Documento consolidado com todas as decisoes para aprovacao |

## 3. LLD — Detalhes de Implementacao

Detalhes tecnicos para desenvolvedores: estruturas internas, regras de negocio e decisoes de implementacao.

| Documento | Descricao |
|-----------|-----------|
| [C4 — Diagrama de Componentes](c4/c4-componentes.md) | Agregados e servicos por bounded context |
| [Modelo de Dominio](modelo-dominio.md) | Diagramas de classes por agregado |
| [ADRs (000-013)](adr/) | Decisoes tecnicas com contexto, alternativas e consequencias |
| [Requisitos Funcionais e Nao-Funcionais](../requisitos/requisitos.md) | Especificacoes detalhadas de comportamento |
| [Estrategia de Testes](../qualidade/estrategia-testes.md) | Piramide de testes, TDD, test doubles, metas de cobertura |

## 4. Complementaridade HLD e LLD

HLD e LLD nao sao fases sequenciais -- sao perspectivas complementares.

- **HLD**: *o que* o sistema faz e *como* os blocos se relacionam.
- **LLD**: *como* cada bloco funciona internamente e *por que* certas decisoes foram tomadas.

Documentos vivos: mudancas em HLD podem exigir revisao de LLD, e restricoes de implementacao (LLD) podem exigir ajustes na visao macro (HLD).

## 5. Modelo C4

Abordagem hierarquica para documentacao de arquitetura.

| Nivel | Descricao | Classificacao | Documento |
|-------|-----------|---------------|-----------|
| **Contexto** | Sistema como caixa unica, atores e sistemas externos | HLD | [c4-contexto.md](c4/c4-contexto.md) |
| **Container** | Blocos de deploy (API, banco, etc.) e comunicacao | HLD | [c4-container.md](c4/c4-container.md) |
| **Componente** | Agregados, servicos e portas por bounded context | LLD | [c4-componentes.md](c4/c4-componentes.md) |
| **Codigo** | Diagramas de classes e estruturas internas | LLD | [modelo-dominio.md](modelo-dominio.md) |

Niveis superiores (Contexto, Container) = HLD. Niveis inferiores (Componente, Codigo) = LLD.

## 6. ADRs

Decisoes tecnicas com contexto, alternativas e consequencias. Tres estados possiveis:

- **Proposta** — decisao em avaliacao pela equipe
- **Aceita** — decisao aprovada e em vigor
- **Descontinuada / Substituida** — decisao que foi superada por outra

| ADR | Titulo | Status |
|-----|--------|--------|
| [000](adr/000-template.md) | Template de ADR | Template |
| [001](adr/001-framework-fastapi.md) | Usar FastAPI como framework web | Aceita |
| [002](adr/002-banco-postgresql.md) | Usar PostgreSQL 16 como banco de dados | Aceita |
| [003](adr/003-arquitetura-ddd-onion.md) | Usar DDD com Arquitetura Onion | Aceita |
| [004](adr/004-autenticacao-jwt.md) | Usar JWT HS256 para autenticacao | Aceita |
| [005](adr/005-estrategia-testes.md) | Estrategia de testes com cobertura realista | Aceita |
| [006](adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo do SQLAlchemy para entidades de dominio | Aceita |
| [007](adr/007-organizacao-contextos-delimitados.md) | Organizacao dos contextos delimitados do dominio | Aceita |
| [008](adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista para reserva de estoque | Aceita |
| [009](adr/009-decisao-de-idioma.md) | Modelo hibrido de idioma para codigo e documentacao | Aceita |
| [010](adr/010-validacao-documentos-brutils.md) | Usar brutils para validacao de CPF, CNPJ e Placa | Aceita |
| [011](adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de Seguranca e Analise Estatica | Aceita |
| [012](adr/012-licenciamento-software-sbom.md) | Licenciamento de Software e SBOM | Aceita |
| [013](adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd e Gherkin | Proposta |
