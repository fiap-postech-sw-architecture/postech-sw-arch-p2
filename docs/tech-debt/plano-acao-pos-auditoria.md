# Plano de Ação — Pós-Auditoria Pré-Entrega (Fase 2)

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)

> **Versão**: 1.0 (2026-06-28) — Plano de ataque unificado e **resumível entre sessões** para os achados da auditoria pré-entrega da fase 2. Dirigido a checkbox: marque o item quando o PR mergear. Fontes: [auditoria-pre-entrega-fase2.md](auditoria-pre-entrega-fase2.md) (achados), as GitHub issues #72–#86 (bugs/docs/feature) e o ledger TD-024..031 ([README.md](README.md)). A ordem segue **impacto na nota** (delivery-facing + refutável pela banca) **>** severidade do bug confirmado **>** ROI.

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

> **Progresso: 0/14 issues + 0/8 TDs.** (Atualize a cada merge. As 14 issues são #72–#86; #85 é controle/meta e não conta como item de correção neste plano. Os 8 TDs são TD-024..TD-031.)

---

## 🎬 Tier 0 — ANTES de gravar o vídeo (decide nota)

Faixa delivery-facing e/ou confirmada ao vivo. É o que o avaliador vê primeiro (o vídeo abre no README) e o que uma banca refuta com um teste de uma linha. **Fechar tudo aqui antes de gravar.**

- [ ] **[#81](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/81)** — `/saude` exempt do rate-limit — **bug** · prioridade **alta** · esforço **⚡ trivial** · **Status: aberto**
  - **Detalhes iniciais:** aplicar `@limiter.exempt` em `saude()` ([`../../src/compartilhado/interfaces/router_publico.py:45`](../../src/compartilhado/interfaces/router_publico.py)); o limite global vive em [`../../src/compartilhado/interfaces/middleware.py:157`](../../src/compartilhado/interfaces/middleware.py). As probes `liveness`/`readiness` saem todas de um IP só; com ≥4 pods o agregado estoura `60/min` e o kubelet recebe `429` → mata o pod → **restart storm auto-reforçante** que **derrota o HPA** (reproduzido: 5 pods reiniciaram). Sem isso, a demo do auto-scaling — **requisito explícito do vídeo** — quebra ao vivo. *Ponto de partida; ver a issue para confirmar que nenhuma outra rota pública precisa do mesmo tratamento.*

- [ ] **[#77](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/77)** — README congelado (delivery-facing) — **doc-bug** · prioridade **alta** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** o README é o primeiro documento que a banca lê (o roteiro do vídeo abre nele) e está defasado. E-mail do admin `.local` → `.dev` ([`../../README.md:157`](../../README.md)); copiar o bloco **Mermaid** atualizado de [`../entrega/fase2/entrega-fase-2.md`](../entrega/fase2/entrega-fase-2.md) (com **relay / redis / prometheus**, que o diagrama atual não tem); completar a tabela de **ADRs 022/023/024** (hoje para na 021); mudar **RFC-002** de "Proposta" → "Aceita" (o próprio [`rfc-002-...:8`](../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) já diz "Aceita"); corrigir a cobertura **97,5% → 95,34%** (número do pacote de entrega). Bate direto no requisito "diagrama com componentes + infraestrutura". *Ponto de partida; ver a issue para a lista completa de pontos a reconciliar.*

- [ ] **[#78](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/78)** — BDD fictício na estratégia de testes — **doc-bug** · prioridade **alta** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** a Seção 7 de [`../qualidade/estrategia-testes.md`](../qualidade/estrategia-testes.md) descreve BDD/`pytest-bdd` e arquivos `.feature` como **entregues** — não existem (zero `.feature`, sem `pytest-bdd` no `pyproject.toml`, ADR-013 ainda "Proposta"). Reescrever a seção como **planejado** (não entregue), remover a árvore fictícia `tests/e2e/features`, ajustar a pirâmide de testes ao real (~91% unitário / ~9% integração / ~0% E2E) e corrigir os comandos (markers reais, `-c pyproject.toml`). *Ponto de partida; ver a issue para validar os números da pirâmide contra a suíte atual.*

- [ ] **[#79](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/79)** — staleness de documentação — **doc** · prioridade **média** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** vários comentários/documentos descrevem o estado anterior do sistema. Comentários **TD-015 stale** ("API migra no boot" — falso, o Job `pytstop-migrate` migra) em [`../../relay/__main__.py:6`](../../relay/__main__.py) (e `k8s/secret.yaml`); a [entrega](../entrega/fase2/entrega-fase-2.md) **subvende** os TDs (mostra ~5, o ledger tem **18 resolvidos**); a [matriz de rastreabilidade](../requisitos/matriz-rastreabilidade.md) congelada na fase 1 (sem RF-020..024); **ADR-024:88** atribui o Service de métricas à ADR-022; corpo stale da **ADR-020**; o roteiro do vídeo fecha "ADRs 015–023" mas demonstra a **024**. *Ponto de partida; ver a issue para o inventário completo dos pontos stale.*

- [ ] **[#74](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/74)** — validar JWT/segredos no startup — **bug-seg** · prioridade **alta** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** os RFCs afirmam que o `JWT_SECRET` é "validado no startup", mas o código só checa **não-vazio** — o serviço sobe com um segredo de **1 byte** (HS256 forjável). Adicionar uma `validar_segredos_no_startup()` no `lifespan`: rejeitar `len(JWT_SECRET) < 32` **e** uma **denylist** dos segredos demo (JWT/webhook/`ENCRYPTION_KEY`, públicos no git) quando `ENVIRONMENT=production`. Fecha de uma vez a divergência doc↔código e **torna verdadeira** a afirmação dos RFCs. *Ponto de partida; ver a issue — o guard de produção pode absorver o escopo do #75 dependendo de como for fatiado.*

---

## 🔒 Tier 1 — Segurança doc-vs-código

Padrão sistêmico de maior alavanca: a documentação vende um controle que o código não implementa. Não é requisito do enunciado, mas cada divergência é refutável com um teste mínimo — fecha a superfície de ataque da banca.

- [ ] **[#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75)** — gates de CI de segurança + triar 39 Dependabot — **bug-seg** · prioridade **média** · esforço **🟡 médio** · **Status: aberto**
  - **Detalhes iniciais:** os documentos de segurança ([relatorio-vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md), [plano-seguranca](../seguranca/plano-seguranca.md)) afirmam `pip-audit`/`gitleaks`/`trivy`/`CodeQL` "no pipeline CI" — o único gate de segurança em PR hoje é `bandit --severity high`. Tornar os gates **reais** (jobs de PR) **OU** alinhar os documentos ao que de fato roda; ampliar o escopo do `bandit` (`relay/`/`scripts/`, hoje fora) para casar com o Makefile; triar os alertas do Dependabot. *Ponto de partida; ver a issue para decidir gate-real vs corrigir-doc por ferramenta.*

- [ ] **[#84](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/84)** — registro de usuário vira sempre ADMIN — **bug-seg** · prioridade **alta** · esforço **🟡 médio** · **Status: aberto**
  - **Detalhes iniciais:** `Usuario.criar` tem default `papel=ADMIN` ([`../../src/autenticacao/dominio/usuario.py:13,38`](../../src/autenticacao/dominio/usuario.py)) e o `RegistrarRequest` não tem campo `papel` → **qualquer registro pela API vira ADMIN** e o RBAC fica anulado. Adicionar `papel` validado no `RegistrarRequest`/DTO e **remover o default perigoso** da factory (`extra=forbid` já cobre mass-assignment, então o campo explícito é seguro). *Ponto de partida; ver a issue para decidir o papel default seguro do registro público.*

- [ ] **[#86](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/86)** — PII vaza em tracebacks — **bug-seg** · prioridade **alta** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** a ordem dos processors está invertida (`scrub_pii` **antes** de `format_exc_info` em [`../../src/compartilhado/infraestrutura/logging.py:128`](../../src/compartilhado/infraestrutura/logging.py)) → o traceback é montado depois do scrub e nunca é mascarado. Reordenar (`format_exc_info` **antes** de `scrub_pii`) **e** rotear o logging stdlib (handler 500) pelo `ProcessorFormatter` com `scrub_pii` no `foreign_pre_chain`. Viola o controle LGPD que o projeto vende. *Ponto de partida; ver a issue para confirmar todos os caminhos de log que despejam traceback cru.*

---

## 🐛 Tier 2 — Concorrência (BUNDLE #82 + #83)

Correções de concorrência acopladas — mesma classe (load sem lock) e uma já confirmada ao vivo. **Atacar como bundle:** a história para a banca ("transições e estoque são serializados sob carga") só fica coerente se as duas fecharem juntas.

- [ ] **[#82](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/82)** — transições de OS sem lock → e-mails duplicados *(confirmado ao vivo)* — **bug** · prioridade **alta** · esforço **🟡 médio** · **Status: aberto**
  - **Detalhes iniciais:** 5× `POST .../diagnostico` concorrentes na **mesma OS** retornaram **5×200** (esperado 1×200 + 4×409) → **5 eventos + 5 e-mails** ao cliente. Não há optimistic lock (sem coluna `version`) nem `FOR UPDATE` no load. Aplicar **optimistic lock** (`version_id_col`) **ou** `SELECT ... FOR UPDATE` no carregamento da OS ([`../../src/ordem_servico/aplicacao/use_cases.py:137`](../../src/ordem_servico/aplicacao/use_cases.py); load em [`../../src/ordem_servico/infraestrutura/repository.py:78`](../../src/ordem_servico/infraestrutura/repository.py)). *Ponto de partida; ver a issue para decidir optimistic vs pessimista — pesa o efeito sobre os outros use cases que carregam a OS.*

- [ ] **[#83](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/83)** — lost-update na reserva de estoque — **bug** · prioridade **média** · esforço **🟡 médio** · **Status: aberto**
  - **Detalhes iniciais:** `reservar`/`liberar` ([`../../src/ordem_servico/infraestrutura/adapters.py:43,58`](../../src/ordem_servico/infraestrutura/adapters.py)) usam `session.get` **sem lock**; só `AjustarQuantidade` usa `FOR UPDATE` → aprovações concorrentes podem **sobre-vender**. Aplicar `FOR UPDATE` no caminho de reserva (reusar `obter_por_id(com_lock=True)`), adquirindo os locks em **ordem de `id`** (anti-deadlock). **Atacar junto com #82.** *Ponto de partida; ver a issue para o ordering de locks quando uma aprovação reserva múltiplos itens.*

---

## 🛡️ Tier 3 — Robustez / LGPD (BUNDLE #72 + #76)

Robustez sem exposição direta na entrega, mas com risco real — e um bundle LGPD (erasure que não cascateia + erasure sem controle/auditoria) que conta como uma narrativa só de conformidade.

- [ ] **[#73](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/73)** — guard de `ENCRYPTION_KEY` — **bug-seg** · prioridade **média** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** `ENCRYPTION_KEY` ausente cai num **fallback efêmero silencioso** e o `decrypt` é **fail-open** ([`../../src/compartilhado/infraestrutura/encryption.py:33-67`](../../src/compartilhado/infraestrutura/encryption.py)) → em produção sem a chave, os dados ficam **irrecuperáveis** após restart e o `documento_hash` **diverge** entre réplicas. **Abortar o boot** em produção sem a chave e fazer o `decrypt` **distinguir dado legado de falha de integridade** (não fail-open). *Ponto de partida; ver a issue para a estratégia de migração de dado legado.*

- [ ] **[#72](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/72)** — LGPD: erasure não cascateia para veículos — **bug-seg** · prioridade **média** · esforço **🟡 médio** · **Status: aberto**
  - **Detalhes iniciais:** `anonimizar_dados` ([`../../src/cliente_veiculo/infraestrutura/repository.py:104`](../../src/cliente_veiculo/infraestrutura/repository.py)) só toca a tabela `clientes` → a **placa** (PII) e o `cliente_id` sobrevivem nos veículos. **Anonimizar os veículos na mesma transação. Bundle LGPD com #76.** *Ponto de partida; ver a issue para confirmar todas as colunas PII no agregado veículo.*

- [ ] **[#76](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/76)** — LGPD: erasure/export sem restrição nem auditoria — **bug-seg** · prioridade **média** · esforço **🟢 baixo** · **Status: aberto**
  - **Detalhes iniciais:** hoje um atendente apaga/exporta **qualquer** cliente, sem trilha ([`../../src/cliente_veiculo/interfaces/router.py:161-193`](../../src/cliente_veiculo/interfaces/router.py)). Restringir o erasure a **admin** + registrar **log de auditoria** (como o admin de outbox já faz). **Bundle LGPD com #72.** *Ponto de partida; ver a issue para o formato do registro de auditoria reusado do outbox.*

---

## 🏗️ Tier 4 — Débito de hardening (ledger; melhor ROI primeiro)

Compromissos **aceitos/justificados** no ledger ([README.md](README.md)) — não são bugs. Atacar por valor-de-nota e ROI; nenhum é exigido pela fase 2.

- [ ] **TD-024** — `securityContext` nos workloads k8s — esforço **médio** · **Status: aberto**
  - **Detalhes iniciais:** `runAsNonRoot` / `allowPrivilegeEscalation:false` / `capabilities.drop:[ALL]` / `readOnlyRootFilesystem` (o relay precisa de um `emptyDir` em `/tmp`). É o **melhor valor-de-nota dos TDs** — hardening de k8s é o mais esperado da **Aula 05** e imagens de terceiros rodam como root hoje. **Se quiser o sinal de maturidade de k8s no vídeo, este sobe de tier.** *Ponto de partida; ver o ledger ([README.md](README.md)) para a alternativa "documentar a decisão".*

- [ ] **TD-025** · **TD-031** · **TD-029** · **TD-028** — quick-wins (⚡/🟢) — **Status: aberto**
  - **Detalhes iniciais:** **TD-025** índice B-tree em `itens_da_ordem.item_estoque_id` (migração reversível; remove o seq scan do `DesativarItemEstoque`); **TD-031** explicitar `--cov-fail-under=95` no step de cobertura de `src/` (hoje implícito via `.coveragerc`); **TD-029** validar `type == "access"` em `obter_usuario_atual` (`if type != "access": 401`, espelhando o fluxo de refresh); **TD-028** pré-hash `base64(sha256(senha))` antes do bcrypt **ou** Argon2 (remove o truncamento em 72 bytes). Baixo esforço, baixo risco — bons para uma rodada de limpeza única. *Ponto de partida; ver o ledger ([README.md](README.md)) para o detalhe de cada um.*

- [ ] **TD-027** · **TD-026** · **TD-030** — médios (🟡) — **Status: aberto**
  - **Detalhes iniciais:** **TD-027** assinatura **HMAC-SHA256** no webhook de orçamento (`ordem_id` + `timestamp` + body, janela anti-replay ±5min) sobre o segredo estático atual; **TD-026** auto-enforçar a ordenação **migração-antes-do-rollout** (initContainer / Helm hook / sync-wave) **ou** documentar "deploy fora do pipeline não-suportado"; **TD-030** **documentar** os eventos de domínio órfãos como "intenção de modelagem, sem consumidor na fase 2" (para a banca não ler como bug) **ou** ligar os handlers. *Ponto de partida; ver o ledger ([README.md](README.md)) para as duas saídas de cada item.*

---

## ✨ Tier 5 — Feature / aceitar

- [ ] **[#80](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/80)** — orçamento complementar — **feature** · prioridade **BAIXA** · **Status: aberto**
  - **Detalhes iniciais:** ⚠️ **Confirmado no PDF oficial: NÃO é requisito do desafio** — o enunciado pede **6 status** e nenhum re-orçamento; a RN-007 (sem novos itens em `EM_EXECUCAO`) é **by-design**. Não é bug de RF. O reframe correto é **claim-vs-código**: ou **corrigir** o `prd`/`glossario` que prometem o complemento, **ou** relaxar a RN-007 — uma decisão de produto, não uma correção de requisito. *Ponto de partida; ver o comentário na issue para a decisão de escopo.*

- **Aceitar, não atacar** (débito deliberado, valor marginal): **TD-002** · **TD-004** · **TD-006** · **TD-013** · **TD-014**. Permanecem no ledger ([README.md](README.md)) como simplificações justificadas; não há ação planejada para a fase 2.

---

## Corte natural

O **Tier 0** (#81 / #77 / #78 / #79 / #74) é o corte que **decide a nota** e deve fechar **antes de gravar o vídeo** (~1–2 dias de trabalho): é a faixa delivery-facing + confirmada ao vivo que o avaliador vê primeiro e refuta com um teste de uma linha. **Tier 1–5** é **backlog pós-entrega** — valor de qualidade e credibilidade, sem bloquear a submissão.

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)
