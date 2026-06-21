# Infraestrutura — Terraform (cluster kind + PostgreSQL)

> [↑ Raiz do projeto](../README.md)

Provisionamento da infraestrutura-base da fase 2 (RNF-021): um único `terraform apply` cria o cluster Kubernetes local ([kind](https://kind.sigs.k8s.io/), [ADR-016](../docs/arquitetura/adr/fase2/016-plataforma-kubernetes.md)) e o PostgreSQL 16 dentro dele ([ADR-017](../docs/arquitetura/adr/fase2/017-provisionamento-banco.md)). Os manifests da aplicação ficam fora daqui, em `/k8s`, aplicados via `kubectl` — a fronteira entre os dois está na [RFC-002 §2](../docs/arquitetura/rfc/fase2/rfc-002-infraestrutura-e-deploy-fase-2.md).

## O que é criado

| Recurso Terraform | O que é |
|---|---|
| `kind_cluster.pytstop` | Cluster kind `pytstop` (1 nó control-plane), imagem de node fixada por tag + digest |
| `kubernetes_namespace.pytstop_infra` | Namespace `pytstop-infra`, que isola a infraestrutura-base dos workloads do app |
| `kubernetes_secret.postgres_credentials` | Secret `postgres-credentials` com `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` |
| `kubernetes_stateful_set.postgres` | StatefulSet `postgres` de réplica única, imagem `postgres:16` (a mesma do docker-compose), PVC de 1Gi via `volumeClaimTemplates`, readiness probe `pg_isready` |
| `kubernetes_service.postgres` | Service ClusterIP `postgres` — DNS interno `postgres.pytstop-infra.svc.cluster.local`, consumido pelos manifests do app |

Credenciais: as variáveis em [`variables.tf`](variables.tf) têm defaults de demonstração (banco `pytstop`, usuário `pytstop`, senha `pytstop-demo`; a senha é `sensitive`). Para sobrescrever fora do cenário de demo: `export TF_VAR_postgres_password=...` antes do apply.

### Conexões e escala horizontal (RNF-024)

O `postgres:16` usa o `max_connections` default (**100**). O pool de conexões da aplicação é dimensionado para o pior caso do HPA: com `maxReplicas=5` ([`k8s/hpa.yaml`](../k8s/hpa.yaml)) e `DB_POOL_SIZE=5` + `DB_MAX_OVERFLOW=10` ([`k8s/configmap.yaml`](../k8s/configmap.yaml)), o teto é `(5 + 10) × 5 = 75` conexões — dentro das 100, com folga para o `pg_isready` e conexões administrativas. Ao aumentar `maxReplicas` ou o pool, recalcule contra o `max_connections` (e, se necessário, eleve-o no StatefulSet em [`postgres.tf`](postgres.tf)).

## Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.7
- Docker em execução (Docker Desktop, Colima ou equivalente) — o cluster kind vive em containers Docker
- `kubectl` (opcional, só para conferir o resultado)

## Aplicar

```bash
terraform -chdir=infra init     # baixa os providers pinados no lock file
terraform -chdir=infra plan     # mostra o que sera criado
terraform -chdir=infra apply    # cria cluster + banco (~2 min)
```

O apply só termina com o PostgreSQL pronto (o provider espera o rollout do StatefulSet) e imprime os outputs: nome do cluster, endpoint do API server, caminho do kubeconfig e DNS do banco.

## Fluxo integrado (`make cd-local` / CD na main)

O `terraform apply` daqui é o primeiro passo do deploy completo ([ADR-019](../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)):

```bash
make cd-local    # terraform apply + build da imagem + kind load + metrics-server + manifests de /k8s + smoke
make k8s-down    # terraform destroy
```

Push na `main` executa o mesmo encadeamento num runner do GitHub Actions, em cluster efêmero — workflow [`.github/workflows/cd.yml`](../.github/workflows/cd.yml) (RNF-022). Os alvos `make` passam `-var cluster_name=$(K8S_CLUSTER)` (default `pytstop`), então `make k8s-up K8S_CLUSTER=outro-nome` provisiona um cluster paralelo — útil para branches irmãs coexistirem.

## Conferir

O provider grava o kubeconfig em `infra/pytstop-config` (caminho no output `kubeconfig_path`, ignorado pelo git) e também o mescla no kubeconfig default, sob o contexto `kind-pytstop`:

```bash
kubectl --context kind-pytstop get pods -n pytstop-infra
# NAME         READY   STATUS    RESTARTS   AGE
# postgres-0   1/1     Running   0          1m

kind get clusters
# pytstop
```

## Destruir

```bash
terraform -chdir=infra destroy
```

Remove o cluster inteiro (e com ele banco, volume e dados). O PVC vive na StorageClass local do kind: os dados sobrevivem a restart de Pod (`kubectl delete pod postgres-0`), mas não à destruição do cluster — limitação aceita no [ADR-017](../docs/arquitetura/adr/fase2/017-provisionamento-banco.md).

## Troubleshooting

| Sintoma | Causa provável | Saída |
|---|---|---|
| `Cannot connect to the Docker daemon` no apply | Docker não está rodando | Suba o Docker (`colima start` no macOS, Docker Desktop no Windows) e repita o apply |
| `node(s) already exist for a cluster with the name "pytstop"` | Cluster criado fora deste state (apply anterior interrompido, ou `kind create cluster` manual) | `kind delete cluster --name pytstop` e repita o apply |
| Apply trava em `kind_cluster.pytstop: Still creating...` por vários minutos | Primeira execução baixa a imagem de node (~1GB) | Aguarde; nas execuções seguintes a imagem já está no cache do Docker |
| Erros do provider `kubernetes` com cluster recém-destruído | State desatualizado apontando para cluster que não existe mais | `terraform -chdir=infra destroy` para reconciliar; caso extremo, apague `infra/*.tfstate*` e o cluster órfão com `kind delete cluster --name pytstop` |

> [↑ Raiz do projeto](../README.md)
