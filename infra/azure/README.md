# `infra/azure/` — ambiente cloud de demonstração (AKS)

> [↑ Raiz do projeto](../../README.md) · [↑ infra/](../README.md)

Módulo Terraform **irmão** de [`infra/`](../README.md) (kind), que fica intocado.
Provisiona um **AKS _tier_ Free com node único** para dar uma **URL pública** à
banca durante a avaliação — **opcional e aditivo** ao CD canônico do kind
([ADR-019](../../docs/arquitetura/adr/fase2/019-pipeline-cicd-deploy.md)).
Decisão, custo e trade-offs: [ADR-025](../../docs/arquitetura/adr/fase2/025-ambiente-cloud-demonstracao.md);
plano: [issue #188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188).

Escopo deste módulo: **só o cluster** (resource group + AKS). Postgres, app e UI
sobem pelo overlay [`k8s/overlays/cloud/`](../../k8s/overlays/cloud/), aplicado
pelo `make cloud-up` — separar cluster (Terraform) de cargas (kubectl/kustomize)
evita o provider kubernetes _chained_ ao cluster no mesmo apply, frágil no AKS.

## Pré-requisitos

- **Azure CLI** (`az`) + `az login` na conta **Azure for Students** (e-mail FIAP).
- **Packages GHCR públicos** — `-app` e `-ui`. O AKS puxa a imagem do GHCR pela
  tag do SHA que o CD já buildou (amd64); públicos dispensam `imagePullSecret`.
  Package settings → Danger Zone → Change visibility → Public.
- `terraform`, `kubectl` (kustomize embutido), `docker` — já usados pelo fluxo kind.

## Uso (deploy local por `make`)

```bash
az login                 # conta Azure for Students
make cloud-up            # provisiona AKS + deploy + imprime a URL pública
make cloud-url           # (re)descobre o IP do LoadBalancer, ajusta CORS
make cloud-down          # DESTROI tudo (cluster + node + LB + disco) -> custo zero
```

`make cloud-up` faz, em ordem: provisiona o AKS (`terraform`), busca o kubeconfig
(`az aks get-credentials`), gera segredos fortes em `.env.cloud` (git-ignored,
via [`scripts/cloud-secrets.sh`](../../scripts/cloud-secrets.sh)) e os materializa
em `Secret`s do cluster, aplica o overlay (config `production` + postgres + UI),
roda o **Job de migração antes do rollout** e sobe deployment/relay/UI. A senha do
admin é impressa e guardada em `.env.cloud`.

> **Custo:** node B2als_v2 + LB/IP ≈ US$ 45–50/mês 24/7. Julho fica no ar; a
> partir de agosto rode `make cloud-down` — o crédito de estudante não tem cartão,
> então crédito esgotado = recursos param, nunca cobrança. Configure um _budget
> alert_ (Cost Management → Budgets, 50%/80%).

## Deploy por CI (OIDC) — evolução opcional

O `make cloud-up` local é o caminho garantido. Para o CD por GitHub Actions
disparar o deploy (job `deploy-cloud`, `workflow_dispatch`), faça o **bootstrap
OIDC** (federated credential — sem senha estática). No `az`:

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
APP_ID=$(az ad app create --display-name "pytstop-cd-github" --query appId -o tsv)
az ad sp create --id "$APP_ID"
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-cloud-env",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:fiap-postech-sw-architecture/postech-sw-arch-p2:environment:cloud",
  "audiences": ["api://AzureADTokenExchange"]
}'
az role assignment create --assignee "$APP_ID" --role Contributor \
  --scope "/subscriptions/$SUBSCRIPTION_ID"
```

Depois crie o **GitHub Environment `cloud`** (Settings → Environments) com
_required reviewers_ e os secrets: `AZURE_CLIENT_ID` (= `$APP_ID`),
`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` + os de produção (`JWT_SECRET`,
`ENCRYPTION_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ORCAMENTO_WEBHOOK_TOKEN`).

> **Atenção:** tenants de universidade frequentemente **bloqueiam `az ad app create`**
> para alunos. Se der erro de autorização, o CD por OIDC não é possível — use o
> `make cloud-up` local (mesmo IaC, sem CI). Nesse caso o backend de estado pode
> continuar local; para CI seria necessário backend remoto (Storage Account).

> [↑ Raiz do projeto](../../README.md) · [↑ infra/](../README.md)
