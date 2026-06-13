# Dívida Técnica

> [↑ Raiz do projeto](../README.md)

> **Versão**: 1.1 — Fase 1 MVP + débitos assumidos no fechamento da fase 2.

Simplificações deliberadas cujo custo de correção é aceito para o escopo do MVP.

Funcionalidades que não serão implementadas no MVP estão classificadas como Could Have no [PRD](requisitos/prd.md). Requisitos que serão implementados estão nos respectivos RFs em [requisitos.md](requisitos/requisitos.md).

Classificação por tipo:

- **Deliberado**: assumido conscientemente pela equipe para acelerar entrega ou validar hipóteses
- **Acidental**: surge sem que a equipe perceba, por desconhecimento ou mudanças inesperadas
- **Planejado**: equipe sabe que a solução não é ideal, documenta e planeja pagar depois
- **Negligenciado**: débito ignorado por muito tempo, mesmo após identificação

## Itens Resolvidos

| # | Área | Descrição | Resolução |
|---|---|---|---|
| TD-001 | Segurança | Sem mecanismo de consentimento explícito LGPD | **Fechado** — Implementado no MVP via RF-019: endpoints `POST/DELETE /clientes/{id}/consentimento` com entidade `ConsentimentoCliente`. |

## Itens Abertos

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-002 | Domínio | Sem histórico de orçamentos (substituição total do JSONB) | Deliberado | Baixa | Baixo | Não | Estável | Orçamento existe como Value Object imutável, mas sem versionamento em array JSONB com timestamp. Funcionalidade parcial aceita. RF-017 (Could Have). |
| TD-003 | Infra | Sem CSP headers (Content-Security-Policy) | Deliberado | Baixa | Baixo | Não | Estável | Boa prática de segurança, mas sem front-end servido pela API o impacto é mínimo. Headers básicos (X-Content-Type-Options, HSTS) estão presentes (RNF-004). |
| TD-004 | API | Notificações via stub (LogNotificacaoAdapter) | Deliberado | Baixa | Baixo | Não | Estável | Decisão consciente: o sistema funciona sem notificações reais (push, email, SMS). O adapter de log permite evolução futura sem mudança no domínio. [ADR-003](arquitetura/adr/003-arquitetura-ddd-onion.md): inversão de dependência viabiliza a troca sem impacto no domínio. |
| TD-005 | Domínio | Orçamento JSONB sem índices GIN | Planejado | Baixa | Médio | Não | Crescente | Performance aceitável no MVP com volume baixo de dados. Índices GIN seriam otimização prematura sem métricas de produção. A ser reavaliado com dados reais. |
| TD-006 | Testes | Mutation testing como meta, não requisito hard | Deliberado | Baixa | Baixo | Não | Estável | Cobertura de linha (90%+) e branch (85%+) nos domínios principais já garante qualidade. Mutmut é bônus para validação adicional. [ADR-005](arquitetura/adr/005-estrategia-testes.md) documenta a estratégia. |

## DDD Tactical Compliance

Débitos aceitáveis no MVP relacionados à conformidade tática do DDD:

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-007 | Domínio | Value Objects com validação mínima | Deliberado | Baixa | Baixo | Não | Estável | `not-null` e tipo correto são obrigatórios. Validação completa de formato (ex: dígito verificador do CPF) é deferida para brutils ([ADR-010](arquitetura/adr/010-validacao-documentos-brutils.md)). |
| TD-008 | Domínio | Dispatch síncrono de domain events | Planejado | Média | Médio | Sim | Crescente | O mecanismo de dispatch é deferido (RF-018 Transactional Outbox, Could Have); o payload dos eventos não é — cada evento deve carregar `agregado_id`, `ocorrido_em` e campos alterados conforme `DomainEvent` base. |
| TD-009 | Domínio | Eventos mapeados no event storming sem emissão no código | Planejado | Baixa | Baixo | Não | Crescente | Eventos identificados mas ainda sem emissão: `ClienteCadastrado`, `VeiculoAdicionado`, `EstoqueReservado`, `EstoqueLiberado`, `ServicoCadastrado`. A serem implementados com o mecanismo de dispatch (TD-008). |

## Segurança e Qualidade

Débitos relacionados a segurança e qualidade de código.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-010 | Segurança | SonarQube não integrado no MVP (quality gate manual) | Deliberado | Baixa | Baixo | Não | Estável | Quality gate automatizado requer infraestrutura SonarQube. No MVP, análise estática local com ruff + bandit. Evolução para SonarCloud em fases posteriores. [ADR-011](arquitetura/adr/011-pipeline-seguranca-analise-estatica.md). |
| TD-011 | Segurança | Sem DAST automatizado (OWASP ZAP manual) | Deliberado | Média | Médio | Não | Estável | Teste dinâmico requer aplicação em execução e configuração de pipeline. No MVP, execução manual sob demanda. Automação planejada para CI quando pipeline estiver maduro. |
| TD-012 | Segurança | Sem SBOM automatizado no CI (geração manual) | Deliberado | Baixa | Baixo | Não | Estável | CycloneDX disponível via CLI, mas integração no CI requer configuração adicional. Geração manual por release no MVP. [ADR-012](arquitetura/adr/012-licenciamento-software-sbom.md). |
| TD-013 | Testes | Sem testes BDD/Gherkin no MVP (pytest-bdd planejado) | Deliberado | Baixa | Baixo | Não | Estável | Testes E2E com Gherkin em português agregam rastreabilidade para requisitos, mas requerem feature files e steps adicionais. Prioridade para testes unitários e de integração no MVP. [ADR-013](arquitetura/adr/013-testes-bdd-pytest-bdd.md). |
| TD-014 | Testes | Sem relatórios Allure no MVP (pytest-html como alternativa leve) | Deliberado | Baixa | Baixo | Não | Estável | Allure oferece relatórios visuais superiores, mas requer servidor dedicado. pytest-html atende necessidades do MVP com menor overhead. |

## Fase 2

Débitos assumidos durante a fase 2 (infra Kubernetes, CI/CD, observabilidade e evolução da API), registrados no fechamento da fase.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-015 | Infra | Corrida de migração com múltiplas réplicas (alembic no entrypoint) | Deliberado | Média | Médio | Sim | Estável | O `entrypoint.sh` roda `alembic upgrade head` no boot; duas réplicas subindo juntas poderiam disputar a migração. Mitigação atual: rollout inicial com réplica única (`replicas: 1` explícito no Deployment) antes de o HPA escalar. Evolução: Job dedicado de migração no deploy ([ADR-019](arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)). |
| TD-016 | Infra | Rate limiter slowapi in-memory por pod | Deliberado | Média | Médio | Sim | Crescente | RNF-024 atendido parcialmente: o contador do slowapi vive na memória de cada pod, então sob HPA o limite efetivo é multiplicado pelo número de réplicas. Aceitável no cluster de demo; evolução é backend compartilhado (Redis) quando houver mais de uma réplica estável. |
| TD-017 | Observabilidade | Traces capturam a query string do acompanhamento (CPF/placa) | Deliberado | Média | Médio | Sim | Estável | A instrumentação FastAPI do OTel registra `url.query` nos spans, e a consulta pública de acompanhamento passa `placa`/`documento` como query params — PII chega ao Jaeger. Aceito porque o OTel é opt-in de demo (default OFF). Se sair da demo, mitigar com `server_request_hook` redigindo a query ([ADR-020](arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)). |
| TD-018 | Infra | `db-image/` no GHCR ainda com imagens da fase 1 | Deliberado | Baixa | Baixo | Não | Estável | As imagens publicadas do fast-check não contêm RF-020..024 nem Mailpit; o README já rebaixa o atalho a "demo da fase 1" com aviso explícito. Republicar como `-p2` é opcional futuro (pós-banca). |
| TD-019 | Arquitetura | `aplicacao → infraestrutura` na autenticação fora do contrato forbidden | Deliberado | Baixa | Baixo | Não | Estável | `src/autenticacao/aplicacao/use_cases.py` importa `password_hasher`/`jwt_service` da infraestrutura do próprio contexto, o que impede estender o contrato forbidden do import-linter para proibir `aplicacao → infraestrutura` globalmente (finding do I1). O domínio segue protegido; corrigir exige extrair ports para o hasher e o JWT. |
| TD-020 | UI | Kanban da `ui/` não mostra OS encerradas por default pós RF-023 | Deliberado | Baixa | Baixo | Não | Estável | A listagem default da API passou a excluir logicamente FINALIZADA/ENTREGUE/CANCELADA (RF-023) e o cliente da `ui/` (dev-only) não passa `incluir_encerradas=true`, então as colunas de encerradas ficam vazias (gap §4). Adaptar a UI é evolução futura. |

## Considerações de Complexidade Algorítmica

Complexidade das operações principais do sistema.

| Operação | Complexidade | Estrutura | Justificativa |
|---|---|---|---|
| Bloqueio pessimista de estoque | O(n log n) ordenação + O(n) reserva | Array de `item_id` ordenado | Ordenação previne deadlocks ([ADR-008](arquitetura/adr/008-bloqueio-pessimista-estoque.md)). Custo aceitável para n < 100 itens por OS. |
| Transição de status da OS | O(1) por transição | Lookup direto (dict/enum) | `MaquinaDeStatus` valida transição em tempo constante. |
| Busca de OS por placa | O(log n) | Índice B-tree PostgreSQL | Índice na coluna `placa` garante busca logarítmica mesmo com volume alto. |
| Cálculo de média de execução | O(n) | Agregação SQL | `AVG()` sobre OS finalizadas. Aceitável com índice em `status` + `finalizado_em`. |
| Validação de CPF/CNPJ | O(1) | Cálculo aritmético | Dígitos verificadores calculados em tempo constante (brutils). |

Otimizações (índices GIN para JSONB -- TD-005, particionamento) a avaliar com dados reais de produção.

## Estratégia de Pagamento

1. **Boy Scout Rule**: cada alteração deixa o código melhor do que encontrou
2. **Refatorações incrementais**: melhorias técnicas nos sprints regulares, como parte do backlog
3. **Sprint técnico**: negociar com o PO para débitos de maior impacto (TD-008, TD-011)
4. **ADRs como prevenção**: decisões registradas em ADR ([ADR-001](arquitetura/adr/001-framework-fastapi.md) a [ADR-013](arquitetura/adr/013-testes-bdd-pytest-bdd.md)) evitam débitos invisíveis
5. **Métricas de fluxo**: lead time, cycle time e taxa de falhas para detectar crescimento do débito

> [↑ Raiz do projeto](../README.md)
