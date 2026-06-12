# k8s — Manifests Kubernetes da aplicação

> [↑ Raiz do projeto](../README.md)

Manifests da aplicação PytStop para o cluster kind da fase 2 (RNF-020): Deployment, Service, ConfigMap, Secret e HPA, mais o Mailpit de demonstração ([ADR-018](../docs/arquitetura/adr/fase2/018-notificacao-email.md)). O desenho integrado está na [RFC-002](../docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md) (§2, §5 e §6).

| Arquivo | Recurso |
|---|---|
| `namespace.yaml` | Namespace `pytstop` |
| `configmap.yaml` | `pytstop-config` — configuração não sensível |
| `secret.yaml` | `pytstop-secrets` — segredos com **valores de demonstração** |
| `deployment.yaml` | `pytstop-api` — API com probes e resources (RNF-023) |
| `service.yaml` | `pytstop-api` — ClusterIP na porta 8000 |
| `hpa.yaml` | HPA por CPU e memória, 1–5 réplicas |
| `mailpit.yaml` | Mailpit — SMTP de demo + UI web |

A infraestrutura-base (cluster kind, metrics-server e PostgreSQL no namespace `pytstop-infra`) é provisionada pelo Terraform de `/infra` (RNF-021) — fronteira descrita na RFC-002 §2.

## Pré-requisitos

- Cluster kind no ar com **metrics-server** e PostgreSQL acessível em `postgres.pytstop-infra.svc.cluster.local:5432`, ambos provisionados pelo `terraform apply` de `/infra` ([ADR-016](../docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md), [ADR-017](../docs/arquitetura/adr/fase2/017-provisionamento-banco.md));
- Imagem da API carregada nos nós — o repositório GHCR é privado e o fluxo usa `kind load`, sem `imagePullSecret` (RFC-002 §4):

  ```bash
  docker build -t ghcr.io/jbamaral/postech-sw-arch-p2-app:dev .
  kind load docker-image ghcr.io/jbamaral/postech-sw-arch-p2-app:dev --name <nome-do-cluster>
  ```

  No CD, a tag `dev` é substituída pela tag imutável do SHA do commit ([ADR-019](../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)).

## Aplicar

`kubectl apply -f` processa o diretório em ordem alfabética — num cluster novo, crie o namespace antes:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

Com o namespace já existente, reaplicações funcionam direto com `kubectl apply -f k8s/`.

## Conferir

```bash
kubectl get pods -n pytstop                  # pytstop-api e mailpit 1/1 Running
kubectl get hpa -n pytstop                   # percentuais de cpu/memoria (exige metrics-server)
kubectl logs -n pytstop deploy/pytstop-api   # migracao + seed + uvicorn no boot
```

O primeiro boot roda `alembic upgrade head` e o seed do admin (best-effort) antes de o uvicorn atender — a readiness só passa com o schema migrado (RFC-002 §7).

## Port-forward

```bash
kubectl port-forward -n pytstop svc/pytstop-api 8000:8000   # API: http://localhost:8000/docs
kubectl port-forward -n pytstop svc/mailpit 8025:8025       # Mailpit UI: http://localhost:8025
```

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

Remove aplicação, Mailpit e configuração de uma vez. A infraestrutura de `/infra` (cluster e banco) é gerenciada pelo Terraform (`terraform destroy`).

---

> [↑ Raiz do projeto](../README.md)
