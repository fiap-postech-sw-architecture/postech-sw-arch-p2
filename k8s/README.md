# k8s — Manifests Kubernetes da aplicação

> [↑ Raiz do projeto](../README.md)

Manifests da aplicação PytStop para o cluster kind da fase 2 (RNF-020): Deployment, Service, ConfigMap, Secret e HPA, mais o Mailpit de demonstração ([ADR-018](../docs/arquitetura/adr/fase2/018-notificacao-email.md)), o Jaeger de traces ([ADR-020](../docs/arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)) e o Prometheus que coleta as métricas do relay ([ADR-024](../docs/arquitetura/adr/fase2/024-metricas-prometheus.md)). O desenho integrado está na [RFC-002](../docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) (§2, §5 e §6).

| Arquivo | Recurso |
|---|---|
| `namespace.yaml` | Namespace `pytstop` |
| `configmap.yaml` | `pytstop-config` — configuração não sensível |
| `secret.yaml` | `pytstop-secrets` — segredos com **valores de demonstração** |
| `deployment.yaml` | `pytstop-api` — API com probes e resources (RNF-023) |
| `service.yaml` | `pytstop-api` — ClusterIP na porta 8000 |
| `hpa.yaml` | HPA por CPU e memória, 1–5 réplicas |
| `mailpit.yaml` | Mailpit — SMTP de demo + UI web |
| `jaeger.yaml` | Jaeger all-in-one — traces OTLP da demo (ADR-020) |
| `prometheus.yaml` | Prometheus — Deployment + Service (9090) que faz *scrape* das métricas do relay (ADR-024) |
| `relay.yaml` | Relay de eventos + Service `pytstop-relay-metrics` (9100) expondo o `/metrics` do relay (ADR-022/ADR-024) |
| `jobs/migration-job.yaml` | `pytstop-migrate` — Job de migração do schema (TD-015), **aplicado à parte** (ver abaixo) |

> O `jobs/migration-job.yaml` fica num **subdir** de propósito: `kubectl apply -f k8s/` não é recursivo, então o Job **não** entra no apply do diretório. Ele é aplicado separadamente, com a tag do SHA substituída, **antes do rollout** (seção [Aplicar](#aplicar)) — resolve a corrida de migração com N réplicas (TD-015; [ADR-019](../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)).

> ⚠️ **Deploy fora do pipeline não é suportado (TD-026).** A ordem _migração → rollout_ é garantida **apenas** pelo caminho imperativo (`make cd-local` / `make k8s-up` / [`cd.yml`](../.github/workflows/cd.yml)), que aplica o Job `pytstop-migrate` e espera `kubectl wait --for=condition=complete` **antes** do `kubectl set image`. Um `kubectl apply -f k8s/` seguido de `set image` manual — ou um fluxo GitOps puro (Argo/Flux) sem hook/sync-wave — **pula esse gate**: código novo pode subir contra um schema antigo. Não há initContainer / Helm hook que auto-force a ordem (decisão aceita para o MVP — o cluster é descartável e o deploy é sempre via pipeline). Se um dia o deploy migrar para GitOps, mover a migração para um **sync-wave / hook** anterior ao rollout.

A infraestrutura-base (cluster kind e PostgreSQL no namespace `pytstop-infra`) é provisionada pelo Terraform de `/infra` (RNF-021); o **metrics-server** (pré-requisito do HPA) é instalado pelo fluxo integrado abaixo — fronteira descrita na RFC-002 §2.

## Fluxo integrado (`make cd-local` / CD na main)

O caminho recomendado executa tudo de uma vez ([ADR-019](../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)):

```bash
make cd-local    # = k8s-up (terraform + build + kind load + metrics-server + manifests + rollout) + k8s-smoke
make k8s-down    # terraform destroy — remove cluster, banco e app
```

Push na `main` roda o mesmo fluxo num cluster kind efêmero do runner, com a imagem publicada no GHCR com tag por SHA do commit — workflow [`.github/workflows/cd.yml`](../.github/workflows/cd.yml) (RNF-022). As seções seguintes documentam os mesmos passos para execução manual.

## Pré-requisitos

- Cluster kind no ar com PostgreSQL acessível em `postgres.pytstop-infra.svc.cluster.local:5432`, provisionados pelo `terraform apply` de `/infra` ([ADR-016](../docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md), [ADR-017](../docs/arquitetura/adr/fase2/017-provisionamento-banco.md));
- **metrics-server** instalado (`make k8s-up` instala e aplica o patch `--kubelet-insecure-tls` que o kind exige);
- Imagem da API carregada nos nós — o repositório GHCR é privado e o fluxo usa `kind load`, sem `imagePullSecret` (RFC-002 §4):

  ```bash
  docker build -t ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev .
  kind load docker-image ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev --name <nome-do-cluster>
  ```

  No CD, a tag `dev` é substituída pela tag imutável do SHA do commit ([ADR-019](../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)).

## Aplicar

`kubectl apply -f` processa o diretório em ordem alfabética — num cluster novo, crie o namespace antes:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

Com o namespace já existente, reaplicações funcionam direto com `kubectl apply -f k8s/`.

### Migração (Job dedicado, antes do rollout)

O `kubectl apply -f k8s/` **não** aplica o `jobs/migration-job.yaml` (subdir, apply não-recursivo). Depois dos manifests e **antes** do `set image`/rollout, aplique o Job de migração com a tag imutável do SHA substituída no lugar do placeholder `:dev` e aguarde a conclusão — é o gate que garante o schema em head antes de qualquer réplica subir (TD-015):

```bash
kubectl -n pytstop delete job pytstop-migrate --ignore-not-found
sed "s|ghcr.io/fiap-postech-sw-architecture/postech-sw-arch-p2-app:dev|<imagem:tag-do-SHA>|" k8s/jobs/migration-job.yaml \
  | kubectl -n pytstop apply -f -
kubectl -n pytstop wait --for=condition=complete --timeout=180s job/pytstop-migrate
```

O fluxo integrado (`make cd-local` / CD na main) já executa esses passos na ordem certa — esta seção documenta o caminho manual. O Job roda `alembic upgrade head` (migração obrigatória — falha reprova o Job e aborta o deploy) seguido do seed do admin best-effort.

## Conferir

```bash
kubectl get pods -n pytstop                  # pytstop-api, mailpit, jaeger e prometheus 1/1 Running
kubectl get hpa -n pytstop                   # percentuais de cpu/memoria (exige metrics-server)
kubectl logs -n pytstop deploy/pytstop-api   # so uvicorn no boot (migracao roda no Job)
kubectl logs -n pytstop job/pytstop-migrate  # alembic upgrade head + seed do admin
```

No cluster a migração **não** roda no boot do pod: o Job `pytstop-migrate` roda `alembic upgrade head` e o seed do admin (best-effort) **antes do rollout** (`RUN_MIGRATIONS_ON_STARTUP=false`/`RUN_SEED_ON_STARTUP=false` no ConfigMap). Os pods da API sobem sobre o schema já migrado — a readiness cobre só a subida do uvicorn (TD-015; RFC-002 §7).

## Port-forward

```bash
kubectl port-forward -n pytstop svc/pytstop-api 8000:8000   # API: http://localhost:8000/docs
kubectl port-forward -n pytstop svc/mailpit 8025:8025       # Mailpit UI: http://localhost:8025
kubectl port-forward -n pytstop svc/jaeger 16686:16686      # Jaeger UI: http://localhost:16686
kubectl port-forward -n pytstop svc/prometheus 9090:9090    # Prometheus UI: http://localhost:9090
```

## Ver traces no Jaeger (ADR-020)

O ConfigMap liga a instrumentação no cluster de demo (`OTEL_ENABLED=true`): a API exporta traces OTLP direto para o Service `jaeger` (porta 4317). Com o port-forward acima ativo, faça qualquer requisição à API (ex.: login no Swagger ou uma listagem) e abra **http://localhost:16686** — selecione o serviço `pytstop-api` e clique em *Find Traces*. Cada trace mostra a jornada da requisição: span do endpoint FastAPI com os spans das queries SQLAlchemy aninhados. `/api/v1/saude` fica fora do trace de propósito (probes do kubelet gerariam ruído contínuo).

## Ver métricas no Prometheus (ADR-024)

O relay liga as métricas via env **inline** no `k8s/relay.yaml` (`RELAY_METRICS_ENABLED=true`/`RELAY_METRICS_PORT=9100`), e não pelo ConfigMap (diferente do `OTEL_ENABLED` da API, que vem do ConfigMap): o relay expõe `/metrics` no formato Prometheus (porta 9100, Service `pytstop-relay-metrics`) e o **Prometheus faz *scrape*** desse alvo. Com o port-forward do Prometheus acima ativo, abra **http://localhost:9090** e consulte os sinais da outbox: `outbox_pendentes`, `outbox_idade_mais_antigo_seconds`, `outbox_dead` (gauges) e `outbox_entregue_total`/`outbox_falha_total`/`outbox_dead_total`/`outbox_retry_total` (counters). Ausente `RELAY_METRICS_ENABLED`, o relay não sobe o `/metrics` e o alvo fica vazio.

> **Escalar o relay (`replicas>1`)**: os counters (`outbox_*_total`) são in-memory por-processo e o `pytstop-relay-metrics` é um Service ClusterIP (load-balanced), então a `replicas>1` cada *scrape* cai num pod aleatório e `rate()`/`increase()` veriam resets espúrios — operar o relay escalado com counters corretos exige *scrape* por-pod (Service *headless* + *service-discovery*). Os gauges (lidos do banco) não têm esse problema. No demo (`replicas:1`) não se manifesta — detalhe na [ADR-024](../docs/arquitetura/adr/fase2/024-metricas-prometheus.md) (Negativas).

## Validar o HPA

Num terminal, observe o HPA:

```bash
kubectl get hpa -n pytstop -w
```

Noutro, gere carga contra o Service — as réplicas sobem de 1 em direção a 5 quando a utilização cruza o alvo; cessada a carga, o scale-down ocorre após a janela de estabilização padrão (~5 min):

```bash
kubectl run gerador-carga -n pytstop --image=busybox:1.36 --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://pytstop-api:8000/api/v1/saude > /dev/null; done"
```

Para mais pressão, suba mais geradores (`gerador-carga-2`, `gerador-carga-3`...). Respostas `429` do rate limiter (60/min por IP, contador por réplica) são esperadas sob loop e ainda consomem CPU; o roteiro do vídeo usa o `full-test/` como gerador de carga realista ([gap analysis §4](../docs/requisitos/fase2/gap-analysis-fase-2.md)). Ao final:

```bash
kubectl delete pod -n pytstop gerador-carga
```

## Limpar

```bash
kubectl delete namespace pytstop
```

Remove aplicação, Mailpit, Jaeger, Prometheus e configuração de uma vez. A infraestrutura de `/infra` (cluster e banco) é gerenciada pelo Terraform (`terraform destroy`).

---

> [↑ Raiz do projeto](../README.md)
