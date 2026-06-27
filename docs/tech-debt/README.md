# Dívida Técnica

> [↑ Raiz do projeto](../../README.md)

> **Versão**: 1.7 (2026-06-27) — reconciliação com o código: TD-009 fechado (eventos `ClienteCadastrado`/`ServicoCadastrado` implementados e emitidos via `_registrar_evento`); TD-007 reescrito (validação de dígito/formato via brutils já entregue — remanescente é só telefone/e-mail sem VO próprio); TD-010 nota o gate CodeQL local; estrutura agora separa explicitamente *Itens Resolvidos* (9) de *Itens Abertos* (13, em 4 grupos). Versão 1.6 — TD-008 resolvido (Transactional Outbox/RF-018, PR #56); adicionados TD-021 (relay HA/fencing) e TD-022 (observabilidade do relay). Versão 1.5: TD-018 fechado por remoção do `db-image/` (fast-check da fase 1) do repo da fase 2. Versão 1.4: dep `mutmut` removido (3.x quebrado); TD-006 sem tooling. Versão 1.3: TD-019 fechado (PR #50). Versão 1.2 (2026-06-22): reconciliação com o código (TD-003/TD-017 fechados, TD-002/004/005/008/009/016 corrigidos).

Simplificações deliberadas cujo custo de correção é aceito para o escopo do MVP.

Funcionalidades que não serão implementadas no MVP estão classificadas como Could Have no [PRD](../requisitos/prd.md). Requisitos que serão implementados estão nos respectivos RFs em [requisitos.md](../requisitos/requisitos.md).

Classificação por tipo:

- **Deliberado**: assumido conscientemente pela equipe para acelerar entrega ou validar hipóteses
- **Acidental**: surge sem que a equipe perceba, por desconhecimento ou mudanças inesperadas
- **Planejado**: equipe sabe que a solução não é ideal, documenta e planeja pagar depois
- **Negligenciado**: débito ignorado por muito tempo, mesmo após identificação

> 📋 **Plano de ataque** dos 13 abertos — priorização, como resolver cada um e checklist de progresso: **[plano-ataque.md](plano-ataque.md)**. Regra: cada TD vira **um PR próprio** que atualiza **todos os docs afetados no mesmo PR**.

## Itens Resolvidos (9)

| # | Área | Descrição | Resolução |
|---|---|---|---|
| TD-001 | Segurança | Sem mecanismo de consentimento explícito LGPD | **Fechado** — Implementado no MVP via RF-019: endpoints `POST/DELETE /clientes/{id}/consentimento` com entidade `ConsentimentoCliente`. |
| TD-020 | UI | Listagem da `ui/` não mostrava OS encerradas por default pós RF-023 | **Fechado** — PR #28: a `ui/` ganhou o toggle "Mostrar encerradas" (passa `incluir_encerradas`), os badges passam a exibir `situacao` (RF-021) e o dialog de nova OS aceita serviços/peças inline (RF-020). |
| TD-012 | Segurança | Sem SBOM automatizado no CI (geração manual) | **Fechado** — job `sbom` no [ci.yml](../../.github/workflows/ci.yml) gera o SBOM CycloneDX a partir do lockfile a cada run e publica como artefato; alvo `make sbom` para geração local ([ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md)). |
| TD-003 | Infra | Sem CSP headers (Content-Security-Policy) | **Fechado** — `SecurityHeadersMiddleware` aplica `Content-Security-Policy: default-src 'none'` em toda resposta (exceto as rotas de docs do Swagger/ReDoc, que precisam de inline scripts), além de `X-Frame-Options: DENY`, HSTS, `X-Content-Type-Options: nosniff` e `Cache-Control: no-store` ([middleware.py](../../src/compartilhado/interfaces/middleware.py)); coberto por `tests/unitarios/test_security.py` e `tests/unitarios/compartilhado/test_middleware.py`. |
| TD-017 | Observabilidade | Traces capturavam a query string (CPF/placa) — PII no OTel | **Fechado** (#34) — `_redigir_pii_da_span` (server_request_hook do `FastAPIInstrumentor`) redige `url.query` e remove a query de `http.target`/`url.path` antes do export dos spans ([observability.py](../../src/compartilhado/infraestrutura/observability.py)). |
| TD-019 | Arquitetura | `aplicacao → infraestrutura` na autenticação fora do contrato forbidden | **Fechado** (#50) — `PasswordHasherPort` + `JWTServicePort` em [aplicacao/ports.py](../../src/autenticacao/aplicacao/ports.py) (Protocol); a infra implementa e o composition root injeta por DI. O contrato `forbidden` do import-linter passou a proibir `aplicacao → infraestrutura` em todos os contextos, verificado por `make lint-arch`/CI (RNF-017). |
| TD-018 | Infra | `db-image/` no GHCR ainda com imagens da fase 1 | **Fechado** — `db-image/` (fast-check da fase 1) removido do repo da fase 2: confundia (imagens `-p1` sem RF-020..024/Mailpit) e não agregava (nada usa; compose e testes usam `postgres:16` vanilla, app builda do fonte e o CD publica `-p2-app` por SHA). Caminhos oficiais: `make up`, k8s/CD. |
| TD-008 | Domínio | Dispatch de domain events síncrono e in-process (sem outbox) | **Fechado** (2026-06-25, PR #56) — Resolvido via RF-018 (Transactional Outbox): a UoW grava `IntegrationEvents` na tabela `outbox` na mesma transação da OS; o relay (`python -m relay`) implementa claim-then-deliver com head-of-line, backoff/DLQ e idempotência via `processed_events`. Notificação proativa via `LISTEN/NOTIFY` (PostgreSQL). Detalhes em [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md). |
| TD-009 | Domínio | Dois eventos de criação do event storming sem classe nem emissão | **Fechado** (PR #48) — `ClienteCadastradoEvent` ([events.py](../../src/cliente_veiculo/dominio/events.py)) e `ServicoCadastradoEvent` ([events.py](../../src/catalogo_servicos/dominio/events.py)) implementados e emitidos via `_registrar_evento` nas factories `Cliente.criar`/`ServicoOferecido.criar`; cobertos por testes unitários (`test_cliente.py`, `test_servico_oferecido.py`). |

## Itens Abertos (13)

Débitos ativos, agrupados por área. Simplificações deliberadas cujo custo de correção é aceito no escopo do MVP.

### Geral

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-002 | Domínio | Sem histórico de orçamentos (snapshot único substitui o anterior) | Deliberado | Baixa | Baixo | Não | Estável | Orçamento é um Value Object imutável persistido como snapshot único na coluna `orcamento_json` — cada novo orçamento substitui o anterior, sem versionamento nem timestamp. Funcionalidade parcial aceita. RF-017 (Could Have). |
| TD-004 | API | Sem notificações push/SMS (e-mail já implementado) | Deliberado | Baixa | Baixo | Não | Estável | RF-024 entregou notificação real por **e-mail** (`EmailPort` + `SmtpEmailAdapter`; Mailpit no compose). Push e SMS seguem fora do escopo do MVP; a inversão de dependência ([ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md)) permite adicioná-los sem tocar no domínio. |
| TD-005 | Domínio | Orçamento em coluna Text, sem consulta estruturada nem índice | Planejado | Baixa | Médio | Não | Crescente | O snapshot do orçamento é persistido como **Text** (`orcamento_json`), não `jsonb` — logo não há query estruturada nem índice GIN. Aceitável no MVP (o orçamento é lido junto da OS, nunca filtrado). Evolução só se surgir necessidade real: migrar a coluna para `jsonb` e então indexar com GIN. |
| TD-006 | Testes | Mutation testing como meta, não requisito hard (sem tooling no momento) | Deliberado | Baixa | Baixo | Não | Estável | Cobertura de linha (90%+) e branch (85%+) nos domínios principais já garante qualidade. O dep `mutmut` foi **removido**: a série 3.x quebra na inicialização (`copy_src_dir` varre a raiz do filesystem). Mutation testing fica sem ferramenta até pinar uma versão funcional, quando virar prioridade. [ADR-005](../arquitetura/adr/005-estrategia-testes.md) documenta a estratégia. |

### DDD Tactical Compliance

Débitos aceitáveis no MVP relacionados à conformidade tática do DDD:

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-007 | Domínio | Contato do cliente como primitivo, sem Value Object dedicado | Deliberado | Baixa | Baixo | Não | Estável | Formato e dígito verificador já são validados: CPF/CNPJ via `brutils.is_valid` ([ADR-010](../arquitetura/adr/010-validacao-documentos-brutils.md)) e placa via regex antigo/Mercosul. Remanescente: o contato do cliente persiste como primitivo único (`contato: str`), sem VO dedicado (Telefone/Email) nem regras de negócio cross-field. Débito menor, sem impacto funcional. |

### Segurança e Qualidade

Débitos relacionados a segurança e qualidade de código.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-010 | Segurança | SonarQube não integrado no MVP (quality gate manual) | Deliberado | Baixa | Baixo | Não | Estável | Quality gate automatizado requer infraestrutura SonarQube. No MVP, análise estática local com ruff + bandit, mais o gate CodeQL Code Quality (`make codeql-quality`, [codeql-config.yml](../../.github/codeql/codeql-config.yml)) — cobertura parcial. SonarQube/SonarCloud em si fica para fases posteriores. [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md). |
| TD-011 | Segurança | Sem DAST automatizado (OWASP ZAP manual) | Deliberado | Média | Médio | Não | Estável | Teste dinâmico requer aplicação em execução e configuração de pipeline. No MVP, execução manual sob demanda. Automação planejada para CI quando pipeline estiver maduro. |
| TD-013 | Testes | Sem testes BDD/Gherkin no MVP (pytest-bdd planejado) | Deliberado | Baixa | Baixo | Não | Estável | Testes E2E com Gherkin em português agregam rastreabilidade para requisitos, mas requerem feature files e steps adicionais. Prioridade para testes unitários e de integração no MVP. [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md). |
| TD-014 | Testes | Sem relatórios Allure no MVP (pytest-html como alternativa leve) | Deliberado | Baixa | Baixo | Não | Estável | Allure oferece relatórios visuais superiores, mas requer servidor dedicado. pytest-html atende necessidades do MVP com menor overhead. |

### Fase 2

Débitos assumidos durante a fase 2 (infra Kubernetes, CI/CD, observabilidade e evolução da API), registrados no fechamento da fase.

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-015 | Infra | Corrida de migração com múltiplas réplicas (alembic no entrypoint) | Deliberado | Média | Médio | Sim | Estável | O `entrypoint.sh` roda `alembic upgrade head` no boot; duas réplicas subindo juntas poderiam disputar a migração. Mitigação atual: rollout inicial com réplica única (`replicas: 1` explícito no Deployment) antes de o HPA escalar. Evolução: Job dedicado de migração no deploy ([ADR-019](../arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)). Rastreado em #33. |
| TD-016 | Infra | Rate limiter slowapi in-memory por pod | Deliberado | Média | Médio | Sim | Crescente | A metade do RNF-024 relativa ao **pool de conexões** já foi entregue (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` em [database.py](../../src/compartilhado/infraestrutura/database.py), #32 fechada). Resta o **rate limiter**: o contador do slowapi vive na memória de cada pod ([middleware.py](../../src/compartilhado/interfaces/middleware.py)), então sob HPA o limite efetivo é multiplicado pelo número de réplicas. Aceitável no cluster de demo; evolução é backend compartilhado (Redis via `storage_uri`) com mais de uma réplica estável. Rastreado em #31. |
| TD-021 | Infra | Relay sem fencing de lease para `replicas>1` | Planejado | Média | Médio | Sim | Latente | O relay roda com `replicas:1`; o drain sequencial torna o lease (visibility timeout, 60 s) seguro nessa topologia. Escalar para `replicas>1` (caminho "HA-ready" via `FOR UPDATE SKIP LOCKED`) exige que o lease sempre exceda a latência de um handler isolado (limitada pelo timeout SMTP de 5 s) **ou** um fencing na entrega (re-checar lease/owner dentro da tx por-linha e pular se o lease foi roubado). Sem isso, um lease vencendo no meio de uma entrega lenta permite que uma segunda réplica re-reivindique a linha → e-mail duplicado. Contexto em [relay/processador.py](../../relay/processador.py) e [relay/listener.py](../../relay/listener.py). |
| TD-022 | Observabilidade | Relay sem métricas OTel nem alerting | Planejado | Baixa-Média | Médio | Não | Crescente | O design (RF-018 §7) prevê métricas proativas: contagem `pendente`, idade do mais antigo pendente, tamanho da DLQ, contagem de retries. Implementado um gauge structlog por ciclo (`outbox_profundidade` em [relay/processador.py](../../relay/processador.py)) como cobertura proporcional ao MVP; falta instrumentação OTel no processo do relay (a API já tem OTel via ADR-020; o relay apenas emite structlog) e alerting sobre `outbox_dead_com_sucessores_pendentes` e backlog elevado. Evolução: exportar métricas do relay via OTel/Prometheus e configurar alertas. |

## Considerações de Complexidade Algorítmica

Complexidade das operações principais do sistema.

| Operação | Complexidade | Estrutura | Justificativa |
|---|---|---|---|
| Bloqueio pessimista de estoque | O(n log n) ordenação + O(n) reserva | Array de `item_id` ordenado | Ordenação previne deadlocks ([ADR-008](../arquitetura/adr/008-bloqueio-pessimista-estoque.md)). Custo aceitável para n < 100 itens por OS. |
| Transição de status da OS | O(1) por transição | Lookup direto (dict/enum) | `MaquinaDeStatus` valida transição em tempo constante. |
| Busca de OS por placa | O(log n) | Índice B-tree PostgreSQL | Índice B-tree (unique) em `veiculos.placa`; a busca de OS resolve a placa pelo veículo (JOIN veículo→OS), logarítmica nessa resolução. |
| Cálculo de média de execução | O(n) | Agregação SQL | `AVG()` de `atualizado_em − criado_em` sobre OS em status final; full scan da tabela (o filtro de `status` não tem índice de suporte — os índices existentes são compostos `(cliente_id, status)`/`(veiculo_id, status)`, com `status` não-líder). Aceitável no volume do MVP. |
| Validação de CPF/CNPJ | O(1) | Cálculo aritmético | Dígitos verificadores calculados em tempo constante (brutils). |

Otimizações (migrar `orcamento_json` de Text para `jsonb` + índice GIN -- TD-005, particionamento) a avaliar com dados reais de produção.

## Estratégia de Pagamento

1. **Boy Scout Rule**: cada alteração deixa o código melhor do que encontrou
2. **Refatorações incrementais**: melhorias técnicas nos sprints regulares, como parte do backlog
3. **Sprint técnico**: negociar com o PO para débitos de maior impacto (TD-011, TD-015, TD-016)
4. **ADRs como prevenção**: decisões registradas em ADR ([ADR-001](../arquitetura/adr/001-framework-fastapi.md) a [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md)) evitam débitos invisíveis
5. **Métricas de fluxo**: lead time, cycle time e taxa de falhas para detectar crescimento do débito

> [↑ Raiz do projeto](../../README.md)
