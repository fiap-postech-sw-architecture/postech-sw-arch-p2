# Apêndice A — Funcionalidades Extras da Fase 2

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega Fase 2](README.md)

> Documento complementar ao [Documento de Entrega — Fase 2](entrega-fase-2.md). Cataloga as funcionalidades implementadas **além** dos entregáveis obrigatórios do enunciado da Fase 2, cada uma ancorada em evidência verificável (ADR, PR, commit ou arquivo). É o análogo, para a Fase 2, do [Apêndice da Fase 1](../apendice-funcionalidades-extras.md).

## O que é este apêndice

O enunciado da Fase 2 ([desafio-tech-fase-2.md](../../requisitos/fase2/desafio-tech-fase-2.md)) exige um conjunto fechado de itens: refatoração para Clean Architecture, cinco APIs de OS, containerização (Dockerfile + docker-compose), manifests Kubernetes (Deployment, Service, ConfigMap, Secret, HPA), Terraform para cluster e banco, pipeline de CI/CD e README com desenho da arquitetura, instruções e link do vídeo. A rastreabilidade desses itens obrigatórios está na [seção 5 do documento de entrega](entrega-fase-2.md#5-rastreabilidade-requisito--evidência) (RF-020–024, RNF-017–024, RN-018–020).

Este apêndice reúne o que o grupo entregou **fora** desse escopo — decisões de robustez, observabilidade, segurança e infraestrutura que não eram cobradas mas evidenciam profundidade de engenharia. O critério de "extra" é objetivo: qualquer item que o enunciado não pede explicitamente. Boa parte nasceu do ledger de dívida técnica versionado ([`docs/tech-debt/README.md`](../../tech-debt/README.md), 26 itens resolvidos) e da auditoria pré-entrega ([auditoria-pre-entrega-fase2.md](../../tech-debt/auditoria-pre-entrega-fase2.md)), atacados em tiers priorizados após a base obrigatória já estar verde. Nenhum era exigido pela fase.

## Critério e organização

Cada extra abaixo traz **motivação** (por que foi feito, já que não era obrigatório) e **evidência** (ADR/PR/commit/arquivo que comprova a implementação no repositório). Os extras estão agrupados por tema. A numeração de PR refere-se aos PRs do repositório da Fase 2 na org `fiap-postech-sw-architecture`.

---

## A.1 Entrega durável de eventos e resiliência (4 extras)

### 1. Transactional Outbox + processo relay

- **Motivação**: o enunciado pede notificação de status "via alguma ferramenta como email" (RF-024). A entrega ingênua — enviar o e-mail dentro da transação de negócio — cria dual-write: a transição da OS pode commitar e o e-mail falhar (ou vice-versa). O grupo adotou o padrão Transactional Outbox para garantir entrega *at-least-once* sem acoplar o envio à transação.
- **Evidência**: [ADR-022](../../arquitetura/adr/fase2/022-transactional-outbox-relay.md). A UnitOfWork grava o `IntegrationEvent` na tabela `outbox` na mesma transação da OS (migração [`003_outbox.py`](../../../migrations/versions/003_outbox.py)); o relay (`python -m relay`) faz *claim-then-deliver* com `FOR UPDATE SKIP LOCKED`, head-of-line, backoff/DLQ e idempotência via `processed_events`, com notificação proativa por `LISTEN/NOTIFY`. Código em [`relay/processador.py`](../../../relay/processador.py) e [`relay/listener.py`](../../../relay/listener.py). O dispatcher síncrono foi congelado vazio (`EventDispatcher(handlers=())`), eliminando o dual-write. TD-008 (PR #56, commit `30c94ec`).

### 2. Fencing de lease no relay (segurança para `replicas>1`)

- **Motivação**: com o relay escalado para mais de uma réplica, duas réplicas poderiam reivindicar a mesma linha da outbox e entregar o e-mail em duplicidade. O fencing torna a escala horizontal do relay segura.
- **Evidência**: TD-021, [ADR-022](../../arquitetura/adr/fase2/022-transactional-outbox-relay.md). Re-lock `FOR UPDATE SKIP LOCKED` + checagem de status `pendente` na transação por-linha (`bloquear_para_entrega` em [`relay/processador.py`](../../../relay/processador.py)), serializando réplicas concorrentes sem duplicar entrega e sem mudança de schema. PR #66 (commit `3ab383d`).

### 3. Resiliência do ciclo do relay (blip de DB não reinicia o pod)

- **Motivação**: um erro transitório de banco no meio do loop de drenagem não deveria derrubar o pod nem perder eventos — as garantias *at-least-once* + lease já cobrem a retentativa.
- **Evidência**: o `while` de `executar_relay` embrulha heartbeat + drenagem num `try/except Exception` que loga `outbox_ciclo_falhou` e faz `continue`; o drain inicial pré-loop fica fora (erro no boot deve falhar alto), e `except Exception` (não `BaseException`) deixa `KeyboardInterrupt`/`SystemExit` propagarem. Código em [`relay/listener.py`](../../../relay/listener.py). Hardening operacional do TD-008 (2026-06-25).

### 4. Correção de swallow de exceção no envio de e-mail (retry/DLQ alcançáveis)

- **Motivação**: o handler de notificação engolia toda exceção do envio (contrato da fase síncrona antiga), o que fazia o relay marcar o e-mail como `entregue` mesmo com o SMTP fora — tornando retry/backoff/DLQ inalcançáveis. Bug real corrigido durante o hardening.
- **Evidência**: `NotificarMudancaDeStatus.__call__` ([`src/ordem_servico/aplicacao/notificacoes.py`](../../../src/ordem_servico/aplicacao/notificacoes.py)) passou a capturar só transporte (`except (OSError, smtplib.SMTPException)`), logar e re-raise; os early-returns de skip seguem não-fatais. Fechado por teste de integração com testcontainers (`tests/integracao/relay/test_relay_smtp_falha.py`) que prova que a falha de SMTP leva a linha a `dead`, não `entregue`.

## A.2 Observabilidade (3 extras)

### 5. Tracing distribuído com OpenTelemetry + Jaeger

- **Motivação**: o enunciado não pede observabilidade. Com o sistema indo para Kubernetes sob HPA, traces de request e de banco são essenciais para diagnosticar latência entre réplicas.
- **Evidência**: [ADR-020](../../arquitetura/adr/fase2/020-observabilidade-opentelemetry.md). `configurar_otel(app, engine)` em [`src/compartilhado/infraestrutura/observability.py`](../../../src/compartilhado/infraestrutura/observability.py) instrumenta FastAPI + SQLAlchemy, exportando via OTLP/gRPC; default OFF por `OTEL_ENABLED` (desligado = zero import de otel). Jaeger all-in-one como workload de demo em [`k8s/jaeger.yaml`](../../../k8s/jaeger.yaml). PR #22.

### 6. Métricas do relay em Prometheus (via OTel `MeterProvider`)

- **Motivação**: a outbox é um ponto operacional crítico — sem métricas de profundidade e idade do pendente mais antigo, uma DLQ crescente passa despercebida.
- **Evidência**: TD-022, [ADR-024](../../arquitetura/adr/fase2/024-metricas-prometheus.md). `MeterProvider` + `PrometheusMetricReader` em [`relay/metrics.py`](../../../relay/metrics.py) servem `/metrics` (porta 9100): gauges de profundidade (pendentes/idade/dead) + contadores entregue/falha/dead/retry, scrapeados por [`k8s/prometheus.yaml`](../../../k8s/prometheus.yaml). Opt-in por env. PR #66 (commit `3ab383d`).

### 7. Redação de PII nos traces (query string com CPF/placa)

- **Motivação**: sem tratamento, os spans capturam a query string — que pode conter CPF/placa —, vazando PII para o backend de tracing. Defesa em profundidade LGPD.
- **Evidência**: TD-017. `_redigir_pii_da_span` (server_request_hook do `FastAPIInstrumentor`) redige `url.query` e remove a query de `http.target`/`url.path` antes do export ([`src/compartilhado/infraestrutura/observability.py`](../../../src/compartilhado/infraestrutura/observability.py)). Fechado na issue #34.

## A.3 Segurança de infraestrutura e supply chain (5 extras)

### 8. `securityContext` endurecido nos workloads próprios

- **Motivação**: o enunciado pede os manifests, mas não hardening. Rodar como root, com filesystem gravável e capabilities amplas é risco desnecessário no cluster.
- **Evidência**: TD-024. Pod + container `securityContext` (`runAsNonRoot`, `runAsUser/runAsGroup/fsGroup 1001`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem`, `capabilities.drop: [ALL]`) + `emptyDir` em `/tmp` nos 3 workloads próprios (api/relay/migrate); UID/GID 1001 pinados no [`Dockerfile`](../../../Dockerfile):52. Manifests em [`k8s/deployment.yaml`](../../../k8s/deployment.yaml) e [`k8s/relay.yaml`](../../../k8s/relay.yaml):35. Teste de mesa no kind confirmou pods `Running` sob o hardening. PR #108 (commit `04c2a42`).

### 9. Webhook de decisão de orçamento assinado por HMAC

- **Motivação**: o endpoint externo de aprovação/recusa (RF-022) inicialmente usava um token estático no corpo. Sem assinatura, um payload adulterado seria aceito. A assinatura HMAC fecha adulteração e limita replay.
- **Evidência**: TD-027, [ADR-021](../../arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md) (emendada). [`src/compartilhado/infraestrutura/webhook_signature.py`](../../../src/compartilhado/infraestrutura/webhook_signature.py) — HMAC-SHA256 de `{ordem_id}.{timestamp}.` + body, chave `ORCAMENTO_WEBHOOK_TOKEN` (não trafega), janela ±5 min via headers `X-Webhook-Signature`/`X-Webhook-Timestamp`. PR #114 (commit `30fe5fe`).

### 10. Gates reais de segurança no CI (pip-audit, gitleaks, trivy)

- **Motivação**: os docs de segurança citavam scanners que nenhum workflow rodava. Automatizá-los transforma intenção em gate — e já capturou CVEs reais.
- **Evidência**: [`.github/workflows/security.yml`](../../../.github/workflows/security.yml) roda **pip-audit** (pegou e corrigiu 5 CVEs reais em cryptography/starlette/fastapi), **gitleaks** (segredos) e **trivy** (CVE na imagem); escopo do **bandit** ampliado para `src ui relay scripts`; **CodeQL** confirmado no default setup + `make codeql-quality` local aplicando supressões de FP; **Dependabot** configurado. PR #116 (commit `931d6aa`).

### 11. DAST automatizado (OWASP ZAP baseline) no CI

- **Motivação**: análise estática não cobre vulnerabilidades de runtime. O baseline dinâmico contra a stack real complementa bandit/CodeQL.
- **Evidência**: TD-011, [ADR-011](../../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md). ZAP baseline no [`full-test-ci`](../../../.github/workflows/full-test-ci.yml) (DAST contra a stack compose), relatório como artefato + alvo `make dast` para paridade local; regras dos WARNs aceitos em [`.zap/rules.tsv`](../../../.zap/rules.tsv). PR #65 (commit `7b0b686`).

### 12. SBOM automatizado (CycloneDX) no CI

- **Motivação**: rastreabilidade de supply chain — saber exatamente quais dependências (e versões) entram na imagem, com política de licenças permissivas.
- **Evidência**: TD-012, [ADR-012](../../arquitetura/adr/012-licenciamento-software-sbom.md). Job `sbom` no [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) gera o SBOM CycloneDX a partir do lockfile a cada run e publica como artefato; alvo `make sbom` para geração local.

## A.4 Hardening de autenticação (4 extras)

### 13. Papel obrigatório no registro + coluna sem default (fail-closed)

- **Motivação**: `POST /autenticacao/registrar` criava **sempre** ADMIN (default `papel=Papel.ADMIN` e ausência do campo no request), anulando o RBAC. Correção de design fail-safe.
- **Evidência**: `papel` passou a ser obrigatório em `RegistrarRequest`/`RegistrarDTO`; omitir → 422 (nunca ADMIN silencioso). Depois, o `default="admin"` da coluna `usuarios.papel` foi removido do mapping ([`src/autenticacao/infraestrutura/mapping.py`](../../../src/autenticacao/infraestrutura/mapping.py)), tornando a inserção sem papel um fail-CLOSED (NOT NULL) em vez de fail-OPEN. PR #84 (commit `c27da5b`) + housekeeping #96 (commit `5404826`).

### 14. Refresh token não vale como access + pré-hash bcrypt 72 bytes

- **Motivação**: dois gaps da auditoria — o claim `type` do JWT não era checado (um refresh token era aceito como access, CWE) e o bcrypt trunca senhas em 72 bytes (colisão de prefixo).
- **Evidência**: TD-028/TD-029. `obter_usuario_atual` ([`src/autenticacao/interfaces/middleware.py`](../../../src/autenticacao/interfaces/middleware.py)) exige `type == "access"` → 401 caso contrário; `hash_senha` pré-hasha `base64(sha256(senha))` antes do bcrypt ([`src/autenticacao/infraestrutura/password_hasher.py`](../../../src/autenticacao/infraestrutura/password_hasher.py), padrão `bcrypt_sha256`). PR #105 (commit `3bc6c4d`).

### 15. Logout revoga também o refresh token (fecha CWE-613)

- **Motivação**: o logout só revogava o `jti` do access; o refresh sobrevivia, permitindo reemitir um access após o logout.
- **Evidência**: bug da auditoria (issue #118/#121). O logout passou a aceitar o refresh opcional no corpo (`Body(None, embed=True)`, sem quebrar clientes só-header) e revogar ambos os `jti`, best-effort e escopado ao dono; `revogar` ficou idempotente. Corrigido em `c33de8a` (PR #142).

### 16. Seed de admin rejeita a senha demo pública

- **Motivação**: o `ADMIN_PASSWORD` de demonstração (`pytstop-admin-demo-2026`) é commitado em `k8s/secret.yaml` e no docker-compose. Sem guarda, um deploy poderia subir produção com essa senha pública.
- **Evidência**: [`scripts/seed_admin.py`](../../../scripts/seed_admin.py) rejeita o valor demo via frozenset, com teste de regressão em `tests/unitarios/scripts/test_seed_admin.py`. Issue #95, housekeeping da entrega (commit `5404826`).

## A.5 Segurança de dados e LGPD (2 extras)

### 17. Erasure LGPD em cascata para veículos

- **Motivação**: a anonimização do cliente (direito ao esquecimento) deixava a placa do veículo — também PII — intacta e vinculável. A cascata fecha o vazamento residual.
- **Evidência**: issue #72. Migração [`006_widen_veiculos_placa.py`](../../../migrations/versions/006_widen_veiculos_placa.py) alarga a coluna `placa` para acomodar o sentinela `PlacaAnonimizada`; o erasure cascateia para os veículos vinculados. Também tornado admin-only com trilha de auditoria (#76, commit `064ef1f`). PR #112 (commit `ea40b2b`).

### 18. Scrub de PII em tracebacks e logs da stdlib

- **Motivação**: mesmo com cifragem em repouso, um traceback ou um access log do uvicorn (com `?documento=CPF` na query) vazaria PII em texto plano.
- **Evidência**: issue #86. Em [`src/compartilhado/infraestrutura/logging.py`](../../../src/compartilhado/infraestrutura/logging.py): `format_exc_info` reordenado para preceder `scrub_pii` (o traceback vira string mascarada); `ProcessorFormatter` instalado no root logger religando os loggers do uvicorn ao scrubber; scrubber ampliado com padrão de telefone BR e denylist de chaves sensíveis (password/token/secret/…). PR #86 (commit `04217f3`).

## A.6 Persistência, domínio e concorrência (4 extras)

### 19. Lock pessimista nas transições da OS + ordem global de locks

- **Motivação**: transições de OS concorrentes sem controle de concorrência podiam emitir N eventos/e-mails e a reserva de estoque sofria lost-update (sobre-venda). Correção de concorrência real.
- **Evidência**: issues #82/#83. `obter_por_id(*, com_lock=True)` com `SELECT ... FOR UPDATE` nas 11 transições de mutação da OS ([`src/ordem_servico/infraestrutura/repository.py`](../../../src/ordem_servico/infraestrutura/repository.py)); ordem global OS→Estoque + locks multi-item em ordem de `item_estoque_id` previnem deadlock. Reforçado com `populate_existing=True` (evita instância stale do identity map, #117). Testes de concorrência com Postgres real em `tests/integracao/ordem_servico/test_concorrencia_lock.py`. PR #101 (commit `7b58156`) + `c33de8a`.

### 20. Snapshot do escopo aprovado do orçamento (JSONB) — cobrança correta do complementar

- **Motivação**: `gerar_orcamento_complementar` sobrescrevia o orçamento e a rejeição não revertia nada — a OS acabava cobrando trabalho recusado e mantinha reservas de estoque nunca liberadas.
- **Evidência**: issues #111/#122. Snapshot do escopo aprovado (orçamento + ids dos itens cobertos) congelado nas aprovações e persistido na coluna JSONB `escopo_aprovado_json` (migração [`007_escopo_aprovado_os.py`](../../../migrations/versions/007_escopo_aprovado_os.py), reversível); a rejeição do complementar restaura o orçamento aprovado, remove itens fora do escopo e libera as reservas na mesma UoW; `finalizar_servico` recusa itens fora do escopo. Commit `e794bfc`.

### 21. `orcamento_json` migrado de `Text` para `jsonb` nativo

- **Motivação**: o orçamento vivia numa coluna `Text` com serialização manual `json.dumps`/`json.loads` no mapping — frágil e fora do padrão da `outbox.payload`.
- **Evidência**: TD-005. Migração [`004_orcamento_jsonb.py`](../../../migrations/versions/004_orcamento_jsonb.py) troca para `jsonb`, removendo a camada manual no [`src/ordem_servico/infraestrutura/mapping.py`](../../../src/ordem_servico/infraestrutura/mapping.py) (`JSONB().with_variant(JSON(), "sqlite")`). PR #68 (commit `c363369`).

### 22. Value Object `Contato` (substitui primitivo `str`)

- **Motivação**: o contato do cliente era um primitivo `str` sem validação nem representação PII-safe — débito tático de DDD herdado da fase 1.
- **Evidência**: TD-007. [`src/cliente_veiculo/dominio/contato.py`](../../../src/cliente_veiculo/dominio/contato.py) — texto livre validado (não-vazio, `<=255`, `strip`, `__repr__` PII-safe), persistido na mesma coluna via shadow + event listeners (padrão CPF/Placa, sem migração). PR #70 (commit `efd5431`).

## A.7 Infraestrutura, escala e DX (4 extras)

### 23. Rate limiter com storage compartilhado (Redis) sob HPA

- **Motivação**: o rate limiter in-memory por pod diverge entre réplicas — sob HPA, cada réplica conta separadamente e o limite global fica incorreto.
- **Evidência**: TD-016, [ADR-023](../../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md). slowapi com `storage_uri` apontando para Redis (env `RATE_LIMIT_STORAGE_URI`), Deployment+Service em [`k8s/redis.yaml`](../../../k8s/redis.yaml), com degradação graciosa para per-réplica se o Redis cair. PR #62 (commit `70b70e3`).

### 24. Rate-limit pelo IP real do cliente atrás de proxy confiável

- **Motivação**: atrás de ingress, o rate-limit por IP do peer imediato colapsa todo o tráfego externo num único bucket. É preciso ler o `X-Forwarded-For` confiável.
- **Evidência**: TD-023, [ADR-023](../../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md). `ProxyHeadersMiddleware` do uvicorn aplicado quando `TRUSTED_PROXIES` está configurado ([`src/compartilhado/interfaces/middleware.py`](../../../src/compartilhado/interfaces/middleware.py)), reescrevendo `request.client` a partir do XFF; default vazio (não confia em XFF, sem spoof). PR #67 (commit `7bb9837`).

### 25. Migração em Job dedicado antes do rollout (fim da corrida multi-réplica)

- **Motivação**: rodar o Alembic no entrypoint do pod cria corrida com N réplicas subindo em paralelo. Um Job dedicado, aplicado antes do rollout, serializa a migração.
- **Evidência**: TD-015, [ADR-019](../../arquitetura/adr/fase2/019-pipeline-cicd-deploy.md). [`k8s/jobs/migration-job.yaml`](../../../k8s/jobs/migration-job.yaml) (`pytstop-migrate`) aplicado com `kubectl wait --for=condition=complete`; `RUN_MIGRATIONS_ON_STARTUP`/`RUN_SEED_ON_STARTUP` passam a `false` no cluster. PR #64 (commit `02900d4`).

### 26. Índice B-tree em `itens_da_ordem.item_estoque_id`

- **Motivação**: a checagem `existe_ativa_com_item_estoque` fazia full scan sem índice de suporte — degrada com o volume de itens.
- **Evidência**: TD-025. Migração [`005_indice_item_estoque.py`](../../../migrations/versions/005_indice_item_estoque.py) (reversível) cria `ix_itens_da_ordem_item_estoque_id`; a declaração `Index` no mapping mantém o `create_all` em sync. `EXPLAIN` confirma `Index Scan`. PR #107 (commit `dbc17db`).

## A.8 Arquitetura, qualidade e plataforma (3 extras)

### 27. Contrato de camadas verificado por import-linter (Clean Architecture executável)

- **Motivação**: o enunciado pede Clean Architecture, mas não sua verificação automática. Sem gate, a separação de camadas degrada silenciosamente.
- **Evidência**: TD-019 (RNF-017), [ADR-015](../../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md). Contratos em `[tool.importlinter]` ([`pyproject.toml`](../../../pyproject.toml)) verificados por `make lint-arch` na CI; o contrato `forbidden` passou a proibir `aplicacao → infraestrutura` em **todos** os contextos após a extração de `PasswordHasherPort`/`JWTServicePort` na autenticação. PR #50 (commit incluído no histórico de fechamento).

### 28. Cobertura ≥95% com gate explícito no CI

- **Motivação**: o enunciado pede apenas testes dos fluxos críticos. O grupo manteve gate de cobertura muito acima do mínimo (a fase 1 exigia 80%), tornando-o explícito no pipeline.
- **Evidência**: TD-031. `--cov-fail-under=95` explícito no step de cobertura de `src/` no [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml), alinhado ao `.coveragerc`; cobertura de ~95,3% confirmada na CI da main. PR #106 (commit `1023e45`).

### 29. Migração para Python 3.14 (runtime, tooling e imagens alinhados)

- **Motivação**: manter o runtime atualizado (o desbloqueio veio com o NiceGUI 3, que removeu a dependência `vbuild`). Não exigido pela fase.
- **Evidência**: `.python-version`=3.14 + `Dockerfile` builder `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` e runtime `python:3.14-slim` (mesma minor, senão o venv copiado quebra) + `ui/Dockerfile` + os 7 pins `python-version: "3.14"` nos workflows. Todas as deps com wheel `cp314`; teste de mesa no app 3.14.6 vivo. PR #150 (commit `f86826f`).

## Total

**29 funcionalidades extras**, todas verificadas contra o repositório, distribuídas em:

| Tema | Extras |
|---|---|
| Entrega durável de eventos e resiliência | 4 (itens 1–4) |
| Observabilidade | 3 (itens 5–7) |
| Segurança de infraestrutura e supply chain | 5 (itens 8–12) |
| Hardening de autenticação | 4 (itens 13–16) |
| Segurança de dados e LGPD | 2 (itens 17–18) |
| Persistência, domínio e concorrência | 4 (itens 19–22) |
| Infraestrutura, escala e DX | 4 (itens 23–26) |
| Arquitetura, qualidade e plataforma | 3 (itens 27–29) |

Nenhum desses itens era exigido pela Fase 2. São iniciativa de qualidade do grupo, materializando a Boy Scout Rule registrada no [ledger de dívida técnica](../../tech-debt/README.md): cada evolução deixa o código e a documentação melhores do que os encontrou. O conjunto completo dos 26 itens de dívida técnica resolvidos está no [ledger](../../tech-debt/README.md#itens-resolvidos-26); os itens de maior valor também aparecem na [seção 5 do documento de entrega](entrega-fase-2.md#qualidade-além-do-escopo--dívida-técnica-endereçada).

---

> [↑ Raiz do projeto](../../../README.md) · [↑ Entrega Fase 2](README.md)
