# Plano de Ataque — Dívida Técnica

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)

> ⚠️ **Snapshot histórico** (campanha de dívida técnica concluída em 2026-06-30). Os números e checkboxes abaixo refletem o estado durante a campanha e **não** são atualizados. Fonte viva das contagens e do status de cada TD: [README.md](README.md) desta pasta (na v3.3, 2026-07-03: **28 resolvidos / 6 abertos**).

> **Para a próxima IA/dev:** plano priorizado que guiou o ataque aos TDs abertos antes da entrega da fase 2. A **fonte da verdade** é o [README.md](README.md) desta pasta (resolvido + aberto, com justificativa e evidência). Este plano diz a **ordem**, o **como**, e o que é *must-do* vs *nice-to-have*. Marque o checkbox quando o PR do TD mergear.

## Regras de execução (obrigatórias)

1. **Um PR por TD.** Cada TD atacado tem o seu próprio PR — pequeno, focado, revisável.
2. **Todos os docs no mesmo PR.** O PR que resolve um TD atualiza, no próprio PR e nunca "para depois": o registro ([README.md](README.md)), o(s) ADR(s) afetados, o índice de ADRs ([../arquitetura/README.md](../arquitetura/README.md)), o [gap-analysis](../requisitos/fase2/gap-analysis-fase-2.md)/requisitos quando aplicável, e qualquer diagrama (C4/modelo) que descreva o comportamento alterado.
3. **Fechar com evidência.** Mover a linha de *Itens Abertos* → *Itens Resolvidos* no README citando arquivo/mecanismo + nº do PR; atualizar as contagens (`Resolvidos N` / `Abertos M`) e o changelog de versão no topo do README.
4. **Gates verdes antes do PR.** `make codeql-quality` (0 findings), `make lint`, `make typecheck`, `make lint-arch`, `make test` (cobertura ≥ 95%). Para TDs de infra/runtime, rodar também o teste de mesa no kind (UI por automação + carga para o HPA).
5. **Marcar o checkbox** deste plano quando o PR mergear.

## Status

> Contagens abaixo são do fim da campanha (2026-06-30). A contagem viva está no [README.md](README.md) (v3.3: 28 resolvidos / 6 abertos — o +2 resolvidos e +1 aberto vieram da auditoria de finalização e do registro de TD-032/033/034, posteriores a esta campanha).

- ✅ **Resolvidos ao fim da campanha: 27** — TD-001, TD-003, TD-005, TD-007, TD-008, TD-009, TD-010, TD-011, TD-012, TD-015, TD-016, TD-017, TD-018, TD-019, TD-020, TD-021, TD-022, TD-023 + TD-024, TD-025, TD-026, TD-028, TD-029, TD-030, TD-031, **TD-027** (campanha Tier 4, jun/2026).
- ⬜ **Abertos ao fim da campanha: 5** — TD-002, TD-004, TD-006, TD-013, TD-014 (originais da fase 1; débito deliberado/aceito).

> Nenhum dos abertos é **exigido** pela fase 2 — todos são débito deliberado/justificado. Atacá-los é iniciativa de qualidade, priorizada por valor de avaliação.

> **TD-024..TD-031 vieram da auditoria pré-entrega** ([auditoria-pre-entrega-fase2.md](auditoria-pre-entrega-fase2.md)) e entram no **Tier 4 (aceitar-ou-evoluir)**: compromissos aceitos/justificados, sem risco de produção no caminho suportado. Os **bugs confirmados** e as **correções delivery-facing** da mesma auditoria são rastreados como **issues no GitHub**, não aqui — este plano cobre só o débito aceito.

## Ordem de ataque

Critério: **risco de produção × valor para a avaliação** (temas da fase: HPA, CD, observabilidade, segurança) **× esforço**.

### Tier 1 — atacar primeiro (risco-prod = Sim; alinha HPA/CD)

> ✅ Tier 1 **concluído** (TD-016 PR #62, TD-015 PR #64). Tier 2 **concluído**: **TD-011 — DAST no CI** (PR #65), **TD-021 — fencing de lease do relay** (PR #66), **TD-022 — OTel no relay** (PR #66) e **TD-023 — rate-limit por cliente atrás de proxy** (PR #67) fechados. Tier 3 **concluído**: **TD-005** (PR #68) e **TD-007 — `Contato` Value Object** (PR #70) fechados. Sem mais itens abertos com risco de produção nem quick wins; a fila aberta passa a ser só o **Tier 4** (deliberados de baixo valor para a banca) — do qual **TD-010 — SonarQube** já foi **fechado por decisão** (PR #71, não vira gate de CI; ver Tier 4).

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

- [x] **TD-011 — DAST no CI (OWASP ZAP)** — ✅ Fechado (PR #65)
  - **Como (feito):** ZAP baseline scan contra a stack compose que o [`full-test-ci`](../../.github/workflows/full-test-ci.yml) já sobe e deixa saudável; roda SEM `-I` (gate real) com os 2 WARNs aceitos da fase 1 (10049, 90004) em IGNORE no [`.zap/rules.tsv`](../../.zap/rules.tsv) → achado novo reprova; relatório (`zap-report.{json,html,md}`) publicado como artefato `zap-dast-report`; alvo `make dast` para paridade local.
  - **Docs no PR:** README; [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md); [scan-fase-2](../seguranca/scan-fase-2.md); [plano-seguranca](../seguranca/plano-seguranca.md).
  - **Esforço:** médio · **Valor:** médio-alto (maturidade de segurança).

- [x] **TD-023 — Rate-limit por cliente atrás de proxy (X-Forwarded-For confiável)** — ✅ Fechado (PR #67)
  - **Por quê:** a chave do rate limit é `get_remote_address` (`request.client.host`), o IP do *peer* imediato. Atrás de um ingress sem XFF confiável, todo o tráfego externo colapsa num único bucket → o limite global vira um só para todos. Risco de produção; no demo (ClusterIP/port-forward) não se manifesta.
  - **Como (feito):** `ProxyHeadersMiddleware` do uvicorn aplicado programaticamente em `criar_app` ([src/main.py](../../src/main.py)), gated pela env `TRUSTED_PROXIES` (`configurar_proxy_headers`/`_resolver_trusted_proxies` em [middleware.py](../../src/compartilhado/interfaces/middleware.py)). Quando definida (IP exato/CIDR/`*`), o middleware reescreve `request.client` a partir do `X-Forwarded-For` SOMENTE quando o peer imediato é confiável, e é adicionado DEPOIS do `SlowAPIMiddleware` (fica por fora → reescreve o client antes do limiter ler a chave). Default vazio → não instala → XFF ignorado (sem spoof). `k8s/configmap.yaml`: `TRUSTED_PROXIES: ""` (demo sem ingress) com comentário do uso em produção. Coberto por testes de integração com `TestClient` (trusted+XFF → bucket por cliente real; default → bucket do peer, XFF ignorado).
  - **Docs no PR:** README; [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md); [gap-analysis (RNF-024)](../requisitos/fase2/gap-analysis-fase-2.md).
  - **Esforço:** médio · **Valor:** médio (correção de segurança).

- [x] **TD-022 — OTel no relay** — ✅ Fechado (PR #66)
  - **Como (feito):** OTel da API ([ADR-020](../arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)) estendido ao processo do relay com backend Prometheus — `MeterProvider` + `PrometheusMetricReader` ([relay/metrics.py](../../relay/metrics.py)) servem `/metrics` (porta 9100), scrapeado pelo [`k8s/prometheus.yaml`](../../k8s/prometheus.yaml) (Service `pytstop-relay-metrics`): gauges de profundidade (pendentes/idade/dead, mesma query do gauge structlog) + contadores entregue/falha/dead/retry.
  - **Docs no PR:** README; [ADR-024](../arquitetura/adr/fase2/024-metricas-prometheus.md) e [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md)/ADR-020.
  - **Esforço:** médio · **Valor:** médio (tema observabilidade).

- [x] **TD-021 — Fencing de lease do relay (`replicas>1`)** — ✅ Fechado (PR #66)
  - **Como (feito):** fencing na entrega — `bloquear_para_entrega` re-adquire o lock da linha (`SELECT ... WHERE id=:id AND status='pendente' FOR UPDATE SKIP LOCKED`) no INÍCIO da tx por-linha de [relay/processador.py](../../relay/processador.py); falso → outra réplica detém a entrega ou a linha já não está `pendente` → pula. O lock vive até o fim da tx (handler + marcação), serializando réplicas concorrentes sem duplicar entrega; sem mudança de schema. Coberto por teste unitário de short-circuit e por dois testes de integração deterministas (duas conexões competindo + duas réplicas entregando 1 linha exatamente uma vez).
  - **Docs no PR:** README; [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md) (consequências/HA); [k8s/relay.yaml](../../k8s/relay.yaml) (comentário: `replicas>1` agora seguro).
  - **Esforço:** médio-alto · **Valor:** médio · Completa a história HA do outbox (`replicas:1` segue como default conservador).

### Tier 3 — quick wins (baixo esforço)

- [x] **TD-005 — `orcamento_json` Text → `jsonb`** — ✅ Fechado (PR #68)
  - **Como (feito):** coluna migrada de `Text` para `jsonb` nativo (migração [004](../../migrations/versions/004_orcamento_jsonb.py), `orcamento_json::jsonb`), removendo a camada manual `json.dumps`/`json.loads` no [mapping.py](../../src/ordem_servico/infraestrutura/mapping.py) — o `dict` cru é passado à coluna `JSONB().with_variant(JSON(), "sqlite")`, espelhando `outbox.payload`. Sem índice GIN (nenhuma consulta filtra por campo do orçamento — YAGNI). Coberto por round-trip do VO em Postgres real + assert `jsonb_typeof = 'object'` (prova que não há string duplamente codificada) e por teste de ida-e-volta da migração 004.
  - **Esforço:** baixo · **Valor:** baixo (limpeza).

- [x] **TD-007 — Value Object de contato** — ✅ Fechado (PR #70)
  - **Como (feito):** `Contato` Value Object ([contato.py](../../src/cliente_veiculo/dominio/contato.py)) — `@dataclass(frozen=True, slots=True)`, validação leve (não-vazio, `<=255` chars, `strip`) e `__repr__` PII-safe — substitui o `contato: str` no agregado `Cliente`. Como o campo é **texto livre** (e-mail, telefone ou nome+e-mail+telefone), NÃO se extraiu `Telefone`/`Email` estritos: um VO `Contato` com validação leve é o ajuste fiel ao domínio. Persiste na mesma coluna `String(255)` via shadow `_contato_valor` + event listeners (load/refresh reidrata o VO; before_insert/before_update serializa de volta), espelhando o padrão CPF/Placa — **sem migração**. Aceita o sentinela LGPD `anonimizado@anonimizado.local` gravado pelo raw UPDATE de `anonimizar_dados`. **`email()` deliberadamente fora do VO:** o handler `notificacoes.py` (RF-024) consome o contato como `str` cru via `ClientePort` (comunicação cross-context por porta); mover a regex `_extrair_email` para o VO criaria o primeiro import `ordem_servico.aplicacao → cliente_veiculo.dominio` do código e quebraria o isolamento de bounded context (verificado: nenhum `aplicacao` importa o `dominio` de outro contexto hoje) — `make lint-arch` segue 3/0.
  - **Esforço:** baixo · **Valor:** baixo-médio (pureza DDD).

### Tier 4 — aceitar (baixo valor; só se sobrar tempo)

Débitos deliberados, justificados, sem risco de produção. Atacar apenas com folga de prazo:

- [ ] **TD-002** — histórico de orçamentos (RF-017 Could-Have)
- [ ] **TD-004** — notificações push/SMS (fora de escopo do MVP)
- [ ] **TD-006** — mutation testing (pinar `mutmut` funcional ou trocar por `cosmic-ray`)
- [x] **TD-010** — SonarQube — ✅ **Fechado por decisão** (PR #71): não vira gate de CI (repo privado = SonarCloud pago; self-hosted = servidor desproporcional ao MVP). A análise estática em CI é CodeQL (`make codeql-quality`) + ruff + bandit; o SonarQube permanece scan manual de fechamento de fase (suportado pelo `sonar-project.properties`, mantido). Decisão em [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md).
- [ ] **TD-013** — testes BDD/Gherkin (pytest-bdd)
- [ ] **TD-014** — relatórios Allure

Da auditoria pré-entrega ([auditoria-pre-entrega-fase2.md](auditoria-pre-entrega-fase2.md)) — compromissos aceitos, *aceitar-ou-evoluir*:

- [x] **TD-024** (PR #108) — `securityContext` (`runAsNonRoot` / `allowPrivilegeEscalation:false` / `capabilities.drop:[ALL]` / `readOnlyRootFilesystem` / seccomp) + `emptyDir` `/tmp` nos 3 workloads próprios; UID 1001 pinado no Dockerfile. Teste de mesa kind.
- [x] **TD-025** (PR #107) — índice B-tree `ix_itens_da_ordem_item_estoque_id` via migração 005 reversível; `EXPLAIN` confirma `Index Scan`.
- [x] **TD-026** (decisão) — documentado em `k8s/README.md`: deploy fora do pipeline (`cd.yml`/`make k8s-up`) é não-suportado; auto-enforce fica para um eventual GitOps.
- [x] **TD-027** (PR #114) — assinatura HMAC-SHA256 por requisição no webhook de orçamento (`X-Webhook-Signature` + `X-Webhook-Timestamp`, chave = `ORCAMENTO_WEBHOOK_TOKEN`, janela ±5min). Helper `webhook_signature` + ADR-021 emendada + harness full-test migrado. Postman → follow-up #113.
- [x] **TD-028** (PR #105) — pré-hash `base64(sha256(senha))` antes do bcrypt; fallback legado só para senha ≤72 bytes.
- [x] **TD-029** (PR #105) — `obter_usuario_atual` valida `type == "access"` (`if type != "access": 401`).
- [x] **TD-030** (decisão) — eventos órfãos documentados em `docs/arquitetura/eventos-de-dominio.md` (intenção de modelagem, sem consumidor na fase 2).
- [x] **TD-031** (PR #106) — `--cov-fail-under=95` explícito no step de cobertura de `src/` no `ci.yml`.

## Notas de complexidade — o que dá para fazer

Da tabela *Considerações de Complexidade Algorítmica* do [README.md](README.md):

- **Cálculo de média (full scan hoje):** o `AVG` filtra `status IN (status finais)` sem índice de suporte — os índices da OS são `(cliente_id, status)`/`(veiculo_id, status)`, com `status` não-líder, que um filtro só por `status` não usa. Se o volume crescer: criar um **índice parcial** `CREATE INDEX ... ON ordens_de_servico (status) WHERE status IN (...)` ou um composto `(status, criado_em, atualizado_em)`. **Hoje é aceitável no volume do MVP — não atacar sem dado de produção** (evita índice especulativo).
- **Orçamento Text → jsonb (TD-005):** ✅ feito (PR #68). A coluna já é `jsonb` nativo (migração 004); índice GIN só se surgir filtro por campo do orçamento (hoje lido junto da OS, nunca filtrado).

## O que entra na entrega (must vs nice)

- **Must (já feito):** os TDs resolvidos + a higiene de documentação (este registro). A fase 2 não exige nenhum dos abertos. (Contagem viva no [README.md](README.md).)
- **Nice, por valor de nota, se houver tempo antes da entrega:** Tier 1 **concluído** (TD-016 PR #62, TD-015 PR #64 — risco-prod + temas HPA/CD), Tier 2 **concluído** — **TD-011 DAST** (PR #65), **TD-021 fencing do relay** (PR #66), **TD-022 OTel no relay** (PR #66) e **TD-023 proxy-headers** (PR #67) — e o Tier 3 **concluído** — **TD-005** (PR #68) e **TD-007 `Contato` VO** (PR #70). Resta só o Tier 4 (deliberados).
- **Provavelmente fora:** Tier 4 (deliberados de baixo valor para a banca).

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)
