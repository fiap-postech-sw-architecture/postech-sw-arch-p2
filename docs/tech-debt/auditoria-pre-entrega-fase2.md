# Auditoria Pré-Entrega — Fase 2

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)

> **Versão**: 1.0 (2026-06-28) — Síntese de auditoria pré-entrega da fase 2: teste de mesa profundo no cluster kind + review estruturado em 6 dimensões. Achados priorizados em P0/P1/P2/P3, candidatos a PR próprio. TD-010 é o único item já fechado (mesmo PR desta auditoria, #71).

Relatório de síntese da auditoria de fechamento da fase 2: consolida os achados acionáveis encontrados num teste de mesa profundo do sistema rodando no cluster, cruzado com um review estruturado e cético do repositório.

## Metadados

| Campo | Valor |
|---|---|
| **Data** | 2026-06-28 |
| **Método** | Teste de mesa profundo no cluster `kind` (UI por automação + carga real para exercitar HPA/concorrência) + review estruturado em 6 dimensões (arquitetura, segurança, correção/domínio, infra/k8s, observabilidade, documentação) conduzido por sub-agentes |
| **Escopo** | Todo o repositório (`src/`, `relay/`, `k8s/`, `.github/`, `scripts/`, `ui/`, `migrations/`) + o pacote de entrega (`README.md`, `docs/`, roteiro do vídeo) |

## Disclaimer (leia antes de agir)

- **Nada nesta lista foi corrigido.** A única exceção é **TD-010** (SonarQube), fechado por decisão no mesmo PR desta auditoria. Todos os demais itens permanecem **abertos**.
- **Cada item é candidato a um PR próprio + teste de mesa.** Não tratar esta lista como um único patch: a maior parte são correções independentes que tocam código e docs distintos.
- Findings marcados **[confirmado ao vivo]** foram **reproduzidos no cluster** (teste de mesa). Os demais vêm do **review estruturado** — conduzido de forma cética, com falsos-positivos já filtrados (cada afirmação foi confrontada com o código antes de entrar aqui).
- A severidade segue o emoji: 🔴 (P0/crítico), 🟠 (alto), 🟡 (médio/baixo).

## Veredito geral

O sistema é **forte e está acima do nível "nota 10"**: arquitetura DDD/Clean sólida (import-linter com 3 contratos *kept*), outbox/relay com qualidade de produção (claim-then-deliver, fencing de lease, backoff/DLQ), RBAC imutável, JWT bem fixado, SQL 100% parametrizado, 1481 testes unitários e gate de cobertura de 95% real.

Apesar disso, a auditoria encontrou **3 bugs confirmados ao vivo** e — mais importante como padrão sistêmico — **vários documentos afirmam controles que o código não entrega**. Uma banca adversarial refuta boa parte desses controles com um teste de uma linha. O meta-padrão de maior alavanca da lista é **alinhar documentação ↔ código**.

---

## P0 — Confirmados ao vivo / delivery-facing

Itens com impacto direto na entrega (o avaliador vê) ou reproduzidos ao vivo no cluster.

### 1. 🔴 [confirmado ao vivo] `/api/v1/saude` cai no rate-limit → restart storm sob HPA

As probes de `liveness` + `readiness` saem todas de um único IP (`10.244.0.1`). Com **≥4 pods**, o agregado de probes excede o limite global `60/min` → o kubelet recebe `429` no health check → mata o pod. Reproduzido: **5 pods reiniciaram**. O efeito é **auto-reforçante**: escalar piora (mais pods = mais probes do mesmo IP). Isso **derrota o HPA** (RNF-020 / RNF-023).

- **Onde:** `saude()` em [`../../src/compartilhado/interfaces/router_publico.py:45`](../../src/compartilhado/interfaces/router_publico.py); limite global em [`../../src/compartilhado/interfaces/middleware.py:157`](../../src/compartilhado/interfaces/middleware.py).
- **Fix:** aplicar `@limiter.exempt` em `saude()` (health checks nunca devem contar para o rate limit).

### 2. 🔴 README congelado antes de relay/redis/prometheus (delivery-facing — o vídeo abre no README)

O [`../../README.md`](../../README.md) está desatualizado em pontos que a banca lê primeiro (o roteiro do vídeo abre nele):

- `README.md:157` — e-mail do admin **errado** (`.local` → deveria ser `.dev`).
- `README.md:35-74` — diagrama Mermaid **sem relay / redis / prometheus**, violando o próprio comentário "fonte única RFC-002 §3".
- Tabela de ADRs **para na 021** (faltam 022, 023, 024).
- RFC-002 marcada como "Proposta" no README, mas [`rfc-002-infraestrutura-e-deploy-fase-2.md:8`](../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) diz "Aceita".
- Cobertura citada no README como **97,5%**, vs **95,34%** no pacote de entrega.
- **Fix:** copiar o bloco Mermaid de [`entrega-fase-2.md`](../entrega/fase2/entrega-fase-2.md), completar a tabela de ADRs, corrigir status da RFC-002 e o número de cobertura.

### 3. 🔴 `docs/qualidade/estrategia-testes.md` descreve BDD/pytest-bdd como entregue, mas não existe

A seção 7 ([`estrategia-testes.md:151-181`](../qualidade/estrategia-testes.md)) cita arquivos `.feature` em `tests/e2e/features/`. Realidade: **zero** arquivos `.feature`, **sem** `pytest-bdd` no `pyproject.toml`, e a ADR-013 segue "Proposta".

- **Fix:** reescrever a seção como **planejado** (não entregue) e ajustar a pirâmide de testes 70/20/10 para o real (~91% unitário / ~9% integração / ~0% E2E).

### 4. 🟠 [confirmado ao vivo] Transições de OS sem lock → eventos/e-mails duplicados

5× `POST .../diagnostico` concorrentes na **mesma OS** resultaram em **5×200** (esperado: 1×200 + 4×409) → **5 eventos emitidos + 5 e-mails** ao cliente. Não há optimistic lock (não existe coluna `version`) nem `FOR UPDATE` no carregamento da OS.

- **Onde:** [`../../src/ordem_servico/aplicacao/use_cases.py:137`](../../src/ordem_servico/aplicacao/use_cases.py) e [`../../src/ordem_servico/infraestrutura/repository.py:78`](../../src/ordem_servico/infraestrutura/repository.py).
- **Fix:** `version_id_col` (optimistic) **ou** `SELECT ... FOR UPDATE` no load. (Estoque já está protegido por `with_for_update`.)

---

## P1 — Segurança: docs afirmam controle que o código não tem

Padrão recorrente: a documentação vende um controle de segurança que o código **não implementa**. Uma banca adversarial refuta cada um com um teste mínimo.

### 5. 🔴 Força mínima do `JWT_SECRET` (≥32 bytes) NÃO é validada

Apesar de [`k8s/secret.yaml:11`](../../k8s/secret.yaml), [`rfc-002-...:210`](../arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) e da RFC-001 (`:245`) afirmarem que o segredo é "validado no startup", o código só checa **não-vazio** ([`../../src/autenticacao/interfaces/dependencies.py:20-26`](../../src/autenticacao/interfaces/dependencies.py)). O serviço sobe com um segredo de **1 byte** → HS256 forjável.

- **Fix:** rejeitar `len < 32` no boot.

### 6. 🔴 Sem guarda contra segredos DEMO em produção

`ENVIRONMENT=production` ([`../../src/main.py:144`](../../src/main.py)) só desliga `/docs`; **não rejeita** os segredos de demo de JWT/webhook/`ENCRYPTION_KEY` (que estão públicos no git). Pior: o [`k8s/configmap.yaml`](../../k8s/configmap.yaml) fixa `ENVIRONMENT: development` no cluster.

- **Fix:** uma função `validar_segredos_producao()` no boot — fecha **#5 e #6** de uma vez.

### 7. 🔴 Gates de CI de segurança não existem, mas os docs dizem que rodam

O único gate de segurança em PR é `bandit --severity high` ([`.github/workflows/ci.yml:62`](../../.github/workflows/ci.yml)). **Não há** `pip-audit` / `gitleaks` / `trivy` / `CodeQL` rodando em workflow de PR. Mas [`relatorio-vulnerabilidades.md:122,158`](../seguranca/relatorio-vulnerabilidades.md) e [`plano-seguranca.md:23`](../seguranca/plano-seguranca.md) afirmam "no pipeline CI" — **falso**.

- **Fix:** adicionar os jobs reais **OU** corrigir os documentos para refletir o que de fato roda.

### 8. 🔴 Todo usuário criado pela API vira ADMIN (cross-confirmado: arquitetura + segurança)

`Usuario.criar` tem default `papel=ADMIN` ([`../../src/autenticacao/dominio/usuario.py:13,38`](../../src/autenticacao/dominio/usuario.py)); o `RegistrarRequest` não tem campo `papel`; e [`use_cases.py:40`](../../src/autenticacao/aplicacao/use_cases.py) chama a factory sem papel. Na prática, o RBAC fica **anulado** — qualquer registro vira ADMIN.

- **Fix:** campo `papel` validado no request + remover o default perigoso. (`extra=forbid` já protege contra mass-assignment, então o campo explícito é seguro.)

### 9. 🔴 PII vaza em tracebacks

A ordem dos processors está invertida (`scrub_pii` **antes** de `format_exc_info`, [`../../src/compartilhado/infraestrutura/logging.py:128`](../../src/compartilhado/infraestrutura/logging.py)) → o traceback é montado **depois** do scrub e nunca é mascarado. Além disso, o logging stdlib do handler 500 ([`../../src/compartilhado/interfaces/error_handler.py:23,94`](../../src/compartilhado/interfaces/error_handler.py)) despeja o traceback cru. Viola o controle LGPD que o projeto vende.

- **Fix:** reordenar os processors (`format_exc_info` antes de `scrub_pii`) **e** rotear o logging stdlib pelo `ProcessorFormatter` com `scrub_pii` no `foreign_pre_chain`.

---

## P2 — Correção / robustez

Bugs e fragilidades de robustez sem exposição direta na entrega, mas com risco real.

- 🟠 **Lost-update na reserva de estoque.** `reservar` / `liberar` ([`../../src/ordem_servico/infraestrutura/adapters.py:43,58`](../../src/ordem_servico/infraestrutura/adapters.py)) usam `session.get` sem lock. `AjustarQuantidade` usa `FOR UPDATE`, mas o caminho de **reserva** não → aprovações concorrentes podem **sobre-vender**. **Fix:** `FOR UPDATE` no caminho de reserva (reusar `obter_por_id(com_lock=True)`), adquirindo os locks em **ordem de `id`** (anti-deadlock).
- 🟠 **Erasure LGPD não cascateia para veículos (cross-confirmado).** `anonimizar_dados` ([`../../src/cliente_veiculo/infraestrutura/repository.py:104-115`](../../src/cliente_veiculo/infraestrutura/repository.py)) só toca a tabela `clientes`; a **placa** (PII) e o `cliente_id` sobrevivem nos veículos. **Fix:** anonimizar os veículos na mesma transação.
- 🟠 **`ENCRYPTION_KEY` ausente → fallback efêmero silencioso + `decrypt` fail-open** ([`../../src/compartilhado/infraestrutura/encryption.py:33-67`](../../src/compartilhado/infraestrutura/encryption.py)). Em produção sem a chave: dados ficam **irrecuperáveis** após restart, e o `documento_hash` **diverge** entre réplicas. **Fix:** abortar o boot em produção sem a chave; o `decrypt` deve distinguir dado legado de falha de integridade (não fail-open).
- 🟠 **Orçamento complementar inerte [confirmado ao vivo].** No estado `EM_EXECUCAO` a OS não aceita novos itens (`POST /itens` retorna 409 — `_ESTADOS_PERMITE_ITENS` em [`../../src/ordem_servico/dominio/ordem_de_servico.py:35`](../../src/ordem_servico/dominio/ordem_de_servico.py)) → o orçamento complementar re-emite idêntico e **não cobra o trabalho extra**. **Fix:** permitir itens em `EM_EXECUCAO` ou um caminho dedicado de complemento.
- 🟠 **`securityContext` ausente em todos os workloads k8s.** É o hardening de k8s mais esperado (Aula 05). Imagens de terceiros rodam como **root**. **Fix:** `runAsNonRoot` / `allowPrivilegeEscalation: false` / `capabilities.drop: [ALL]` / `readOnlyRootFilesystem` (o relay precisa de um `emptyDir` em `/tmp`).
- 🟡 **Refresh token aceito como access token.** O `type` do token não é checado em `obter_usuario_atual` ([`../../src/compartilhado/interfaces/middleware.py:25-49`](../../src/compartilhado/interfaces/middleware.py)). Contido hoje pelo RBAC (403), mas latente. **Fix:** `if type != "access": 401`.
- 🟡 **LGPD: atendente apaga/exporta qualquer cliente, sem auditoria** ([`../../src/cliente_veiculo/interfaces/router.py:161-193`](../../src/cliente_veiculo/interfaces/router.py)). **Fix:** restringir erasure a **admin** + registrar log de auditoria (como o admin de outbox já faz).
- 🟡 **Webhook: segredo estático sem HMAC** ([`../../src/compartilhado/interfaces/router_publico.py:99-131`](../../src/compartilhado/interfaces/router_publico.py)) — sujeito a replay/forja se o segredo vazar. **Fix:** assinatura HMAC-SHA256 (`ordem_id` + `timestamp` + body) com janela anti-replay de ±5min.
- 🟡 **bandit do CI não varre `relay/` nem `scripts/`.** [`ci.yml:63`](../../.github/workflows/ci.yml) tem como alvo `src ui`, enquanto o Makefile usa `src ui relay scripts`. **Fix:** alinhar o escopo do CI ao do Makefile.

---

## P3 — Consistência / docs / polish

Itens de menor severidade: consistência documental, comentários stale, otimizações marginais.

- **Comentários stale do TD-015 (cross-confirmado 3×):** [`relay/__main__.py:5-6`](../../relay/__main__.py) e [`k8s/secret.yaml:22-23`](../../k8s/secret.yaml) ainda dizem "API migra no boot" — **falso** (o Job `pytstop-migrate` migra; `RUN_MIGRATIONS_ON_STARTUP=false`).
- [`entrega-fase-2.md:136-147`](../entrega/fase2/entrega-fase-2.md) mostra só ~5 TDs (o ledger tem **18 resolvidos**) → **subvende** o trabalho; ainda marcado "v1.2".
- [`matriz-rastreabilidade.md`](../requisitos/matriz-rastreabilidade.md) congelada na fase 1 (sem RF-020..024); [`docs/requisitos/README.md`](../requisitos/README.md) não linka os documentos da fase 2.
- **ADR-024** (`:88`) atribui o Service `pytstop-relay-metrics` à ADR-022 (não é definido lá); **ADR-020** tem corpo stale ("pode terminar Proposta") apesar de "Aceita" + a supersessão parcial pela 024 não está marcada no Status; o roteiro (`:133`) fecha "ADRs 015–023" mas demonstra a **024**.
- Sem índice em `itens_da_ordem.item_estoque_id` (seq scan no `DesativarItemEstoque`, [`../../src/ordem_servico/infraestrutura/repository.py:169`](../../src/ordem_servico/infraestrutura/repository.py)).
- A ordenação migração-antes-do-rollout só é garantida **pelo pipeline** (não pelo cluster) → adicionar Helm hook / initContainer **ou** documentar "deploy fora do pipeline não-suportado".
- Gate de cobertura de `src/` é implícito via `.coveragerc` → **explicitar** `--cov-fail-under=95` no step.
- bcrypt **trunca em 72 bytes** (pwdlib sem pré-hash); [`scripts/seed_usuarios.py`](../../scripts/seed_usuarios.py) sem guarda de `ENVIRONMENT`; metrics-server pinado em `latest`; vulns aceitas (nicegui / imagem HIGH) adiadas "para a fase 2" — que **já chegou**; [`ui/cliente_api.py:502`](../../ui/cliente_api.py) retorna `.json()` sob `type: ignore`.
- **Eventos de domínio órfãos** (8 de 11 são emitidos sem consumidor nem persistência — `estoque` / `cliente_veiculo` / `catalogo` não têm dispatcher) → **documentar como "intenção de modelagem, sem consumidor na fase 2"** para a banca não ler como bug. Idem: `ItemEstoque.liberar()` sem limite superior; e a política de reserva (quais estados seguram estoque) vive no use case, não no agregado.

---

## Como usar esta lista

Ordem de priorização recomendada:

1. **P0** — confirmados ao vivo + delivery-facing. Risco direto na avaliação e na demo.
2. **P1** — doc-vs-código de segurança. É o que uma banca refuta com um teste de 1 linha.
3. **P2** — correção / robustez.
4. **P3** — polish e consistência documental.

Regras:

- **Cada item vira um PR próprio + teste de mesa.** Manter o padrão do [plano-ataque](plano-ataque.md): PR pequeno, focado, com todos os docs afetados no mesmo PR e gates verdes antes de abrir.
- O **meta-padrão de maior alavanca** é alinhar **doc ↔ código** — toda a faixa P1, mais os itens **#2** (README) e **#3** (estratégia de testes). Corrigir essa classe de divergência remove a maior superfície de ataque da banca de uma vez.

> [↑ Raiz do projeto](../../README.md) · [↑ Dívida Técnica](README.md)
