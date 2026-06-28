# Plano de Ataque — Dívida Técnica

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)

> **Para a próxima IA/dev:** plano priorizado para atacar os 12 TDs abertos antes da entrega da fase 2. A **fonte da verdade** é o [README.md](README.md) desta pasta (resolvido + aberto, com justificativa e evidência). Este plano diz a **ordem**, o **como**, e o que é *must-do* vs *nice-to-have*. Marque o checkbox quando o PR do TD mergear.

## Regras de execução (obrigatórias)

1. **Um PR por TD.** Cada TD atacado tem o seu próprio PR — pequeno, focado, revisável.
2. **Todos os docs no mesmo PR.** O PR que resolve um TD atualiza, no próprio PR e nunca "para depois": o registro ([README.md](README.md)), o(s) ADR(s) afetados, o índice de ADRs ([../arquitetura/README.md](../arquitetura/README.md)), o [gap-analysis](../requisitos/fase2/gap-analysis-fase-2.md)/requisitos quando aplicável, e qualquer diagrama (C4/modelo) que descreva o comportamento alterado.
3. **Fechar com evidência.** Mover a linha de *Itens Abertos* → *Itens Resolvidos* no README citando arquivo/mecanismo + nº do PR; atualizar as contagens (`Resolvidos N` / `Abertos M`) e o changelog de versão no topo do README.
4. **Gates verdes antes do PR.** `make codeql-quality` (0 findings), `make lint`, `make typecheck`, `make lint-arch`, `make test` (cobertura ≥ 95%). Para TDs de infra/runtime, rodar também o teste de mesa no kind (UI por automação + carga para o HPA).
5. **Marcar o checkbox** deste plano quando o PR mergear.

## Status

- ✅ **Resolvidos: 11** — TD-001, TD-003, TD-008, TD-009, TD-012, TD-015, TD-016, TD-017, TD-018, TD-019, TD-020.
- ⬜ **Abertos: 12** — TD-002, TD-004, TD-005, TD-006, TD-007, TD-010, TD-011, TD-013, TD-014, TD-021, TD-022, TD-023 — abaixo, por ordem de ataque.

> Nenhum dos 12 abertos é **exigido** pela fase 2 — todos são débito deliberado/justificado. Atacá-los é iniciativa de qualidade, priorizada por valor de avaliação.

## Ordem de ataque

Critério: **risco de produção × valor para a avaliação** (temas da fase: HPA, CD, observabilidade, segurança) **× esforço**.

### Tier 1 — atacar primeiro (risco-prod = Sim; alinha HPA/CD)

> ✅ Tier 1 **concluído** (TD-016 PR #62, TD-015 PR #64). A cabeça da fila aberta passa a ser o **TD-011 — DAST no CI** (Tier 2).

- [x] **TD-016 — Rate limiter compartilhado (Redis)** — ✅ Fechado (PR #62)
  - **Por quê:** o slowapi conta in-memory por pod → sob HPA o limite efetivo é multiplicado pelo nº de réplicas (RNF-024). Risco de produção real; tema HPA direto.
  - **Como:** subir um Redis pequeno no `k8s/` (Deployment + Service) e no compose; configurar o `Limiter` do slowapi com `storage_uri` (env `RATE_LIMIT_STORAGE_URI`), com fallback in-memory se ausente. **Teste:** limite consistente entre réplicas (carga no kind, como no TD-008).
  - **Docs no PR:** README; [gap-analysis (RNF-024)](../requisitos/fase2/gap-analysis-fase-2.md); [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md) (Redis de rate limit).
  - **Esforço:** médio · **Valor:** alto · **Rastreado em:** #31.

- [x] **TD-015 — Migração em Job dedicado** — ✅ Fechado (PR #64)
  - **Por quê:** o `entrypoint.sh` rodava `alembic upgrade head` no boot; N réplicas subindo juntas disputavam a migração. Risco-prod; tema CD.
  - **Como (feito):** migração tirada do entrypoint no cluster (`RUN_MIGRATIONS_ON_STARTUP=false`/`RUN_SEED_ON_STARTUP=false` no configmap); Job `pytstop-migrate` ([`k8s/jobs/migration-job.yaml`](../../k8s/jobs/migration-job.yaml)) roda `alembic upgrade head` + seed best-effort uma vez, aplicado pelo CD/`make k8s-up` com a tag SHA (sed) antes do rollout, com `kubectl wait --for=condition=complete`. O subdir `k8s/jobs/` fica fora do `kubectl apply -f k8s/`.
  - **Docs no PR:** README; [ADR-019](../arquitetura/adr/fase2/019-pipeline-cicd-deploy.md) (estratégia de migração); [RFC-002](../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md); [k8s/README](../../k8s/README.md).
  - **Esforço:** médio · **Valor:** alto · **Rastreado em:** #33.

### Tier 2 — follow-ups fortes (valor de nota; fecham temas da fase)

- [ ] **TD-011 — DAST no CI (OWASP ZAP)** *(cabeça da fila aberta, com o Tier 1 fechado)*
  - **Como:** ZAP baseline scan contra o compose que o `full-test-ci` já sobe; publicar o relatório como artefato.
  - **Docs no PR:** README; [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md); [relatório de segurança](../seguranca/relatorio-vulnerabilidades.md).
  - **Esforço:** médio · **Valor:** médio-alto (maturidade de segurança).

- [ ] **TD-023 — Rate-limit por cliente atrás de proxy (X-Forwarded-For confiável)**
  - **Por quê:** a chave do rate limit é `get_remote_address` (`request.client.host`), o IP do *peer* imediato. Atrás de um ingress sem XFF confiável, todo o tráfego externo colapsa num único bucket → o limite global vira um só para todos. Risco de produção; no demo (ClusterIP/port-forward) não se manifesta.
  - **Como:** ingress que injeta `X-Forwarded-For` + uvicorn `--proxy-headers --forwarded-allow-ips=<trusted>` (ou `ProxyHeadersMiddleware`), restringindo a origem confiável; validar que a chave passa a refletir o cliente real, não o proxy.
  - **Docs no PR:** README; [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md); [gap-analysis (RNF-024)](../requisitos/fase2/gap-analysis-fase-2.md).
  - **Esforço:** médio (precisa de ingress + proxy-headers) · **Valor:** médio (correção de segurança).

- [ ] **TD-022 — OTel no relay**
  - **Como:** estender o OTel da API ([ADR-020](../arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)) ao processo do relay; emitir métricas (profundidade da outbox, tamanho da DLQ, retries) via OTLP. Valor pleno pede um backend de métricas (Prometheus) — avaliar escopo mínimo.
  - **Docs no PR:** README; [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md) e/ou ADR-020.
  - **Esforço:** médio · **Valor:** médio (tema observabilidade).

- [ ] **TD-021 — Fencing de lease do relay (`replicas>1`)**
  - **Como:** re-checar lease/owner dentro da transação por-linha e pular se o lease foi roubado; só então permitir `replicas>1`. Completa a história HA do outbox.
  - **Docs no PR:** README; [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md) (atualiza a seção de consequências/HA).
  - **Esforço:** médio-alto (delicado — exige teste de roubo de lease) · **Valor:** médio · **Latente hoje** (relay roda `replicas:1`).

### Tier 3 — quick wins (baixo esforço)

- [ ] **TD-005 — `orcamento_json` Text → `jsonb`**
  - **Como:** migração de coluna Text → jsonb (índice GIN só se for filtrar por campo do orçamento — hoje não é). Docs no PR: README; modelo de dados.
  - **Esforço:** baixo · **Valor:** baixo (limpeza).

- [ ] **TD-007 — Value Object de contato**
  - **Como:** extrair `Telefone`/`Email` (ou um `Contato`) como Value Object com validação de formato, em vez do `contato: str` atual. Docs no PR: README; [modelo-dominio](../arquitetura/modelo-dominio.md).
  - **Esforço:** baixo · **Valor:** baixo-médio (pureza DDD).

### Tier 4 — aceitar (baixo valor; só se sobrar tempo)

Débitos deliberados, justificados, sem risco de produção. Atacar apenas com folga de prazo:

- [ ] **TD-002** — histórico de orçamentos (RF-017 Could-Have)
- [ ] **TD-004** — notificações push/SMS (fora de escopo do MVP)
- [ ] **TD-006** — mutation testing (pinar `mutmut` funcional ou trocar por `cosmic-ray`)
- [ ] **TD-010** — SonarCloud (o gate CodeQL local já dá cobertura parcial)
- [ ] **TD-013** — testes BDD/Gherkin (pytest-bdd)
- [ ] **TD-014** — relatórios Allure

## Notas de complexidade — o que dá para fazer

Da tabela *Considerações de Complexidade Algorítmica* do [README.md](README.md):

- **Cálculo de média (full scan hoje):** o `AVG` filtra `status IN (status finais)` sem índice de suporte — os índices da OS são `(cliente_id, status)`/`(veiculo_id, status)`, com `status` não-líder, que um filtro só por `status` não usa. Se o volume crescer: criar um **índice parcial** `CREATE INDEX ... ON ordens_de_servico (status) WHERE status IN (...)` ou um composto `(status, criado_em, atualizado_em)`. **Hoje é aceitável no volume do MVP — não atacar sem dado de produção** (evita índice especulativo).
- **Orçamento Text → jsonb (TD-005):** ver Tier 3. Sem necessidade de query estruturada hoje; `jsonb` + índice GIN só se surgir filtro por campo do orçamento.

## O que entra na entrega (must vs nice)

- **Must (já feito):** os 11 resolvidos + a higiene de documentação (este registro). A fase 2 não exige nenhum dos 12 abertos.
- **Nice, por valor de nota, se houver tempo antes da entrega:** Tier 1 **concluído** (TD-016 PR #62, TD-015 PR #64 — risco-prod + temas HPA/CD); seguir pelo Tier 2 (TD-011 DAST à frente, depois TD-022, TD-021).
- **Provavelmente fora:** Tier 3 (limpeza de baixo retorno) e Tier 4 (deliberados de baixo valor para a banca).

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)
