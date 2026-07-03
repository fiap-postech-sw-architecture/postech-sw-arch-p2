# Scans de Segurança — Fechamento da Fase 2

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)

> **Versão**: 2.1 — adiciona a **sétima camada**: SonarQube como scan manual de fechamento (TD-010/[ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)) executado em 02/07/2026, com Quality Gate **Passed** e os 3 security hotspots levados a zero (1 corrigido no código, 2 revisados como seguros com justificativa) — antes/depois no Anexo B do documento de entrega.
>
> **Versão 2.0** — bateria de fechamento **reexecutada na HEAD final da fase 2** (commit [`5404826`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/commit/5404826), 02/07/2026), já sobre **Python 3.14** ([PR #150](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/150)). Sucede a versão 1.0 (12/06/2026), que cobria só `src/`+`ui/` e não reexecutou trivy; esta versão fecha o escopo — `src/`+`relay/` no SAST, deps de runtime na SCA, imagem 3.14 no scan de container, segredos, CodeQL e DAST — e incorpora os PRs de segurança posteriores a 12/06. Complementa o [relatório de vulnerabilidades](relatorio-vulnerabilidades.md) da fase 1, que permanece válido para o baseline OWASP API Top 10 do MVP.

## Escopo

Reexecução completa dos scans automatizados de segurança sobre o código da fase 2 na HEAD final, cobrindo as seis camadas do pipeline ([ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)):

- **SAST** (bandit) sobre `src/` + `relay/` — o `relay/` (Transactional Outbox, [PR #56](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/56)/[ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md)), ausente da bateria de 12/06, agora é varrido de primeira;
- **SCA de dependências** (pip-audit) sobre as dependências de **runtime** (produção), pós-migração consolidada de deps ([#143](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/143), redis 8) e upgrade do NiceGUI 3 ([#149](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/149));
- **SCA de imagem** (trivy) sobre a imagem de runtime **agora em Python 3.14** ([#150](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/150));
- **Detecção de segredos** (gitleaks) sobre a árvore de trabalho;
- **SAST semântico** (CodeQL, python + javascript-typescript);
- **DAST** (OWASP ZAP baseline) contra o OpenAPI vivo da stack compose.

Diferentemente da bateria de 12/06 — um scan local pontual — a bateria de fechamento **é o próprio CI**: a partir de [#116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116) (fecha [#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75)) os gates de pip-audit, gitleaks e trivy rodam em [`security.yml`](../../.github/workflows/security.yml); o bandit em [`ci.yml`](../../.github/workflows/ci.yml) (job `security`, escopo `src/ ui/ relay/ scripts/`); o CodeQL pelo *default setup* do GitHub (jobs `Analyze (python)` e `Analyze (javascript-typescript)`); e o ZAP baseline em [`full-test-ci.yml`](../../.github/workflows/full-test-ci.yml) ([TD-011](../tech-debt/README.md), [PR #65](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/65)). Todos os seis passaram **verdes na HEAD final** — a evidência abaixo é o resultado dessas execuções, e não mais um scan manual sem trilha.

> **Nota sobre os relatórios versionados:** os JSON em `docs/seguranca/*-report.json` (trivy, pip-audit, ZAP, gitleaks, bandit) são os artefatos da fase 1, preservados como baseline histórico — não são reescritos a cada bateria (o CI publica os seus próprios como artefatos de run). Os números desta versão 2.0 refletem o **estado da HEAD final** (lockfile e imagem em 3.14), que diverge do snapshot da fase 1 nos JSON versionados.

## Resumo

| Ferramenta | Tipo | Alvo | Resultado na HEAD final |
|---|---|---|---|
| bandit 1.9.4 | SAST | `src/` + `relay/` (10.112 LoC) | **0 high / 0 medium / 0 low** — nenhum achado |
| pip-audit | SCA (deps) | dependências de runtime resolvidas do `uv.lock` | **0 vulnerabilidades** (3 CVEs de nicegui dev-only aceitos, #112) |
| trivy | SCA (imagem) | imagem de runtime `pytstop` (Python 3.14) | **0 HIGH/CRITICAL** no gate (`ignore-unfixed` + `.trivyignore`) |
| gitleaks | Segredos | árvore de trabalho (`gitleaks dir`) com allowlist | **0 leaks** |
| CodeQL | SAST semântico | python + javascript-typescript (default setup) | **`Analyze` verde** — sem alertas de segurança ativos |
| OWASP ZAP | DAST baseline | API viva via OpenAPI (stack compose) | **0 FAIL** — 2 WARN aceitos como IGNORE ([`.zap/rules.tsv`](../../.zap/rules.tsv)) |
| SonarQube (Community, local) | Análise estática + hotspots | `src/` (7,4k LoC, cobertura importada) | **Quality Gate Passed** — 0 security, 0 reliability, coverage 95,3%; **hotspots 3 → 0** (1 FIXED, 2 SAFE) |

Referência da última execução verde: check-runs do commit [`5404826`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/commit/5404826) — `security`, `pip-audit (CVE em dependências)`, `gitleaks (segredos)`, `trivy (CVE na imagem)`, `Analyze (python)`, `Analyze (javascript-typescript)` e o `full-test-ci` (que hospeda o DAST) todos `success`.

## Análise Estática (bandit)

Gate do projeto (`make security`, espelhado no CI): `bandit -r src/ ui/ relay/ scripts/ ... -c pyproject.toml --severity-level high` — **nenhum achado high**. A varredura completa de **`src/` + `relay/`** sem filtro de severidade (10.112 LoC) fecha em **0 high / 0 medium / 0 low**: nenhum resultado. O `relay/`, introduzido depois da bateria de 12/06, entra limpo.

A UI (`ui/`, dev-only, fora do runtime de produção e não empacotada pelo `pyproject.toml`) mantém o único achado **low** já aceito na versão 1.0:

| Arquivo | ID | Severidade | Análise |
|---|---|---|---|
| `ui/config.py:52` | B105 (hardcoded password) | Low | Fallback dev-only do `storage_secret` da UI NiceGUI, usado somente quando `UI_STORAGE_SECRET` não está definido. Valor auto-documentado (`pytstop-ui-dev-only-...`). Aceito. |

Reprodução:

```bash
make security
```

## Auditoria de Dependências (pip-audit)

O gate de CI ([`security.yml`](../../.github/workflows/security.yml)) audita apenas as dependências de **runtime** — `uv export --no-dev --no-emit-project` gera `requirements-prod.txt`, que exclui o tooling de teste e a UI NiceGUI (dev-only) — porque essa é a superfície de ataque de produção:

```bash
uv export --frozen --no-emit-project --no-dev --no-hashes --format requirements-txt -o requirements-prod.txt
uvx pip-audit -r requirements-prod.txt --strict
```

**Resultado na HEAD final**: `No known vulnerabilities found`. Os únicos advisories excluídos são os **3 HIGH de `nicegui`** ([CVE-2025-66645, CVE-2026-21873, CVE-2026-25732](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/112)) — a UI é dev-only e não consta no lockfile de produção; ficam como `--ignore-vuln` explícito (cinto-e-suspensório, [#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/112)).

Este resultado limpo é o **estado consolidado** de duas ondas de upgrade posteriores à v1.0:

| Onda | PR | O que mudou |
|---|---|---|
| Gate de CI + 5 CVEs reais | [#116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116) | A automação do pip-audit no CI (#75) pegou **5 CVEs reais** e forçou o upgrade — **cryptography 46→49**, **starlette 1.0→1.3.1**, **fastapi→0.138.2** — além dos bumps de pyjwt/urllib3/idna/mako já feitos na v1.0 |
| Migração consolidada de deps | [#143](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/143) | Leva do Dependabot consolidada (redis 8, entre outros), com Dependabot mensal ativo |
| NiceGUI 3 | [#149](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/149) | Upgrade `nicegui 2.24 → 3.14` — removeu a transitiva `vbuild` (que usava `pkgutil.find_loader`, extinto no Python 3.14), destravando a migração 3.14 |
| Pisos de deps + Terraform action | [#151](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/151) | Alinha pisos de `pwdlib`/`testcontainers`; `setup-terraform@v4` |

Versões-chave resolvidas no `uv.lock` da HEAD final: `pyjwt 2.13.0`, `starlette 1.3.1`, `cryptography 49.0.0`, `fastapi 0.139.0`, `urllib3 2.7.0`, `idna 3.18`, `mako 1.3.12`, `redis 8.0.1`. A suíte completa (1.617 testes unitários + 163 de integração, contagem via `pytest --collect-only`) segue verde após os bumps, validando ausência de regressão.

## Scan de Imagem (trivy)

Reexecutado nesta bateria (a v1.0 havia pulado o trivy): a imagem de runtime agora é **Python 3.14** ([#150](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/150) — builder `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` + runtime `python:3.14-slim`). O gate ([`security.yml`](../../.github/workflows/security.yml)) constrói a imagem e reprova em HIGH/CRITICAL:

```bash
docker build -t pytstop:ci-scan .
trivy image --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore --exit-code 1 pytstop:ci-scan
```

**Resultado na HEAD final**: **0 HIGH/CRITICAL** no gate. Os CVEs de pacotes de SO da imagem base sem fix upstream (`ncurses`, `systemd`) são descartados por `ignore-unfixed` e listados explicitamente em [`.trivyignore`](../../.trivyignore) (CVE-2025-69720, CVE-2026-29111) — não usados pelo runtime FastAPI/uvicorn (entrypoint é `uvicorn` direto, sem systemd), aceite herdado de [#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/113).

## Detecção de Segredos (gitleaks)

O gate ([`security.yml`](../../.github/workflows/security.yml)) varre a **árvore atual** (não o histórico) com a config do repo — barra segredos novos entrando por PR sem re-flagar dev-secrets antigos já cobertos pela allowlist:

```bash
gitleaks dir . --config .gitleaks.toml --redact --no-banner --verbose
```

**Resultado na HEAD final**: **0 leaks**. A [`.gitleaks.toml`](../../.gitleaks.toml) mantém a allowlist documentada dos falsos positivos e valores de demo deliberados da fase 1 (digests do relatório trivy, estado local do Terraform gitignored, token de demo do webhook de orçamento — todos auto-documentados como `...-nao-usar-em-producao`).

## SAST Semântico (CodeQL)

O CodeQL roda pelo **default setup** do GitHub code scanning (decisão de [#116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116)/[TD-010](../tech-debt/README.md): sem workflow `codeql.yml` avançado, que conflita com o default setup). Os jobs `Analyze (python)` e `Analyze (javascript-typescript)` estão **verdes na HEAD final**, sem alertas de segurança ativos. Paridade local via `make codeql-quality`, que aplica as supressões de falso positivo que o default setup não permite.

> A API REST de code scanning responde `403 "Advanced Security must be enabled"` para este repositório privado — mensagem enganosa: o default setup **está ativo** e os jobs `Analyze` rodam e reprovam normalmente no CI (é a razão de não se criar um `codeql.yml` avançado). A evidência do resultado são os check-runs verdes, não a API de alerts.

## DAST (OWASP ZAP baseline)

O ZAP baseline (scan passivo) roda continuamente no [`full-test-ci`](../../.github/workflows/full-test-ci.yml) contra o OpenAPI vivo da stack compose ([TD-011](../tech-debt/README.md), [PR #65](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/65)), com gate por [`.zap/rules.tsv`](../../.zap/rules.tsv): sem `-I`, qualquer alerta que não esteja como `IGNORE` reprova a build. As duas únicas regras em IGNORE são os 2 WARN aceitos e justificados na fase 1 (falsos positivos esperados para API REST):

| Plugin | Regra | Tratamento |
|---|---|---|
| 10049 | Non-Storable Content | IGNORE — correto para uma API com `Cache-Control: no-store` |
| 90004 | Cross-Origin-Resource-Policy Header | IGNORE — superfície interna do cluster de demo |

**Resultado na HEAD final**: **0 FAIL** — nenhum achado novo além dos 2 WARN aceitos; o `full-test-ci` fechou verde no commit [`5404826`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/commit/5404826). Baseline de referência da fase 1: 65 PASS / 0 FAIL / 2 WARN (49 URLs via OpenAPI). Paridade local via `make dast`.

## SonarQube (scan manual de fechamento)

O SonarQube **não é gate de CI** por decisão registrada (TD-010, [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)): repo privado torna o SonarCloud pago e um servidor self-hosted é desproporcional ao MVP. Ele roda como **scan manual de fechamento de fase** — SonarQube Community local (docker) + `sonar-scanner` com o [`sonar-project.properties`](../../sonar-project.properties) versionado e o `coverage.xml` da suíte unitária importado.

**Execução de fechamento da fase 2 (02/07/2026)** — Quality Gate **Passed**: Security **0** (rating A), Reliability **0** (A), Maintainability 147 code smells (A, informativo), Coverage **95,3%**, Duplications **0,0%**. A primeira análise apontou **3 security hotspots** ("to review" — pontos de atenção, não vulnerabilidades confirmadas), todos tratados no fluxo de revisão da própria ferramenta:

| Hotspot | Regra | Tratamento |
|---|---|---|
| Regex de extração de e-mail com backtracking polinomial (`notificacoes.py`) | S5852 (DoS) | **Corrigido no código**: domínio casado label a label (`.` fora da classe de caracteres) elimina o backtracking; input já limitado a 255 chars pelo VO `Contato`. Teste adversarial em `TestExtrairEmail`. Revisado como **FIXED** |
| `http://jaeger:4317` como endpoint OTLP default (`observability.py`, 2 ocorrências) | S5332 (encrypt-data) | **Revisado como SAFE**: tráfego OTLP gRPC intra-cluster (o DNS `jaeger` só resolve dentro do cluster/compose); um collector externo entra via `OTEL_EXPORTER_OTLP_ENDPOINT` com `https`, que desliga o modo insecure automaticamente |

**Resultado final: 0 hotspots a revisar**, Quality Gate mantido **Passed**. O universo de cobertura foi alinhado ao gate do `.coveragerc` (`sonar.coverage.exclusions=**/__init__.py` — arquivos omitidos do gate não entram no denominador): a primeira leitura reportava 93,6% por medir um conjunto maior de arquivos do que o gate de 95% mede; alinhado, a cobertura real é **95,3%** (o gate de CI mede 97,5% incluindo `ui/`). O antes/depois está nas evidências visuais do Anexo B do documento de entrega ([`b6-sonarqube-quality-gate.png`](../entrega/fase2/evidencias/b6-sonarqube-quality-gate.png) → [`b6b-sonarqube-hotspots-zerados.png`](../entrega/fase2/evidencias/b6b-sonarqube-hotspots-zerados.png)).

## Itens de Segurança Endereçados na Fase 2

Além dos scans limpos, a fase 2 fechou um conjunto de correções de segurança/correção — os bugs confirmados da [auditoria de finalização](../entrega/fase2/finalization-plan.md) ([issue #128](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/128)) viraram issues no GitHub e foram corrigidos com teste TDD (red→green):

| Item | PR (issue) | Correção |
|---|---|---|
| Revogação de refresh token (CWE-613) | [#142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) ([#118](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/118), [#121](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/121)) | Logout passa a revogar o **refresh** (best-effort, escopado ao dono) e vira idempotente (guard antes do INSERT — logout duplo não estoura o UNIQUE do JTI) |
| TOCTOU na recusa externa de orçamento | [#142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) ([#119](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/119)) | A recusa externa revalida o estado de espera **sob lock** antes de delegar o cancelamento — fecha a janela que cancelava OS já em execução |
| Item de estoque desativado em OS | [#142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) ([#120](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/120)) | Peça desativada não entra em OS nova nem é reservada (`ItemEstoqueDTO.ativo` + rejeição em `_montar_item` + defesa em `ItemEstoque.reservar`) |
| Instância stale sob `FOR UPDATE` | [#142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) ([#117](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/117)) | `populate_existing=True` no ramo `com_lock` + listeners de `refresh` no mapping — sem isso o SELECT FOR UPDATE devolvia a instância stale do identity map, derrotando a defesa de concorrência |
| Seed com senha de demo pública | [#152](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/152) ([#95](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/95)) | `seed_admin.py` rejeita o `ADMIN_PASSWORD` de demo commitado (`pytstop-admin-demo-2026`); teste-guarda falha se removerem o valor da denylist |
| Papel de usuário fail-closed | [#152](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/152) ([#96](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/96)) | Removido `default="admin"` da coluna `papel` no mapping de auth — inserção sem papel vira `NOT NULL` (fail-closed) em vez de `admin` silencioso, completando o fail-safe do [#84](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/84) |
| Webhook de orçamento assinado | [#114](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/114) | Aprovação/recusa externa passa a exigir assinatura HMAC (`X-Webhook-Signature` + `X-Webhook-Timestamp`) — [ADR-021](../arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md), TD-027 |
| Rate limiter global sob HPA | [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62), [#67](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/67) | Storage compartilhado (Redis) via `storage_uri` — limite por IP correto e global entre réplicas, com degradação graciosa se o Redis cair ([ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md)); IP real atrás de proxy via `ProxyHeadersMiddleware` quando `TRUSTED_PROXIES` está setado |

Complementam os controles já entregues antes desta bateria: `ENCRYPTION_KEY` obrigatória em produção + decrypt sem fail-open ([#103](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/103)), erasure LGPD admin-only com trilha de auditoria ([#104](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/104)), pré-hash bcrypt de 72 bytes + refresh não vale como access ([#105](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/105)), `securityContext` nos workloads k8s ([#108](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/108)) e scrub de PII em tracebacks/logs ([#86](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/86)).

## Relação com Outros Documentos

- [Relatório de vulnerabilidades (fase 1)](relatorio-vulnerabilidades.md) — baseline OWASP API Top 10, trivy, ZAP e SonarQube
- [Plano de segurança](plano-seguranca.md) — modelo de ameaças e controles
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) — pipeline de segurança em camadas
- [Dívida técnica](../tech-debt/README.md) — débitos de segurança aceitos e rastreados

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)
