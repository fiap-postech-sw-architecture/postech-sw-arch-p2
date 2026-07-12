# `infra/azure-vm/` — demo pública em VM + k3s (spot)

> [↑ Raiz do projeto](../../README.md) · [↑ infra/](../README.md) · irmão de [`infra/azure-aks/`](../azure-aks/README.md)

Veículo da demonstração pública **enquanto o AKS está bloqueado** na conta
Azure for Students (adendo do [ADR-025](../../docs/arquitetura/adr/fase2/025-ambiente-cloud-demonstracao.md):
o system pool do AKS exige SKUs v5–v7, todos com quota zero e pedido de aumento
negado; VMs avulsas não têm essa trava). Uma VM **`Standard_D2s_v3` Spot**
(2 vCPU/8 GB, ~US$ 0,019/h ≈ **US$ 14/mês**) roda **k3s** (Kubernetes
single-node) e recebe o overlay [`k8s/overlays/vm-k3s/`](../../k8s/overlays/vm-k3s/kustomization.yaml)
— que herda o overlay cloud inteiro: mesmos manifests, mesma ordem
(migração via Job antes do rollout), mesmas 4 superfícies públicas.

**Um único IP** (estático, recurso separado do Terraform — sobrevive a
eviction e à troca spot↔on-demand): UI `:8080`, API `:8000`, Jaeger `:16686`,
Prometheus `:9090`. O klipper-lb do k3s materializa os `Service LoadBalancer`
nessas portas; o NSG abre exatamente elas (+ SSH restrito ao IP do operador).
HPA funciona sem passo extra (o k3s embute o metrics-server).

## Uso

```bash
az login                    # conta Azure for Students
make vm-up                  # provisiona (spot) + k3s + deploy + seed + imprime IP/portas
make vm-url                 # (re)imprime acessos + ajusta CORS
make vm-seed                # repovoa dados de demo
make vm-down                # destrói tudo (RG + IP + disco) -> custo zero

make vm-up SPOT=false       # on-demand (~US$ 70/mês) p/ janela crítica — MESMO IP
```

`make vm-up` faz: Terraform (VM spot + IP estático + NSG + cloud-init k3s) →
espera SSH/k3s → exporta kubeconfig (`.kube-vm-config`, git-ignored) →
Secrets reais de `.env.cloud` → overlay `vm-k3s` → Job de migração →
deployment/relay/UI → CORS + seed. Chave SSH dedicada `.vm-demo-ssh`
(git-ignored, gerada no primeiro up).

## Subindo como membro do grupo

Qualquer integrante consegue subir/derrubar o ambiente do zero, desde que:

1. **Acesso à subscription** — o dono da conta Azure for Students concede
   uma vez: `az role assignment create --assignee RM<numero>@fiap.com.br
   --role Contributor --scope /subscriptions/<id-da-subscription>`.
2. **Toolchain local** — `az` (CLI), `terraform`, `kubectl`, `docker` e `uv`
   ([setup por plataforma](../../docs/setup/)).
3. **Segredos** — receber o `.env.cloud` do dono por canal seguro (nunca
   commitar; já está no `.gitignore`) e colocá-lo na raiz do repo. Sem ele o
   `vm-up` funciona igual, mas **gera credenciais novas** (`cloud-secrets.sh`
   é idempotente: reusa o arquivo se existir, cria se não) — aí as senhas
   divergem das documentadas para a banca.
4. `az login` com a conta FIAP → `make vm-up`.

Cuidados: o crédito é da subscription do dono (US$ 100, sem cartão);
`make vm-down` ao terminar testes fora da janela da banca. O IP muda a cada
`vm-down`+`vm-up` — atualizar o marcador `CLOUD-URL-FASE-2` no documento de
entrega quando o ambiente da banca for (re)erguido.

## Spot: eviction e religamento

- `max_bid_price = -1`: paga no máximo o preço on-demand ⇒ eviction **só por
  falta de capacidade** (rara em Dsv3/eastus), nunca por preço.
- `eviction_policy = Deallocate`: discos preservados — religou, k3s e dados voltam.
- **Religamento manual** (o IP estático não muda):
  `az vm start -g rg-pytstop-vm -n pytstop-vm`.
  Um workflow de religamento automático (`vm-watchdog`) existiu e foi
  **descomissionado em 2026-07-08**: exigia bootstrap OIDC adicional
  (federated credential escopada à main) que nunca foi concluído, e cada
  execução falhando a cada 30 min só poluía o Actions — para uma eviction
  rara que um comando resolve.

## Custo (preços reais consultados em 2026-07)

| Config | $/h | ~$/mês |
|---|---|---|
| D2s_v3 **spot** (default) | 0,0188 | **~14** |
| D2s_v3 on-demand (`SPOT=false`) | 0,096 | ~70 |
| + IP público estático | — | ~4 |

Regiões permitidas pela conta com oferta spot de D2s_v3: `eastus` (default),
`northcentralus` (mais barata, fallback: `make vm-up VM_LOCATION=northcentralus`),
`southcentralus`, `southafricanorth`. `brazilsouth` é vetado pela policy da
subscription; `chilecentral` não tem oferta spot deste SKU.

> [↑ Raiz do projeto](../../README.md) · [↑ infra/](../README.md)
