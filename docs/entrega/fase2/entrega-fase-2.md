# Documento de Entrega — Tech Challenge Fase 2

> [↑ Raiz do projeto](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2) · [↑ Entrega Fase 2](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/docs/entrega/fase2)

> **Versão**: 1.4 — Julho/2026.

Documento de entrega da Fase 2 do Tech Challenge da Pós-Graduação em Arquitetura de Software (FIAP). O conteúdo cobre os itens exigidos pelo enunciado da fase: identificação do grupo, link do repositório (compartilhado com o avaliador), desenho da arquitetura, instruções de execução e deploy, link da collection das APIs e link do vídeo de demonstração.

## Como ler este documento

O repositório é a fonte de verdade da entrega. Os artefatos exigidos pela fase — código refatorado com Clean Architecture, Dockerfile e docker-compose revisados, manifests Kubernetes em `/k8s`, scripts Terraform em `/infra`, pipeline de CI/CD e README atualizado — estão versionados no próprio projeto. Os links abaixo apontam diretamente para esses arquivos no GitHub (branch `main`), navegáveis pela UI nativa do GitHub com o avaliador adicionado como colaborador. O desenho da arquitetura é modelado em Mermaid, renderizado nativamente pelo GitHub; a fonte única do diagrama é a [RFC-002 §3](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md), e ele é replicado no [README](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/README.md) e na seção 7 deste documento.

A opção por documentação textual e versionada segue a fase 1: o projeto é AI-first, e Markdown + Mermaid permitem manutenção por agentes de IA sem prejuízo da leitura humana. As decisões da fase estão registradas em ADRs (015–024) e consolidadas na RFC-002; a rastreabilidade requisito → implementação → evidência está na seção 6.

---

## 1. Identificação do Grupo

| Campo | Valor |
|---|---|
| Nome do grupo | PytStop |
| Turma | 15SOAT — Pós-Graduação em Arquitetura de Software (FIAP) |

### Participantes

| Nome | RM | Discord |
|---|---|---|
| João Amaral | RM373448 | joao_13997 |
| Allan Aurélio | RM372116 | all66_ |
| Carlos Silva | RM374191 | carlossilva156 |
| Guilherme Sousa | RM373609 | romen0 |
| Nicolas Gerbi | RM372644 | sethiiz_gerbi |

## 2. Link do Repositório

Repositório privado no GitHub, compartilhado com `soat-architecture` conforme exigido pelo enunciado. A fase 2 continua no mesmo histórico da fase 1: o repositório preserva os 118 commits do MVP ([PR #11](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/11)) e evolui a partir deles.

| Recurso | URL |
|---|---|
| Repositório | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2 |
| README (arquitetura, execução local, deploy K8s, Terraform) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/README.md |
| Dockerfile | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/Dockerfile |
| docker-compose.yml | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docker-compose.yml |
| Manifests Kubernetes (`/k8s`) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/k8s |
| Scripts Terraform (`/infra`) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/infra |
| Pipeline de CI (herdada da fase 1) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/ci.yml |
| Pipeline de CD (build de imagem + deploy + smoke test) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/cd.yml |
| Collection das APIs (Postman, gerada do OpenAPI) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/postman_collection.json |

A collection foi gerada a partir do contrato OpenAPI vivo da aplicação (46 requisições agrupadas por tag) e é executável de ponta a ponta — validada com newman contra o cluster ([PR #157](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/157)). O request de decisão externa de orçamento traz um **pre-request script que assina a requisição com HMAC** (`X-Webhook-Signature` + `X-Webhook-Timestamp`, espelhando `webhook_signature.py`). O Swagger UI em `/docs` permanece a referência interativa — instruções de acesso no README.

### Execuções verdes do CD na main

O pipeline de CD provisiona um cluster kind (Kubernetes in Docker) efêmero no runner via Terraform, publica a imagem no GHCR (GitHub Container Registry) com tag imutável por SHA e aplica os manifests com smoke test ao final ([ADR-019](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)):

| Execução | Conteúdo | URL |
|---|---|---|
| Run 27450493913 | Primeiro deploy completo (merge do [PR #21](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/21)) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27450493913 |
| Run 27451618014 | Deploy com OpenTelemetry/Jaeger (merge do [PR #22](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/22)) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/27451618014 |

## 3. Link do Vídeo

Vídeo de até 15 minutos demonstrando deploy, execução do CI/CD, consumo das APIs e escalabilidade automática, conforme o enunciado. Roteiro de gravação: [roteiro-video.md](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/roteiro-video.md).

| Recurso | URL |
|---|---|
| Vídeo de demonstração | _link será adicionado após a gravação_ <!-- VIDEO-LINK-FASE-2 --> |

## 4. Link da Documentação

Toda a documentação versionada está no próprio repositório, na pasta `docs/`.

### 4.1 Índice geral

| Recurso | URL |
|---|---|
| Pasta `docs/` (índice) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/docs |
| Requisitos da fase 2 (enunciado transcrito) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/requisitos/fase2/desafio-tech-fase-2.md |
| Gap analysis — enunciado × código da fase 1 (RF-020–024, RNF-017–024, RN-018–020) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/requisitos/fase2/gap-analysis-fase-2.md |
| Apêndice A — funcionalidades extras da fase 2 (além do enunciado) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/apendice-funcionalidades-extras.md |
| Scans de segurança — fechamento da fase 2 (bateria na HEAD final) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/seguranca/scan-fase-2.md |

### 4.2 Decisões de arquitetura da fase 2

| Artefato | Decisão | URL |
|---|---|---|
| RFC-002 | Infraestrutura e deploy da fase 2 — desenho integrado e diagrama de referência | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md |
| ADR-015 | Clean Architecture como arquitetura alvo (sem rewrite) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md |
| ADR-016 | kind como plataforma Kubernetes (dev, vídeo e CI) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md |
| ADR-017 | PostgreSQL como StatefulSet provisionado pelo Terraform | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/017-provisionamento-banco.md |
| ADR-018 | Notificação de status por e-mail via adapter SMTP com Mailpit | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/018-notificacao-email.md |
| ADR-019 | Pipeline de CI/CD com deploy em cluster kind efêmero no runner | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md |
| ADR-020 | Observabilidade com OpenTelemetry e Jaeger em escopo mínimo | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md |
| ADR-021 | Aprovação e recusa externas de orçamento via token dedicado | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md |
| ADR-022 | Transactional Outbox + relay para entrega de eventos de integração | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/022-transactional-outbox-relay.md |
| ADR-023 | Rate limiter com storage compartilhado (Redis) sob HPA | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md |
| ADR-024 | Métricas de observabilidade com Prometheus e OpenTelemetry no relay | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/024-metricas-prometheus.md |
| ADR-025 | Ambiente cloud de demonstração persistente (Azure for Students / AKS) — aditivo ao kind | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/025-ambiente-cloud-demonstracao.md |

A documentação da fase 1 (Event Storming, Domain Storytelling, Linguagem Ubíqua, mapa de contextos, modelo de domínio, ADRs 001–014) permanece válida e versionada nas mesmas pastas — índice em [`docs/`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/docs).

## 5. Relatório de Análise de Vulnerabilidades

A postura de segurança da fase 2 é **verificada por CI, não afirmada em documento**: os seis scanners que a fase 1 rodava manualmente foram automatizados como gates de pipeline ([PR #116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116), fecha [#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75)) e reexecutados na HEAD final, já sobre **Python 3.14** ([PR #150](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/150)). Os seis passaram verdes — cobrindo `src/` + `relay/` no SAST, dependências de runtime na SCA, a imagem 3.14 no scan de container, segredos, análise semântica e DAST contra a API viva. A sétima camada é o **SonarQube**, scan manual de fechamento de fase ([TD-010/ADR-011](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)), executado na mesma HEAD com todos os achados tratados.

### 5.1 Ferramentas e resultado na HEAD final

| Ferramenta | Tipo | Alvo | Resultado |
|---|---|---|---|
| bandit | SAST | `src/` + `relay/` (10.112 LoC) | 0 high / 0 medium / 0 low |
| pip-audit | SCA — dependências | deps de runtime resolvidas do `uv.lock` | 0 vulnerabilidades (3 CVEs de nicegui dev-only aceitos, [#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/112)) |
| trivy | SCA — imagem Docker | imagem de runtime `pytstop` (Python 3.14) | 0 HIGH/CRITICAL no gate |
| gitleaks | Detecção de segredos | árvore de trabalho, com allowlist | 0 leaks |
| CodeQL | SAST semântico | python + javascript-typescript (default setup) | `Analyze` verde, sem alertas ativos |
| OWASP ZAP | DAST baseline | API viva via OpenAPI (stack compose) | 0 FAIL — 2 WARN aceitos como IGNORE |
| SonarQube | Análise estática + security hotspots | `src/` (7,4k LoC, cobertura importada) | **Quality Gate Passed** — 0 security, 0 reliability, coverage 95,3%; **hotspots 3 → 0** |

No ciclo do SonarQube, a primeira análise apontou **3 security hotspots**: um na regex de extração de e-mail com backtracking polinomial (S5852) e dois em avisos de `http://` no exporter OTLP. A regex foi corrigida no código — e a mesma classe de defeito foi eliminada também na regex do scrubber de logs ([PR #155](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/155)); os avisos de `http://` foram revisados como seguros (tráfego gRPC intra-cluster, com endpoint externo entrando via env com `https`). A reanálise fechou com **0 hotspots**; o antes/depois está no Anexo B do PDF.

Gates em [`security.yml`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/security.yml) (pip-audit, gitleaks, trivy), [`ci.yml`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/ci.yml) (bandit) e [`full-test-ci.yml`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/full-test-ci.yml) (ZAP), mais o CodeQL pelo default setup do GitHub e o Dependabot mensal.

### 5.2 Itens de segurança endereçados

Além dos scans limpos, a auditoria de finalização ([issue #128](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/128)) gerou correções de segurança com teste TDD:

- **Revogação de refresh token** (CWE-613) e logout idempotente ([PR #142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) — [#118](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/118)/[#121](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/121));
- **Corrida TOCTOU (time-of-check/time-of-use) na recusa externa de orçamento** — revalidação sob lock antes do cancelamento ([PR #142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) — [#119](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/119));
- **Item de estoque desativado** barrado em OS nova e na reserva ([PR #142](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/142) — [#120](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/120));
- **Seed com denylist sensível a ambiente** — `seed_admin.py` rejeita o `ADMIN_PASSWORD` público de demo fora de `development`/`test` ([PR #152](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/152) — [#95](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/95); escopo por ambiente no [PR #159](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/159));
- **Papel de usuário fail-closed** — removido `default="admin"` do mapping, inserção sem papel passa a falhar com violação de `NOT NULL` ([PR #152](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/152) — [#96](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/96));
- **Webhook de orçamento assinado por HMAC** ([PR #114](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/114), TD-027), com a collection do Postman assinando via pre-request script ([PR #157](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/157));
- **Rate limiter global sob HPA** com storage compartilhado Redis ([PR #62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62), [ADR-023](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md));
- **Mensagens de erro sem eco de dado pessoal** — invariantes de domínio com PII usam rótulo fixo (varredura dos 75 `raise ValueError`) e o 422 de validação de schema deixou de devolver o `input` cru ([PR #155](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/155) — [#126](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/126));
- **Scrubber de PII nos logs ampliado** — telefones BR sem espaços ou com `+55` colado passam a ser mascarados pelo valor, e os campos `telefone`/`celular`/`contato`, pelo nome ([PR #155](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/155) — [#99](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/99)).

### 5.3 Documentos completos

| Documento | URL |
|---|---|
| Scans de fechamento da fase 2 (v2.1, HEAD final — inclui o ciclo SonarQube) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/seguranca/scan-fase-2.md |
| Relatório de Vulnerabilidades (baseline OWASP API Top 10, fase 1) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/seguranca/relatorio-vulnerabilidades.md |

## 6. Rastreabilidade requisito → evidência

Cada requisito da fase 2 ([gap analysis](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/requisitos/fase2/gap-analysis-fase-2.md)) está mapeado para o PR que o implementou e para a evidência principal no código; a sequência de demonstração está no [roteiro do vídeo](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/roteiro-video.md).

### Requisitos funcionais

| ID | PR | Requisito | Evidência (arquivo / teste chave) |
|---|---|---|---|
| RF-020 | [#15](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/15) | Abertura de OS com cliente, veículo, serviços e peças, retornando id único | `CriarOrdemDTO` com `servicos`/`pecas` (`src/ordem_servico/aplicacao/dtos.py`) e montagem única de itens em `use_cases.py`; e2e `tests/integracao/test_api_e2e.py::TestCriacaoOsComItens` |
| RF-021 | [#14](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/14) | Consulta de status no vocabulário do enunciado | `situacao_de` em `src/ordem_servico/aplicacao/situacoes.py` + campo `situacao` nos 3 schemas de resposta; `tests/unitarios/ordem_servico/test_presenters.py` |
| RF-022 | [#16](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/16) | Endpoint externo de aprovação/recusa de orçamento | Rota `POST /api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento` em `src/compartilhado/interfaces/router_publico.py`; use case `DecidirOrcamento`; [ADR-021](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md) |
| RF-023 | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Listagem ordenada por prioridade de status, sem encerradas (exclusão lógica) | `_PRIORIDADE_STATUS`/`_ESTADOS_ENCERRADOS` + parâmetro `incluir_encerradas` em `src/ordem_servico/infraestrutura/repository.py`; teste-guarda em `tests/unitarios/ordem_servico/test_repository_os.py` |
| RF-024 | [#17](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/17), [#56](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/56) | Notificação de atualização de status por e-mail | Notificação via **Transactional Outbox**: a UnitOfWork grava o `IntegrationEvent` na mesma transação da mudança de OS e o **relay** entrega o e-mail, com idempotência e retries ([ADR-022](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/022-transactional-outbox-relay.md)). Handler de e-mail em `relay/handlers.py` + adapter SMTP em `infraestrutura/`; `tests/unitarios/ordem_servico/test_notificacoes.py` |

### Requisitos não funcionais

| ID | PR | Requisito | Evidência (arquivo / teste chave) |
|---|---|---|---|
| RNF-017 | [#12](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/12) | Clean Architecture formalizada e verificada | Contratos de camadas em `[tool.importlinter]` (`pyproject.toml`), verificados na CI (step *Architecture contracts*, `lint-imports`; paridade local via `make lint-arch`); [ADR-015](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) |
| RNF-018 | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13)–[#17](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/17) (transversal) | Testes dos fluxos críticos mantidos na evolução | Gate de 95% em `.coveragerc` (1.617 testes unitários + 163 de integração na HEAD final); cobertura de 95,3% em `src/` medida no fechamento (Anexo A) — CI verde na main ([run 28637221227](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/actions/runs/28637221227)) |
| RNF-019 | [#18](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/18) | Dockerfile e docker-compose revisados (healthcheck do app) | `HEALTHCHECK` no `Dockerfile` + bloco `healthcheck` do serviço `app` no `docker-compose.yml`, ambos probando `/api/v1/saude` |
| RNF-020 | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19) | Manifests K8s: Deployment, Service, ConfigMap, Secret, HPA | [`k8s/`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/k8s) — `namespace.yaml`, `deployment.yaml`, `service.yaml`, `configmap.yaml`, `secret.yaml`, `hpa.yaml`, `jobs/migration-job.yaml`, `mailpit.yaml`, `jaeger.yaml`, `relay.yaml`, `redis.yaml`, `prometheus.yaml`, `ui-{deployment,service,configmap}.yaml` (UI no cluster, issue #186) |
| RNF-021 | [#20](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/20) | IaC: Terraform provisiona cluster e banco, documentado | [`infra/`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/infra) — cluster kind + namespace + Secret + StatefulSet PostgreSQL + Service num único apply; recursos documentados em `infra/README.md` |
| RNF-022 | [#21](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/21) | CI/CD: build, testes, imagem, deploy de banco e app, manifests | [`.github/workflows/cd.yml`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/cd.yml) + alvos `make k8s-up`/`k8s-smoke`/`cd-local` espelhando o workflow |
| RNF-023 | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19) | HPA-readiness: probes e resources no Deployment | Liveness/readiness em `/api/v1/saude` + requests/limits em `k8s/deployment.yaml`; metrics-server instalado pelo fluxo de deploy |
| RNF-024 | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19), [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62) | Statelessness para escala horizontal | JWT stateless com denylist no PostgreSQL (fase 1); `ENCRYPTION_KEY` única e estável via `k8s/secret.yaml`; pool dimensionado para o pior caso do HPA (`DB_POOL_SIZE`); rate limiter com **storage compartilhado (Redis)** via `storage_uri` → limite por IP correto e **global sob HPA** (não diverge entre réplicas), com degradação graciosa para per-réplica se o Redis cair ([ADR-023](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md), TD-016) |

### Regras de negócio

| ID | PR | Regra | Evidência (arquivo / teste chave) |
|---|---|---|---|
| RN-018 | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Prioridade Em execução > Aguardando aprovação > Em diagnóstico > Recebida; mais antigas primeiro, desempate por id | `CASE` de prioridade + `criado_em ASC, id` em `src/ordem_servico/infraestrutura/repository.py` |
| RN-019 | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Exclusão lógica de `FINALIZADA`/`ENTREGUE` (nenhum delete físico) | Filtro de consulta `notin_(_ESTADOS_ENCERRADOS)`; `incluir_encerradas=true` prova que as linhas permanecem |
| RN-020 | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) (ratificada no [ADR-021](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md)) | Status extras: complementar ordena com Aguardando aprovação; `CANCELADA` excluída como encerrada | Teste-guarda de totalidade dos 8 estados em `tests/unitarios/ordem_servico/test_repository_os.py` |

**Além dos requisitos**: observabilidade com OpenTelemetry. **Traces** de FastAPI e SQLAlchemy no Jaeger ([ADR-020](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md), [PR #22](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/22)); **métricas** do relay no Prometheus — profundidade da outbox, idade do pendente mais antigo, DLQ (dead-letter queue) e contadores de entrega/falha/retry, via `MeterProvider` OTel + `PrometheusMetricReader` ([ADR-024](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/024-metricas-prometheus.md), [PR #66](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/66), TD-022). Ambos rodam no cluster de demo e são demonstrados no bloco 6 do vídeo.

### Qualidade além do escopo — dívida técnica endereçada

O backlog de dívida técnica é mantido como um ledger versionado em [`docs/tech-debt/README.md`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/tech-debt/README.md), com itens classificados e rastreados desde a fase 1. O ledger registra hoje **29 itens resolvidos** e **5 abertos** (todos deliberados e justificados, sem impacto de produção no caminho suportado; os achados da [auditoria pré-entrega](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/tech-debt/auditoria-pre-entrega-fase2.md) foram endereçados por completo). Fora do escopo exigido pela fase 2, o grupo amortizou parte expressiva desse backlog — incluindo um débito tático de DDD herdado da fase 1 — atacando-o em tiers priorizados ([plano-ataque.md](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/tech-debt/plano-ataque.md)) e mantendo o ledger fiel ao código. Os principais:

| Item | PR | O que foi feito |
|---|---|---|
| TD-009 (DDD tático — fase 1) | [#48](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/48) | Emissão dos eventos de criação que faltavam no event storming, `ClienteCadastrado` e `ServicoCadastrado`, via factory `criar()` nos agregados, com payload sem PII e teste de regressão |
| TD-008 (Transactional Outbox — RF-018) | [#56](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/56) | Dispatch de eventos passou a usar outbox transacional + processo relay (claim-then-deliver, head-of-line, backoff/DLQ, idempotência via processed_events, LISTEN/NOTIFY) — elimina o dual-write das notificações |
| TD-016 (rate limiter sob HPA — RNF-024) | [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62) | Rate limiter slowapi com storage compartilhado (Redis), opt-in por env, com degradação graciosa; limite correto entre réplicas |
| TD-022 (métricas do relay — observabilidade) | [#66](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/66) | Pilar de **métricas** no relay: Prometheus no cluster + `MeterProvider` OTel/`PrometheusMetricReader` expondo `/metrics`, opt-in por env; complementa a [ADR-020](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md) na parte de métricas ([ADR-024](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/024-metricas-prometheus.md)) |
| TD-015 (corrida de migração multi-réplica — infra) | [#64](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/64) | Migração movida do entrypoint do pod para um Job dedicado (`pytstop-migrate`), aplicado antes do rollout com `kubectl wait --for=condition=complete`; `RUN_MIGRATIONS_ON_STARTUP`/`RUN_SEED_ON_STARTUP` passam a `false` no cluster — resolve a corrida com N réplicas |
| TD-011 (DAST automatizado — segurança) | [#65](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/65) | OWASP ZAP baseline automatizado no `full-test-ci` (DAST contra a stack compose), relatório como artefato + alvo `make dast` para paridade local |
| TD-021 (relay HA — fencing de lease) | [#66](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/66) | Fencing de lease na entrega (re-lock `FOR UPDATE SKIP LOCKED` + checagem de status na transação por-linha) torna `replicas>1` seguro sem duplicar entrega, sem mudança de schema |
| TD-023 (rate-limit por cliente real atrás de proxy — segurança/RNF-024) | [#67](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/67) | `ProxyHeadersMiddleware` do uvicorn aplicado quando `TRUSTED_PROXIES` está configurado, reescrevendo `request.client` a partir do `X-Forwarded-For` confiável; default vazio (não confia em XFF, sem spoof) |
| TD-005 (orçamento em coluna Text — domínio) | [#68](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/68) | Coluna `orcamento_json` migrada de `Text` para `jsonb` nativo (migração 004), removendo a camada manual `json.dumps`/`json.loads` no mapping; serialização passa a seguir o padrão de `outbox.payload` |
| TD-007 (contato como primitivo — DDD) | [#70](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/70) | `Contato` Value Object (texto livre validado, `__repr__` PII-safe) substitui o `contato: str` primitivo no agregado `Cliente`, persistindo na mesma coluna via shadow + event listeners (padrão CPF/Placa, sem migração) |
| TD-010 (SonarQube como gate de CI — segurança) | [#71](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/71) | Fechado **por decisão**: SonarQube/SonarCloud não vira gate de CI (repo privado + custo desproporcional ao MVP); a análise estática em CI é CodeQL + ruff + bandit, com SonarQube como scan manual de fechamento |
| Reconciliação do ledger | [#47](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/47) | Auditoria item a item de `tech-debt/README.md` contra o código: TD-003 (CSP) e TD-017 (PII no OpenTelemetry) marcados como resolvidos (já implementados) e TD-002/004/005/008/016 corrigidos para refletir o estado real |
| TD-019 (Clean Architecture) | [#50](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/50) | Extração de `PasswordHasherPort`/`JWTServicePort` na autenticação, removendo o último acoplamento `aplicação → infraestrutura`; o contrato `forbidden` do import-linter passou a verificá-lo globalmente em todos os contextos, reforçando a **RNF-017** |
| #75 (gates de segurança em CI) | [#116](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/116) | Automação dos scanners que os docs de segurança citavam mas nenhum workflow rodava: **pip-audit** (CVE em deps — pegou e corrigiu 5 CVEs reais em cryptography/starlette), **gitleaks** (segredos) e **trivy** (CVE na imagem) em [`security.yml`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/.github/workflows/security.yml); escopo do **bandit** ampliado (`src ui relay scripts`); **CodeQL** confirmado no default setup do GitHub + `make codeql-quality` local aplicando as supressões de falsos positivos que o default setup não permite; **Dependabot** habilitado (hoje com cadência mensal) |

A tabela acima destaca os itens de maior valor; o conjunto completo dos **29 resolvidos** (incluindo itens fechados nas campanhas de finalização da fase 2 e pendências herdadas da fase 1) está no [ledger](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/tech-debt/README.md#itens-resolvidos-29).

Isso concretiza a Boy Scout Rule registrada na estratégia de pagamento do [ledger de dívida técnica](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/tech-debt/README.md): cada evolução deixa o código e a documentação melhores do que os encontrou.

## 7. Desenho da arquitetura

Diagrama de referência da fase 2 — pipeline de deploy, infraestrutura provisionada e workloads no cluster. Fonte única: [RFC-002 §3](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md).

<!-- fonte: RFC-002 §3 — manter em sincronia -->
```mermaid
flowchart TB
    push_main(["Push na main"]) --> ci_stage

    subgraph gha["GitHub Actions — pipeline de CI/CD (ADR-019)"]
        ci_stage["CI herdada<br/>ruff · mypy · bandit ·<br/>testes com gate de 95%"] --> build_img["Build da<br/>imagem Docker"]
        build_img --> publish["Push no GHCR<br/>tag = SHA do commit"]
        publish --> cd_job["Job de CD<br/>terraform apply · kind load ·<br/>kubectl apply · smoke test"]
    end

    ghcr[("GHCR<br/>imagem versionada por SHA")]
    publish --> ghcr

    cd_job -->|"terraform apply"| infra_tf
    cd_job -->|"kubectl apply -f k8s/"| k8s_app
    ghcr -.->|"kind load — imagem injetada<br/>nos nós, sem pull do registry"| app

    subgraph cluster["Cluster kind (ADR-016) — dev local, vídeo e CI efêmero"]
        subgraph infra_tf["/infra — Terraform (ADR-016, ADR-017)"]
            pg[("PostgreSQL 16<br/>StatefulSet + PVC")]
            ms["metrics-server"]
        end
        subgraph k8s_app["/k8s — manifests da aplicação"]
            svc["Service"]
            app["PytStop API — Deployment<br/>Clean Architecture (ADR-015):<br/>Entidades · Casos de Uso ·<br/>Adaptadores de Interface ·<br/>Frameworks & Drivers"]
            cfg["ConfigMap + Secret"]
            hpa["HPA — CPU e memória"]
            mailpit["Mailpit (ADR-018)<br/>Deployment + Service ClusterIP"]
            jaeger["Jaeger all-in-one (ADR-020)<br/>tracing — deploy opcional"]
            relay["Relay de eventos (ADR-022)<br/>Deployment — outbox→SMTP"]
            redis["Redis (ADR-023)<br/>Deployment + Service — rate limit"]
            prometheus["Prometheus (ADR-024)<br/>Deployment + Service — métricas do relay"]
            ui["UI de demonstração (NiceGUI)<br/>Deployment + Service ClusterIP<br/>BACKEND_URL → pytstop-api"]
        end
    end

    svc --> app
    cfg -.->|"env vars"| app
    hpa -->|"escala réplicas"| app
    ms -.->|"métricas de CPU e memória"| hpa
    ui -->|"consome a API no cluster"| svc
    app -->|"SQL via DATABASE_URL"| pg
    app -->|"grava outbox + NOTIFY"| pg
    relay -->|"LISTEN/NOTIFY + claim outbox"| pg
    relay -->|"SMTP"| mailpit
    app -.->|"rate limit"| redis
    app -.->|"traces OTLP"| jaeger
    prometheus -.->|"scrape /metrics"| relay
```

No fluxo acima, a CI atua como gate no PR (antes do merge); no push à `main`, CI e CD disparam em paralelo — a seta sequencial representa a ordem lógica (qualidade antes do deploy), não uma dependência entre workflows.

A demo pode ser conduzida inteiramente no cluster: a UI de simulação (NiceGUI, [issue #186](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/186)) sobe como o Deployment `pytstop-ui` e consome a API pelo Service interno `pytstop-api:8000` — `make cd-local` a implanta junto com o resto, e `kubectl -n pytstop port-forward svc/pytstop-ui 8080:8080` a expõe em `http://localhost:8080`. Alternativamente, o `docker-compose.yml` sobe a mesma UI localmente (`make up`); o passo a passo dos dois caminhos está no [README](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/README.md#ui-de-simula%C3%A7%C3%A3o) e no [`k8s/README.md`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/k8s/README.md).

### Evolução das camadas — da Onion (fase 1) à Clean Architecture (fase 2)

A fase 1 organizava cada contexto delimitado em quatro camadas no modelo Onion ([ADR-003](../../arquitetura/adr/003-arquitetura-ddd-onion.md)): `dominio/`, `aplicacao/`, `infraestrutura/` e `interfaces/`, com a regra de dependência apontando para dentro, ports declarados em `aplicacao/` e adapters concretos na borda — mas sem ordem formal entre `interfaces/` e `infraestrutura/`.

<!-- fonte: ADR-003 — camadas da fase 1 -->
```mermaid
flowchart TB
    subgraph borda["Borda — interfaces/ e infraestrutura/, sem subdivisão formal"]
        direction TB
        i1["interfaces/<br/>routers FastAPI, schemas"]
        n1["infraestrutura/<br/>ORM, repositórios, PostgreSQL"]
        subgraph app1["aplicacao/ — casos de uso, DTOs, ports, UnitOfWork"]
            dom1["dominio/ — entidades, agregados, value objects, eventos"]
        end
    end
```

A refatoração da fase 2 ([ADR-015](../../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md), RNF-017) adotou a Clean Architecture sem rewrite: o núcleo ports & adapters permaneceu válido, e a mudança formalizou a nomenclatura de Martin e subdividiu a borda — `interfaces/` virou a camada de **Adaptadores de Interface** (controllers e presenters) e `infraestrutura/` a de **Frameworks & Drivers** (gateways SQLAlchemy, ORM, conexão com o banco), cada uma com papel e regras próprios.

<!-- fonte: ADR-015 — camadas da fase 2 -->
```mermaid
flowchart TB
    subgraph fd["Frameworks & Drivers — infraestrutura/ (gateways SQLAlchemy, ORM, PostgreSQL, SMTP)"]
        subgraph ad["Adaptadores de Interface — interfaces/ (controllers FastAPI, presenters Pydantic)"]
            subgraph uc["Casos de Uso — aplicacao/ (use cases, DTOs, ports, UnitOfWork)"]
                ent["Entidades — dominio/<br/>entidades, agregados, value objects, eventos"]
            end
        end
    end
```

A regra de dependência deixou de ser convenção e virou gate: o [import-linter](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/pyproject.toml) roda na CI com três contratos — camadas `interfaces → aplicacao → dominio` em todos os contextos (inclusive o shared kernel), proibição de `dominio/` e `aplicacao/` importarem `infraestrutura/`, e independência entre contextos delimitados ([ADR-015](../../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md)).

### Ambiente cloud de demonstração (opcional — ADR-025)

Além do cluster kind (dev, vídeo e CI), a solução pode ser publicada num **AKS gerenciado** como ambiente vivo para a banca navegar durante a avaliação — **aditivo**, sem alterar o CD canônico do RNF-022. Reusa as mesmas imagens por SHA, os mesmos manifests de `k8s/` (via _overlay_ kustomize) e o mesmo Job de migração; só o provisionamento (`infra/azure/`) e um punhado de ajustes de deploy (ENVIRONMENT de produção, ingress, segredos reais) diferem. A decisão, os trade-offs de custo e o fallback estão no [ADR-025](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/025-ambiente-cloud-demonstracao.md); o plano de execução na [issue #188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188).

> **Ambiente de demonstração na nuvem:** `CLOUD-URL-FASE-2` — disponível **24/7 durante julho/2026** (horário de Brasília); a banca pode abrir a qualquer hora do mês. A partir de 01/08/2026 o ambiente é destruído para preservar o crédito de estudante e reerguível sob demanda em ~10 min (deploy 100% reproduzível). Custo mantido próximo de zero por _node_ único, ingress via NodePort + `nip.io` (sem LoadBalancer) e destruição fora da janela — risco financeiro zero (conta de estudante sem cartão). Este ambiente é um **diferencial**: o aceite do enunciado (vídeo + repositório + IaC do kind) não depende dele.

## 8. Conteúdo do PDF de submissão

O PDF entregue no portal do aluno é gerado a partir deste documento pelo [`scripts/build-entrega-pdf.sh`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/scripts/build-entrega-pdf.sh), que acrescenta uma **capa ABNT** no início, renderiza os diagramas Mermaid como imagens, converte os links relativos em absolutos e anexa os apêndices de evidência. A seção 9 (Pendências) é um checklist interno da equipe e **não** é incluída no PDF submetido.

O PDF contém os três itens exigidos pelo enunciado:

1. **Link do repositório GitHub** compartilhado com o usuário `soat-architecture`: https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2
2. **Desenho da arquitetura** com os recursos escolhidos (seção 7 — kind, Terraform, GHCR, manifests K8s com HPA, Mailpit, Jaeger, Prometheus).
3. **Link do vídeo** de até 15 minutos apresentando a solução (seção 3 — preenchido após a gravação).

Mais três anexos de evidência de profundidade:

- **Anexo A — Scans de Segurança da Fase 2**: bateria de fechamento na HEAD final ([`scan-fase-2.md`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/seguranca/scan-fase-2.md)).
- **Anexo B — Evidências Visuais**: capturas da demonstração no cluster (pipeline verde, HPA escalando 1 → 5, traces no Jaeger, e-mails no Mailpit, métricas no Prometheus e o antes/depois do SonarQube — hotspots 3 → 0, Quality Gate Passed).
- **Anexo C — Funcionalidades Extras da Fase 2**: catálogo além do enunciado ([`apendice-funcionalidades-extras.md`](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/apendice-funcionalidades-extras.md)).

## 9. Pendências para fechar a entrega

Ações manuais que permanecem com a equipe (nenhuma bloqueia a navegação do repositório):

| # | Pendência | Onde |
|---|---|---|
| 1 | Confirmar/convidar `soat-architecture` como colaborador do repositório | GitHub → Settings → Collaborators |
| 2 | Gravar o vídeo seguindo o [roteiro](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/roteiro-video.md) e publicar (YouTube/Vimeo, não listado) | — |
| 3 | Preencher o link do vídeo na seção 3 deste documento e no README (marcadores `VIDEO-LINK-FASE-2`) | `docs/entrega/fase2/entrega-fase-2.md` + `README.md` |
| 4 | Mergear as alterações finais (link do vídeo) na `main` — os links do PDF apontam para a `main` | PR do branch de entrega |
| 5 | Regerar o PDF (`documento-entrega-fase-2.pdf`) com o link do vídeo preenchido e submeter no portal do aluno | fluxo descrito no [README da pasta](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/entrega/fase2/README.md) |
| 6 _(opcional, diferencial)_ | Subir o ambiente cloud de demonstração e preencher a URL na seção 7 (marcador `CLOUD-URL-FASE-2`) | bootstrap Azure + Environment `cloud`; ver [ADR-025](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/blob/main/docs/arquitetura/adr/fase2/025-ambiente-cloud-demonstracao.md) e [#188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188) |

---

> [↑ Raiz do projeto](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2) · [↑ Entrega Fase 2](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/tree/main/docs/entrega/fase2)
