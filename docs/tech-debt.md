# Dívida Técnica

> [↑ Raiz do projeto](../README.md)

> **Versão**: 1.2 — Reconciliado com o código em 2026-06-22: TD-003 e TD-017 fechados (já implementados); TD-002/004/005/008/009/016 corrigidos para refletir o estado real do código.

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
| TD-020 | UI | Listagem da `ui/` não mostrava OS encerradas por default pós RF-023 | **Fechado** — PR #28: a `ui/` ganhou o toggle "Mostrar encerradas" (passa `incluir_encerradas`), os badges passam a exibir `situacao` (RF-021) e o dialog de nova OS aceita serviços/peças inline (RF-020). |
| TD-012 | Segurança | Sem SBOM automatizado no CI (geração manual) | **Fechado** — job `sbom` no [ci.yml](../.github/workflows/ci.yml) gera o SBOM CycloneDX a partir do lockfile a cada run e publica como artefato; alvo `make sbom` para geração local ([ADR-012](arquitetura/adr/012-licenciamento-software-sbom.md)). |
| TD-003 | Infra | Sem CSP headers (Content-Security-Policy) | **Fechado** — `SecurityHeadersMiddleware` aplica `Content-Security-Policy: default-src 'none'` em toda resposta (exceto as rotas de docs do Swagger/ReDoc, que precisam de inline scripts), além de `X-Frame-Options: DENY`, HSTS, `X-Content-Type-Options: nosniff` e `Cache-Control: no-store` ([middleware.py](../src/compartilhado/interfaces/middleware.py)); coberto por `tests/unitarios/test_security.py` e `tests/unitarios/compartilhado/test_middleware.py`. |
| TD-017 | Observabilidade | Traces capturavam a query string (CPF/placa) — PII no OTel | **Fechado** (#34) — `_redigir_pii_da_span` (server_request_hook do `FastAPIInstrumentor`) redige `url.query` e remove a query de `http.target`/`url.path` antes do export dos spans ([observability.py](../src/compartilhado/infraestrutura/observability.py)). |

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-002 | Domínio | Sem histórico de orçamentos (snapshot único substitui o anterior) | Deliberado | Baixa | Baixo | Não | Estável | Orçamento é um Value Object imutável persistido como snapshot único na coluna `orcamento_json` — cada novo orçamento substitui o anterior, sem versionamento nem timestamp. Funcionalidade parcial aceita. RF-017 (Could Have). |
| TD-004 | API | Sem notificações push/SMS (e-mail já implementado) | Deliberado | Baixa | Baixo | Não | Estável | RF-024 entregou notificação real por **e-mail** (`EmailPort` + `SmtpEmailAdapter`; Mailpit no compose). Push e SMS seguem fora do escopo do MVP; a inversão de dependência ([ADR-003](arquitetura/adr/003-arquitetura-ddd-onion.md)) permite adicioná-los sem tocar no domínio. |
| TD-005 | Domínio | Orçamento em coluna Text, sem consulta estruturada nem índice | Planejado | Baixa | Médio | Não | Crescente | O snapshot do orçamento é persistido como **Text** (`orcamento_json`), não `jsonb` — logo não há query estruturada nem índice GIN. Aceitável no MVP (o orçamento é lido junto da OS, nunca filtrado). Evolução só se surgir necessidade real: migrar a coluna para `jsonb` e então indexar com GIN. |
| TD-006 | Testes | Mutation testing como meta, não requisito hard | Deliberado | Baixa | Baixo | Não | Estável | Cobertura de linha (90%+) e branch (85%+) nos domínios principais já garante qualidade. Mutmut é bônus para validação adicional. [ADR-005](arquitetura/adr/005-estrategia-testes.md) documenta a estratégia. |

## DDD Tactical Compliance

Débitos aceitáveis no MVP relacionados à conformidade tática do DDD:

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-007 | Domínio | Value Objects com validação mínima | Deliberado | Baixa | Baixo | Não | Estável | `not-null` e tipo correto são obrigatórios. Validação completa de formato (ex: dígito verificador do CPF) é deferida para brutils ([ADR-010](arquitetura/adr/010-validacao-documentos-brutils.md)). |
| TD-008 | Domínio | Dispatch de domain events síncrono e in-process (sem outbox) | Planejado | Média | Médio | Sim | Estável | O `EventDispatcher` ([aplicacao/dispatcher.py](../src/ordem_servico/aplicacao/dispatcher.py)) já despacha os eventos de domínio de forma síncrona e in-process, pós-commit. O que segue deferido é o **Transactional Outbox** (RF-018, Could Have) para entrega assíncrona e durável; sob falha de handler a entrega não é re-tentada. O payload já segue o `DomainEvent` base (`agregado_id`, `ocorrido_em`). |
| TD-009 | Domínio | Dois eventos de criação do event storming sem classe nem emissão | Planejado | Baixa | Baixo | Não | Estável | A maioria dos eventos já é emitida via `_registrar_evento` e despachada (TD-008): `VeiculoAdicionadoEvent`, `EstoqueReservadoEvent`, `EstoqueLiberadoEvent` (além de `ClienteDesativadoEvent`/`ClienteAtualizadoEvent`). Faltam apenas os eventos de criação `ClienteCadastrado` e `ServicoCadastrado`, que nunca chegaram a ser implementados como classes. |

## Segurança e Qualidade

Débitos relacionados a segurança e qualidade de código.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-010 | Segurança | SonarQube não integrado no MVP (quality gate manual) | Deliberado | Baixa | Baixo | Não | Estável | Quality gate automatizado requer infraestrutura SonarQube. No MVP, análise estática local com ruff + bandit. Evolução para SonarCloud em fases posteriores. [ADR-011](arquitetura/adr/011-pipeline-seguranca-analise-estatica.md). |
| TD-011 | Segurança | Sem DAST automatizado (OWASP ZAP manual) | Deliberado | Média | Médio | Não | Estável | Teste dinâmico requer aplicação em execução e configuração de pipeline. No MVP, execução manual sob demanda. Automação planejada para CI quando pipeline estiver maduro. |
| TD-013 | Testes | Sem testes BDD/Gherkin no MVP (pytest-bdd planejado) | Deliberado | Baixa | Baixo | Não | Estável | Testes E2E com Gherkin em português agregam rastreabilidade para requisitos, mas requerem feature files e steps adicionais. Prioridade para testes unitários e de integração no MVP. [ADR-013](arquitetura/adr/013-testes-bdd-pytest-bdd.md). |
| TD-014 | Testes | Sem relatórios Allure no MVP (pytest-html como alternativa leve) | Deliberado | Baixa | Baixo | Não | Estável | Allure oferece relatórios visuais superiores, mas requer servidor dedicado. pytest-html atende necessidades do MVP com menor overhead. |

## Fase 2

Débitos assumidos durante a fase 2 (infra Kubernetes, CI/CD, observabilidade e evolução da API), registrados no fechamento da fase.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-015 | Infra | Corrida de migração com múltiplas réplicas (alembic no entrypoint) | Deliberado | Média | Médio | Sim | Estável | O `entrypoint.sh` roda `alembic upgrade head` no boot; duas réplicas subindo juntas poderiam disputar a migração. Mitigação atual: rollout inicial com réplica única (`replicas: 1` explícito no Deployment) antes de o HPA escalar. Evolução: Job dedicado de migração no deploy ([ADR-019](arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)). Rastreado em #33. |
| TD-016 | Infra | Rate limiter slowapi in-memory por pod | Deliberado | Média | Médio | Sim | Crescente | A metade do RNF-024 relativa ao **pool de conexões** já foi entregue (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` em [database.py](../src/compartilhado/infraestrutura/database.py), #32 fechada). Resta o **rate limiter**: o contador do slowapi vive na memória de cada pod ([middleware.py](../src/compartilhado/interfaces/middleware.py)), então sob HPA o limite efetivo é multiplicado pelo número de réplicas. Aceitável no cluster de demo; evolução é backend compartilhado (Redis via `storage_uri`) com mais de uma réplica estável. Rastreado em #31. |
| TD-018 | Infra | `db-image/` no GHCR ainda com imagens da fase 1 | Deliberado | Baixa | Baixo | Não | Estável | As imagens publicadas do fast-check não contêm RF-020..024 nem Mailpit; o README já rebaixa o atalho a "demo da fase 1" com aviso explícito. Republicar como `-p2` é opcional futuro (pós-banca). |
| TD-019 | Arquitetura | `aplicacao → infraestrutura` na autenticação fora do contrato forbidden | Deliberado | Baixa | Baixo | Não | Estável | `src/autenticacao/aplicacao/use_cases.py` importa `password_hasher`/`jwt_service` da infraestrutura do próprio contexto, o que impede estender o contrato forbidden do import-linter para proibir `aplicacao → infraestrutura` globalmente (finding do I1). O domínio segue protegido; corrigir exige extrair ports para o hasher e o JWT. Rastreado em #35. |

## Considerações de Complexidade Algorítmica

Complexidade das operações principais do sistema.

| Operação | Complexidade | Estrutura | Justificativa |
|---|---|---|---|
| Bloqueio pessimista de estoque | O(n log n) ordenação + O(n) reserva | Array de `item_id` ordenado | Ordenação previne deadlocks ([ADR-008](arquitetura/adr/008-bloqueio-pessimista-estoque.md)). Custo aceitável para n < 100 itens por OS. |
| Transição de status da OS | O(1) por transição | Lookup direto (dict/enum) | `MaquinaDeStatus` valida transição em tempo constante. |
| Busca de OS por placa | O(log n) | Índice B-tree PostgreSQL | Índice na coluna `placa` garante busca logarítmica mesmo com volume alto. |
| Cálculo de média de execução | O(n) | Agregação SQL | `AVG()` sobre OS finalizadas. Aceitável com índice em `status` + `finalizado_em`. |
| Validação de CPF/CNPJ | O(1) | Cálculo aritmético | Dígitos verificadores calculados em tempo constante (brutils). |

Otimizações (migrar `orcamento_json` de Text para `jsonb` + índice GIN -- TD-005, particionamento) a avaliar com dados reais de produção.

## Estratégia de Pagamento

1. **Boy Scout Rule**: cada alteração deixa o código melhor do que encontrou
2. **Refatorações incrementais**: melhorias técnicas nos sprints regulares, como parte do backlog
3. **Sprint técnico**: negociar com o PO para débitos de maior impacto (TD-008, TD-011)
4. **ADRs como prevenção**: decisões registradas em ADR ([ADR-001](arquitetura/adr/001-framework-fastapi.md) a [ADR-013](arquitetura/adr/013-testes-bdd-pytest-bdd.md)) evitam débitos invisíveis
5. **Métricas de fluxo**: lead time, cycle time e taxa de falhas para detectar crescimento do débito

> [↑ Raiz do projeto](../README.md)
