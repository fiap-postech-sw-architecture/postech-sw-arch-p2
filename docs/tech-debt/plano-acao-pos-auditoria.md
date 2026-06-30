# Plano de Ação — Pós-Auditoria Pré-Entrega (Fase 2)

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)

> **Versão**: 1.2 (2026-06-30) — **Tier 3 e Tier 4 fechados**: Tier 3 #73 (PR #103) + #76 (PR #104), #72 deferido; Tier 4 TD-024/025/026/028/029/030/031 (PRs #105–#108 + 2 decisões), TD-027 deferido. Cada mudança de código com gate local completo + review single-shot (prompt do CI) + teste de mesa na imagem final, merge via `--admin` (CI travado no billing). Versão 1.1 (2026-06-29) — Tier 0-2 **fechado** (8 PRs; merge via `--admin` por causa do CI travado no billing); **#75 deferido**; 6 achados novos rastreados como issues. Plano de ataque unificado e **resumível entre sessões** para os achados da auditoria pré-entrega da fase 2. Dirigido a checkbox: marque o item quando o PR mergear. Fontes: [auditoria-pre-entrega-fase2.md](auditoria-pre-entrega-fase2.md) (achados), as GitHub issues #72–#86 (bugs/docs/feature) e o ledger TD-024..031 ([README.md](README.md)). A ordem segue **impacto na nota** (delivery-facing + refutável pela banca) **>** severidade do bug confirmado **>** ROI.

Plano priorizado e resumível dos achados da auditoria de fechamento da fase 2. Consolida, num único roteiro acionável, os três rastreadores que hoje vivem separados — o relatório de auditoria, as issues do GitHub e o ledger de dívida técnica — sem duplicar a fonte da verdade de cada um.

## Como usar / continuar entre sessões

Este documento é o ponto de retomada entre sessões. Ao reabrir, leia a linha de **Progresso** e o **Status** de cada item antes de escolher o próximo.

- **Marque `[x]`** quando o PR do item **mergear** — não antes.
- **Atualize a coluna `Status`** ao longo do ciclo de vida: `aberto` → `PR #NN` → `fechado`.
- **Fluxo por item:** implementa → review canônico → teste de mesa (se for runtime/infra) → abre PR. **Não usar auto-merge** — o usuário revisa cada PR manualmente.
- **Bundles indicados (`BUNDLE`) devem ser atacados juntos** no mesmo PR ou em PRs irmãos abertos na mesma rodada — são correções acopladas (mesma classe de bug, mesmo arquivo ou mesma narrativa para a banca).
- Cada item já traz uma **abordagem-semente** com `file:line`. Ela é um **ponto de partida, não a solução fechada** — ver a issue (ou o ledger) para investigar/decidir antes de implementar.

## Fonte-de-verdade do requisito

> **IMPORTANTE.** O enunciado **oficial** da fase 2 está em `~/git/local/postech-bootstrap/lessons/phase2/Challenge/Phase2_Tech_Challenge.txt` — **não** nos RFs do repositório. Quando este plano fala em "requisito da fase", é esse arquivo que manda. Os RFs/RNFs do repo são a nossa modelagem; o enunciado é o contrato com a banca.

O que a fase 2 **exige** (o que compõe a nota):

- **Evolução do código:** refatorar a fase 1 com **Clean Code + Clean Architecture (ou Hexagonal)** e **testes automatizados** (unitários e/ou integração) cobrindo os fluxos críticos.
- **5 APIs:** (1) **abertura** de OS; (2) **consulta de status** com os **6 status** (`Recebida`, `Diagnóstico`, `Aguardando Aprovação`, `Execução`, `Finalizada`, `Entregue`); (3) **aprovação** externa de orçamento (webhook); (4) **listagem** ordenada (Execução > Aguardando Aprovação > Diagnóstico > Recebida; mais antigas primeiro; exclui logicamente finalizadas/entregues); (5) **atualização de status via e-mail** (ou ferramenta equivalente).
- **Infraestrutura:** **Docker** (Dockerfile + compose), **Kubernetes** (Deployments, Services, ConfigMaps/Secrets, **HPA**), **Terraform** (cluster + banco), **CI/CD** (build, testes, imagem, deploy no k8s + banco + manifestos).
- **Entregáveis:** **README** com descrição + **diagrama da arquitetura** (componentes da aplicação, infraestrutura provisionada, fluxo de deploy) + instruções (local / k8s / Terraform); **collection das APIs** (Postman/Swagger); **vídeo ≤ 15 min** demonstrando **deploy, CI/CD, consumo das APIs e auto-scaling**; **PDF** no portal (link do repo, diagrama, link do vídeo).

O que a fase 2 **não exige** (e portanto não vale nota por si só):

- **Orçamento complementar.** O enunciado pede **6 status** e nada de re-orçamento — confirmado no PDF oficial. É decisão de modelagem nossa (ver #80).
- **Segurança não é requisito explícito.** Não há item de segurança no enunciado. Ela entra como **qualidade e credibilidade**: um controle que a documentação vende e o código não entrega vira munição para a banca refutar a entrega — por isso a faixa de segurança (Tier 1) pesa na nota indiretamente, não como requisito.

**Tradução para a nota:** nota = **infra (Docker/k8s/HPA/Terraform/CI-CD)** + **5 APIs** + **Clean Arch/testes** + **entregáveis (README/diagrama/Postman/vídeo/PDF)**. Tudo o mais é higiene de qualidade que protege a entrega de uma banca cética.

## Progresso

> **Progresso: 11/14 issues fechados + 7/8 TDs** (2026-06-30). Tier 0 (5/5) + Tier 1 (#84, #86) + Tier 2 (#82+#83) **fechados**; **Tier 3** #73 (PR #103) + #76 (PR #104) **fechados**, #72 **deferido** (migração+sentinela); **Tier 4** TD-024/025/026/028/029/030/031 **fechados** (PRs #105–#108 + 2 decisões), **TD-027 deferido** (webhook HMAC — ripple no caller). Restam: **#75** (CI billing) + **#72** (deferido) + **TD-027** (deferido) + Tier 5 **#80** (não-requisito). (As 14 issues são #72–#86; #85 é controle/meta. Os 8 TDs são TD-024..TD-031.)

> ⚠️ **CI travado no billing.** O GitHub Actions está bloqueado (pagamento/spending limit da conta) — todos os jobs falham em 2-3s. Enquanto isso, cada item foi merjado via **`gh pr merge --admin`** após o **CI rodado localmente na íntegra** (lock·ruff·import-linter·mypy·bandit·sbom·unit·integ·codeql) **+ review canônico com o prompt do CI** (`.github/claude-prompts/code-review.md`) **+ teste de mesa na kind**. Destravar (Settings → Billing & plans) restaura o CI real e o #75.

## Achados novos durante o ataque (issues abertas, seguir)

Defeitos/melhorias descobertos ao implementar o Tier 0-2 — abertos como issues e seguidos (não bloquearam o item de origem):

- **[#90](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/90)** — README diz "Python 3.12" mas o runtime é `python:3.13-slim` (doc, low).
- **[#93](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/93)** — roteiro do vídeo sem passo de demo das métricas Prometheus / ADR-024 (doc, low).
- **[#95](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/95)** — `seed_admin.py` não rejeita o `ADMIN_PASSWORD` demo público (caminho do Job de migração) (bug-seg, medium).
- **[#96](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/96)** — coluna `usuarios.papel` ainda tem `default="admin"` no mapping (contradiz o fail-safe do #84) (bug-seg, low).
- **[#99](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/99)** — scrubber de log não mascara telefone BR sem espaço (enhancement-seg, low).
- **[#100](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/100)** — testes de estoque order-dependent (falham isolados) (bug, low).

Nits LOW/INFO não-acionados (documentados nos reviews): repo-alloc em loop no adapter de estoque; probe `pg_stat_activity` global nos testes de concorrência (só sob `pytest-xdist`); cartão de crédito não-mascarado pelo scrubber.

---

## 🎬 Tier 0 — ANTES de gravar o vídeo (decide nota)

Faixa delivery-facing e/ou confirmada ao vivo. É o que o avaliador vê primeiro (o vídeo abre no README) e o que uma banca refuta com um teste de uma linha. **Fechar tudo aqui antes de gravar.**

- [x] **[#81](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/81)** — `/saude` exempt do rate-limit — **bug** · prioridade **alta** · esforço **⚡ trivial** · **Status: ✅ fechado (PR #88, merge --admin)**
  - **Detalhes iniciais:** aplicar `@limiter.exempt` em `saude()` ([`../../src/compartilhado/interfaces/router_publico.py:45`](../../src/compartilhado/interfaces/router_publico.py)); o limite global vive em [`../../src/compartilhado/interfaces/middleware.py:157`](../../src/compartilhado/interfaces/middleware.py). As probes `liveness`/`readiness` saem todas de um IP só; com ≥4 pods o agregado estoura `60/min` e o kubelet recebe `429` → mata o pod → **restart storm auto-reforçante** que **derrota o HPA** (reproduzido: 5 pods reiniciaram). Sem isso, a demo do auto-scaling — **requisito explícito do vídeo** — quebra ao vivo. *Ponto de partida; ver a issue para confirmar que nenhuma outra rota pública precisa do mesmo tratamento.*

- [x] **[#77](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/77)** — README congelado (delivery-facing) — **doc-bug** · prioridade **alta** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #89, merge --admin)**
  - **Detalhes iniciais:** o README é o primeiro documento que a banca lê (o roteiro do vídeo abre nele) e está defasado. E-mail do admin `.local` → `.dev` ([`../../README.md:157`](../../README.md)); copiar o bloco **Mermaid** atualizado de [`../entrega/fase2/entrega-fase-2.md`](../entrega/fase2/entrega-fase-2.md) (com **relay / redis / prometheus**, que o diagrama atual não tem); completar a tabela de **ADRs 022/023/024** (hoje para na 021); mudar **RFC-002** de "Proposta" → "Aceita" (o próprio [`rfc-002-...:8`](../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) já diz "Aceita"); corrigir a cobertura **97,5% → 95,34%** (número do pacote de entrega). Bate direto no requisito "diagrama com componentes + infraestrutura". *Ponto de partida; ver a issue para a lista completa de pontos a reconciliar.*

- [x] **[#78](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/78)** — BDD fictício na estratégia de testes — **doc-bug** · prioridade **alta** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #91, merge --admin)**
  - **Detalhes iniciais:** a Seção 7 de [`../qualidade/estrategia-testes.md`](../qualidade/estrategia-testes.md) descreve BDD/`pytest-bdd` e arquivos `.feature` como **entregues** — não existem (zero `.feature`, sem `pytest-bdd` no `pyproject.toml`, ADR-013 ainda "Proposta"). Reescrever a seção como **planejado** (não entregue), remover a árvore fictícia `tests/e2e/features`, ajustar a pirâmide de testes ao real (~91% unitário / ~9% integração / ~0% E2E) e corrigir os comandos (markers reais, `-c pyproject.toml`). *Ponto de partida; ver a issue para validar os números da pirâmide contra a suíte atual.*

- [x] **[#79](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/79)** — staleness de documentação — **doc** · prioridade **média** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #92, merge --admin)**
  - **Detalhes iniciais:** vários comentários/documentos descrevem o estado anterior do sistema. Comentários **TD-015 stale** ("API migra no boot" — falso, o Job `pytstop-migrate` migra) em [`../../relay/__main__.py:6`](../../relay/__main__.py) (e `k8s/secret.yaml`); a [entrega](../entrega/fase2/entrega-fase-2.md) **subvende** os TDs (mostra ~5, o ledger tem **18 resolvidos**); a [matriz de rastreabilidade](../requisitos/matriz-rastreabilidade.md) congelada na fase 1 (sem RF-020..024); **ADR-024:88** atribui o Service de métricas à ADR-022; corpo stale da **ADR-020**; o roteiro do vídeo fecha "ADRs 015–023" mas demonstra a **024**. *Ponto de partida; ver a issue para o inventário completo dos pontos stale.*

- [x] **[#74](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/74)** — validar JWT/segredos no startup — **bug-seg** · prioridade **alta** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #94, merge --admin; +#95/#96 follow-ups)**
  - **Detalhes iniciais:** os RFCs afirmam que o `JWT_SECRET` é "validado no startup", mas o código só checa **não-vazio** — o serviço sobe com um segredo de **1 byte** (HS256 forjável). Adicionar uma `validar_segredos_no_startup()` no `lifespan`: rejeitar `len(JWT_SECRET) < 32` **e** uma **denylist** dos segredos demo (JWT/webhook/`ENCRYPTION_KEY`, públicos no git) quando `ENVIRONMENT=production`. Fecha de uma vez a divergência doc↔código e **torna verdadeira** a afirmação dos RFCs. *Ponto de partida; ver a issue — o guard de produção pode absorver o escopo do #75 dependendo de como for fatiado.*

---

## 🔒 Tier 1 — Segurança doc-vs-código

Padrão sistêmico de maior alavanca: a documentação vende um controle que o código não implementa. Não é requisito do enunciado, mas cada divergência é refutável com um teste mínimo — fecha a superfície de ataque da banca.

- [ ] **[#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75)** — gates de CI de segurança + triar 39 Dependabot — **bug-seg** · prioridade **média** · esforço **🟡 médio** · **Status: ⏭️ DEFERIDO** — é mudança de **workflow do CI**, não validável com o **CI travado no billing** (a regra "passar o CI local" não cobre "o job novo roda verde"); + a triagem dos 39 Dependabot é substancial. **Atacar após destravar o billing.**
  - **Detalhes iniciais:** os documentos de segurança ([relatorio-vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md), [plano-seguranca](../seguranca/plano-seguranca.md)) afirmam `pip-audit`/`gitleaks`/`trivy`/`CodeQL` "no pipeline CI" — o único gate de segurança em PR hoje é `bandit --severity high`. Tornar os gates **reais** (jobs de PR) **OU** alinhar os documentos ao que de fato roda; ampliar o escopo do `bandit` (`relay/`/`scripts/`, hoje fora) para casar com o Makefile; triar os alertas do Dependabot. *Ponto de partida; ver a issue para decidir gate-real vs corrigir-doc por ferramenta.*

- [x] **[#84](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/84)** — registro de usuário vira sempre ADMIN — **bug-seg** · prioridade **alta** · esforço **🟡 médio** · **Status: ✅ fechado (PR #97, merge --admin)**
  - **Detalhes iniciais:** `Usuario.criar` tem default `papel=ADMIN` ([`../../src/autenticacao/dominio/usuario.py:13,38`](../../src/autenticacao/dominio/usuario.py)) e o `RegistrarRequest` não tem campo `papel` → **qualquer registro pela API vira ADMIN** e o RBAC fica anulado. Adicionar `papel` validado no `RegistrarRequest`/DTO e **remover o default perigoso** da factory (`extra=forbid` já cobre mass-assignment, então o campo explícito é seguro). *Ponto de partida; ver a issue para decidir o papel default seguro do registro público.*

- [x] **[#86](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/86)** — PII vaza em tracebacks — **bug-seg** · prioridade **alta** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #98, merge --admin; +#99 follow-up)**
  - **Detalhes iniciais:** a ordem dos processors está invertida (`scrub_pii` **antes** de `format_exc_info` em [`../../src/compartilhado/infraestrutura/logging.py:128`](../../src/compartilhado/infraestrutura/logging.py)) → o traceback é montado depois do scrub e nunca é mascarado. Reordenar (`format_exc_info` **antes** de `scrub_pii`) **e** rotear o logging stdlib (handler 500) pelo `ProcessorFormatter` com `scrub_pii` no `foreign_pre_chain`. Viola o controle LGPD que o projeto vende. *Ponto de partida; ver a issue para confirmar todos os caminhos de log que despejam traceback cru.*

---

## 🐛 Tier 2 — Concorrência (BUNDLE #82 + #83)

Correções de concorrência acopladas — mesma classe (load sem lock) e uma já confirmada ao vivo. **Atacar como bundle:** a história para a banca ("transições e estoque são serializados sob carga") só fica coerente se as duas fecharem juntas.

- [x] **[#82](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/82)** — transições de OS sem lock → e-mails duplicados *(confirmado ao vivo)* — **bug** · prioridade **alta** · esforço **🟡 médio** · **Status: ✅ fechado (PR #101, bundle, merge --admin)**
  - **Detalhes iniciais:** 5× `POST .../diagnostico` concorrentes na **mesma OS** retornaram **5×200** (esperado 1×200 + 4×409) → **5 eventos + 5 e-mails** ao cliente. Não há optimistic lock (sem coluna `version`) nem `FOR UPDATE` no load. Aplicar **optimistic lock** (`version_id_col`) **ou** `SELECT ... FOR UPDATE` no carregamento da OS ([`../../src/ordem_servico/aplicacao/use_cases.py:137`](../../src/ordem_servico/aplicacao/use_cases.py); load em [`../../src/ordem_servico/infraestrutura/repository.py:78`](../../src/ordem_servico/infraestrutura/repository.py)). *Ponto de partida; ver a issue para decidir optimistic vs pessimista — pesa o efeito sobre os outros use cases que carregam a OS.*

- [x] **[#83](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/83)** — lost-update na reserva de estoque — **bug** · prioridade **média** · esforço **🟡 médio** · **Status: ✅ fechado (PR #101, bundle, merge --admin)**
  - **Detalhes iniciais:** `reservar`/`liberar` ([`../../src/ordem_servico/infraestrutura/adapters.py:43,58`](../../src/ordem_servico/infraestrutura/adapters.py)) usam `session.get` **sem lock**; só `AjustarQuantidade` usa `FOR UPDATE` → aprovações concorrentes podem **sobre-vender**. Aplicar `FOR UPDATE` no caminho de reserva (reusar `obter_por_id(com_lock=True)`), adquirindo os locks em **ordem de `id`** (anti-deadlock). **Atacar junto com #82.** *Ponto de partida; ver a issue para o ordering de locks quando uma aprovação reserva múltiplos itens.*

---

## 🛡️ Tier 3 — Robustez / LGPD (BUNDLE #72 + #76)

Robustez sem exposição direta na entrega, mas com risco real — e um bundle LGPD (erasure que não cascateia + erasure sem controle/auditoria) que conta como uma narrativa só de conformidade.

- [x] **[#73](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/73)** — guard de `ENCRYPTION_KEY` — **bug-seg** · prioridade **média** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #103)**
  - **Resolução:** `validar_segredos_no_startup` aborta o boot em produção sem `ENCRYPTION_KEY`; `decrypt` distingue legado (sem prefixo `gAAAAA` → devolve) de falha real (prefixo + `InvalidToken` → levanta), sem fail-open. Teste de mesa na imagem final.

- [ ] **[#72](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/72)** — LGPD: erasure não cascateia para veículos — **bug-seg** · prioridade **média** · esforço **🟡 médio** · **Status: ⏸️ deferido (plano na issue)**
  - **Deferido:** `placa` é `String(7)` unique (tombstone longo não cabe) e `ordens_de_servico.veiculo_id` é FK NOT NULL (delete quebra histórico) → exige **migração** (alargar a coluna) + **sentinela de domínio** + tratamento no read-path. Plano investigado registrado na issue; mais complexo que os demais, fica para uma sessão focada.

- [x] **[#76](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/76)** — LGPD: erasure/export sem restrição nem auditoria — **bug-seg** · prioridade **média** · esforço **🟢 baixo** · **Status: ✅ fechado (PR #104)**
  - **Resolução:** erasure restrito a **admin**; export e delete emitem evento de auditoria structlog (ator do JWT + `cliente_id`) após confirmar o efeito (404 não audita); `_ator_de` extraído para `compartilhado/interfaces/auditoria.py`. Teste de mesa na chain real: ator preservado, zero PII no log.

---

## 🏗️ Tier 4 — Débito de hardening (ledger; melhor ROI primeiro)

Compromissos **aceitos/justificados** no ledger ([README.md](README.md)) — não são bugs. Atacar por valor-de-nota e ROI; nenhum é exigido pela fase 2.

- [x] **TD-024** — `securityContext` nos workloads k8s — esforço **médio** · **Status: ✅ fechado (PR #108)**
  - **Resolução:** pod+container `securityContext` (`runAsNonRoot`, `runAsUser/fsGroup 1001`, seccomp, `allowPrivilegeEscalation:false`, `readOnlyRootFilesystem`, `capabilities.drop:[ALL]`) + `emptyDir` `/tmp` nos 3 workloads próprios; UID 1001 pinado no Dockerfile. Teste de mesa kind: pods Running, `/saude` 200, heartbeat em `/tmp`.

- [x] **TD-025** · **TD-031** · **TD-029** · **TD-028** — quick-wins (⚡/🟢) — **Status: ✅ fechados**
  - **Resolução:** **TD-025** (PR #107) índice B-tree `ix_itens_da_ordem_item_estoque_id` (migração 005; EXPLAIN confirma Index Scan); **TD-031** (PR #106) `--cov-fail-under=95` explícito no `ci.yml`; **TD-029** (PR #105) `obter_usuario_atual` exige `type == "access"`; **TD-028** (PR #105) pré-hash `base64(sha256(senha))` antes do bcrypt + fallback legado ≤72 bytes.

- [~] **TD-027** · **TD-026** · **TD-030** — médios (🟡) — **Status: TD-026/TD-030 ✅ (decisão) · TD-027 ⏸️ deferido**
  - **Resolução:** **TD-026** documentado em `k8s/README.md` (deploy fora do pipeline não-suportado); **TD-030** documentado em `docs/arquitetura/eventos-de-dominio.md` (8 eventos órfãos = intenção de modelagem). **TD-027** (webhook HMAC) **deferido**: o esquema atual é MVP documentado (ADR-021) e a evolução exige ripple no caller (e2e + postman da entrega + ADR) — risco alto às vésperas da entrega.

---

## ✨ Tier 5 — Feature / aceitar

- [ ] **[#80](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/80)** — orçamento complementar — **feature** · prioridade **BAIXA** · **Status: aberto**
  - **Detalhes iniciais:** ⚠️ **Confirmado no PDF oficial: NÃO é requisito do desafio** — o enunciado pede **6 status** e nenhum re-orçamento; a RN-007 (sem novos itens em `EM_EXECUCAO`) é **by-design**. Não é bug de RF. O reframe correto é **claim-vs-código**: ou **corrigir** o `prd`/`glossario` que prometem o complemento, **ou** relaxar a RN-007 — uma decisão de produto, não uma correção de requisito. *Ponto de partida; ver o comentário na issue para a decisão de escopo.*

- **Aceitar, não atacar** (débito deliberado, valor marginal): **TD-002** · **TD-004** · **TD-006** · **TD-013** · **TD-014**. Permanecem no ledger ([README.md](README.md)) como simplificações justificadas; não há ação planejada para a fase 2.

---

## Corte natural

O **Tier 0** (#81 / #77 / #78 / #79 / #74) é o corte que **decide a nota** e deve fechar **antes de gravar o vídeo** (~1–2 dias de trabalho): é a faixa delivery-facing + confirmada ao vivo que o avaliador vê primeiro e refuta com um teste de uma linha. **Tier 1–5** é **backlog pós-entrega** — valor de qualidade e credibilidade, sem bloquear a submissão.

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)
