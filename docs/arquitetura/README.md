# Guia de Documentacao de Arquitetura

> [↑ Raiz do projeto](../../README.md)

> **Versao**: 1.0 — Fase 1 MVP.

Classificação dos documentos de arquitetura do projeto conforme HLD (High-Level Design) e LLD (Low-Level Design).

## 1. Objetivo

Classificar os artefatos de arquitetura do projeto PytStop em HLD e LLD, facilitando a navegação por nível de detalhe. Gestores consultam HLD; desenvolvedores, LLD.

## 2. HLD — Visão Macro

Visão macro do sistema para stakeholders técnicos e não-técnicos: decisões estruturais, limites e comunicação entre blocos.

| Documento | Descricao |
|-----------|-----------|
| [RFC-001: Design do Sistema](rfc/rfc-001-design-do-sistema.md) | Visão geral da arquitetura, stack tecnológica e decisões fundamentais |
| [RFC-002: Infraestrutura e Deploy da Fase 2](rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) | Design integrado da infraestrutura da fase 2 — cluster kind, Terraform, CI/CD com deploy, HPA e notificação por e-mail |
| [C4 — Diagrama de Contexto](c4/c4-contexto.md) | Sistema como caixa única com atores e sistemas externos |
| [C4 — Diagrama de Container](c4/c4-container.md) | Principais blocos (FastAPI, PostgreSQL) e comunicação entre eles |
| [Mapa de Contextos](mapa-contextos.md) | Bounded contexts e padrões de integração (OHS, Cliente-Fornecedor) |
| [DAS — Documento de Aprovacao da Solucao](../entrega/documento-aprovacao-solucao.md) | Documento consolidado com todas as decisões para aprovação |

## 3. LLD — Detalhes de Implementação

Detalhes técnicos para desenvolvedores: estruturas internas, regras de negócio e decisões de implementação.

| Documento | Descricao |
|-----------|-----------|
| [C4 — Diagrama de Componentes](c4/c4-componentes.md) | Agregados e serviços por bounded context |
| [Modelo de Dominio](modelo-dominio.md) | Diagramas de classes por agregado |
| [ADRs (000-020)](adr/) | Decisões técnicas com contexto, alternativas e consequências |
| [Requisitos Funcionais e Nao-Funcionais](../requisitos/requisitos.md) | Especificações detalhadas de comportamento |
| [Estrategia de Testes](../qualidade/estrategia-testes.md) | Pirâmide de testes, TDD, test doubles, metas de cobertura |

## 4. Complementaridade HLD e LLD

HLD e LLD não são fases sequenciais -- são perspectivas complementares.

- **HLD**: *o que* o sistema faz e *como* os blocos se relacionam.
- **LLD**: *como* cada bloco funciona internamente e *por que* certas decisões foram tomadas.

Documentos vivos: mudanças em HLD podem exigir revisão de LLD, e restrições de implementação (LLD) podem exigir ajustes na visão macro (HLD).

## 5. Modelo C4

Abordagem hierárquica para documentação de arquitetura.

| Nivel | Descricao | Classificacao | Documento |
|-------|-----------|---------------|-----------|
| **Contexto** | Sistema como caixa única, atores e sistemas externos | HLD | [c4-contexto.md](c4/c4-contexto.md) |
| **Container** | Blocos de deploy (API, banco, etc.) e comunicação | HLD | [c4-container.md](c4/c4-container.md) |
| **Componente** | Agregados, serviços e portas por bounded context | LLD | [c4-componentes.md](c4/c4-componentes.md) |
| **Codigo** | Diagramas de classes e estruturas internas | LLD | [modelo-dominio.md](modelo-dominio.md) |

Níveis superiores (Contexto, Container) = HLD. Níveis inferiores (Componente, Codigo) = LLD.

## 6. ADRs

Decisões técnicas com contexto, alternativas e consequências. Três estados possíveis:

- **Proposta** — decisão em avaliação pela equipe
- **Aceita** — decisão aprovada e em vigor
- **Descontinuada / Substituída** — decisão que foi superada por outra

| ADR | Titulo | Status |
|-----|--------|--------|
| [000](adr/000-template.md) | Template de ADR | Template |
| [001](adr/001-framework-fastapi.md) | Usar FastAPI como framework web | Aceita |
| [002](adr/002-banco-postgresql.md) | Usar PostgreSQL 16 como banco de dados | Aceita |
| [003](adr/003-arquitetura-ddd-onion.md) | Usar DDD com Arquitetura Onion | Aceita |
| [004](adr/004-autenticacao-jwt.md) | Usar JWT HS256 para autenticação | Aceita |
| [005](adr/005-estrategia-testes.md) | Estratégia de testes com cobertura realista | Aceita |
| [006](adr/006-mapeamento-imperativo-sqlalchemy.md) | Mapeamento imperativo do SQLAlchemy para entidades de domínio | Aceita |
| [007](adr/007-organizacao-contextos-delimitados.md) | Organização dos contextos delimitados do domínio | Aceita |
| [008](adr/008-bloqueio-pessimista-estoque.md) | Bloqueio pessimista para reserva de estoque | Aceita |
| [009](adr/009-decisao-de-idioma.md) | Modelo híbrido de idioma para código e documentação | Aceita |
| [010](adr/010-validacao-documentos-brutils.md) | Usar brutils para validação de CPF, CNPJ e Placa | Aceita |
| [011](adr/011-pipeline-seguranca-analise-estatica.md) | Pipeline de Segurança e Análise Estática | Aceita |
| [012](adr/012-licenciamento-software-sbom.md) | Licenciamento de Software e SBOM | Aceita |
| [013](adr/013-testes-bdd-pytest-bdd.md) | Testes BDD com pytest-bdd e Gherkin | Proposta |
| [014](adr/014-gerenciador-pacotes-uv.md) | Gerenciador de pacotes e ambientes virtuais com uv | Aceita |
| [015](adr/fase2/015-arquitetura-alvo-fase-2.md) | Clean Architecture como arquitetura alvo da fase 2 | Proposta |
| [016](adr/fase2/016-plataforma-kubernetes.md) | kind como plataforma Kubernetes da fase 2 | Proposta |
| [017](adr/fase2/017-provisionamento-banco.md) | PostgreSQL no cluster como StatefulSet provisionado pelo Terraform | Proposta |
| [018](adr/fase2/018-notificacao-email.md) | Notificação de status por e-mail via adapter SMTP com Mailpit | Proposta |
| [019](adr/fase2/019-pipeline-cicd-deploy.md) | Pipeline de CI/CD com deploy em cluster kind efêmero no runner | Proposta |
| [020](adr/fase2/020-observabilidade-opentelemetry.md) | Observabilidade com OpenTelemetry e Jaeger em escopo mínimo condicional | Proposta |

---

> [↑ Raiz do projeto](../../README.md)
