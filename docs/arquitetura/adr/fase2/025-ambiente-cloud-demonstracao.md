# Ambiente cloud de demonstração persistente (Azure for Students / AKS)

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-07-05

## Contexto e Problema

O [ADR-019](019-pipeline-cicd-deploy.md) decidiu o CD da fase 2 sobre um **cluster kind efêmero no runner** e, ao fazê-lo, avaliou e **rejeitou** explicitamente a alternativa "CD para cluster cloud persistente" por três motivos: custo recorrente, conta cloud pessoal e credenciais de longa duração como secrets no repositório. Aquela decisão está correta para o aceite do RNF-022 — deploy real, reprodutível, custo zero, sem segredo pessoal — e **permanece o CD canônico do projeto**: todo push na `main` provisiona, implanta e valida o sistema do zero.

Três fatos novos reabrem — de forma **aditiva**, não substitutiva — a alternativa cloud:

1. **Necessidade de URL pública para a banca.** O kind é `localhost` e efêmero: não há endereço que a banca avaliadora possa abrir durante a avaliação. O vídeo e o repositório cobrem o requisito formal, mas uma instância viva e navegável é um diferencial de demonstração que o kind, por construção, não entrega.
2. **Azure for Students remove o custo e o risco financeiro.** O e-mail institucional FIAP habilita o Azure for Students — US$ 100 de crédito **sem cartão de crédito**, renovável a cada ano re-verificando a matrícula (verificado em 2026-07). AKS tem **control plane gratuito** (paga-se só o node). Como a conta não tem cartão, quando o crédito acaba os recursos param — **não há como ser cobrado**. O "custo recorrente" e o risco financeiro que fundamentaram a rejeição do ADR-019 deixam de existir.
3. **OIDC federated credentials removem o segredo de longa duração.** O login do GitHub Actions no Azure passa a usar um _federated credential_ (OpenID Connect) escopado ao _environment_ `cloud` do repositório: o pipeline **assume uma identidade sem senha**, sem service principal estático guardado como secret. O terceiro "Ruim" do ADR-019 também cai.

Com os três motivos da rejeição endereçados, o problema é: **como oferecer uma URL pública de demonstração, com custo próximo de zero e sem credencial de longa duração, reusando o mesmo pipeline, as mesmas imagens e os mesmos manifests do kind — sem tocar no CD canônico que já cumpre o RNF-022?**

## Decisão

Adotar o **Azure Kubernetes Service (AKS) no _tier_ Free, provisionado por Terraform em `infra/azure/`, como ambiente cloud de demonstração OPCIONAL e ADITIVO ao kind** — mesmas imagens GHCR (por SHA), mesmos manifests de `k8s/` via _overlay_ kustomize, mesmo Job de migração antes do rollout ([ADR-019](019-pipeline-cicd-deploy.md); TD-015).

- **Aditivo, não substituto.** O kind efêmero ([ADR-016](016-plataforma-kubernetes.md)/[ADR-019](019-pipeline-cicd-deploy.md)) continua sendo o CD que satisfaz o RNF-022: roda em todo push, prova a reprodutibilidade do zero, custo zero. O AKS é **um alvo a mais**, disparado sob demanda (`workflow_dispatch` no CI ou `make cloud-up` local), nunca em todo push. O `infra/azure/` é um módulo Terraform **irmão** de `infra/`, que permanece intocado.

- **Config de custo mínimo.** Um único node `Standard_B2als_v2` (2 vCPU / 4 GB, burstável — o mais barato que roda o stack, que já cabe no kind com folga; upgrade para `Standard_B2ms` de 8 GB se algum pod for OOMKilled). **Exposição por `Service` type `LoadBalancer`** — quatro superfícies que a banca acessa por IP: **UI** (navegar o app), **API** (testar com Postman), **Jaeger** (traces) e **Prometheus** (métricas). Sem ingress/domínio/TLS: "dar acesso à banca" é passar os IPs (a relaxação de "não precisa ser público de verdade" permite bare-IP). Um AKS Standard já provisiona um Load Balancer para _egress_ por padrão (o pull das imagens do GHCR exige saída), então o custo-base do LB é **inerente** — os quatro `Service`s reusam esse mesmo LB, somando só os IPs públicos (~US$ 3,6/mês cada); NodePort **não** evitaria o LB de egress e ainda exigiria regra de NSG por porta. A API pública é segura por construção: `ENVIRONMENT=production` desliga o `/docs`, todo endpoint exige JWT e há rate limit; Jaeger/Prometheus expõem só dados fictícios de um backend efêmero. PVC do PostgreSQL descartável: o `terraform destroy` apaga o disco e o seed idempotente repõe os dados fictícios no próximo `apply`.

- **Janela de disponibilidade.** **Julho/2026: node 24/7** (~US$ 45–50 no mês, node + LB/IP) — a banca abre a URL a qualquer hora, sem janela a acertar. **A partir de agosto: ambiente destruído por padrão**, reerguível sob demanda em ~10 min (o deploy é 100% reproduzível), com custo residual de centavos (apenas o _storage account_ do estado do Terraform). Um _trilho de longa duração_ gratuito para sempre (Oracle Cloud Always Free + k3s ARM) fica registrado como evolução no plano ([issue #188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188)), fora do escopo desta entrega — os _overlays_ e o pipeline são os mesmos; muda só o provisionamento.

- **Risco financeiro zero.** Conta de estudante sem cartão: crédito esgotado ⇒ recursos param, nunca cobrança. Um _budget alert_ (50%/80% do crédito) serve de aviso, não de trava financeira — a trava é a própria natureza da conta.

- **Credenciais por OIDC, segredos por Environment.** O pipeline loga via _federated credential_ (GitHub Actions ↔ Microsoft Entra ID), sem senha estática. Os segredos reais de produção (`JWT_SECRET`, `ENCRYPTION_KEY`, `ADMIN_*`, `ORCAMENTO_WEBHOOK_TOKEN`) vivem no **GitHub Environment `cloud`** com _required reviewers_ (aprovação manual antes de qualquer deploy) e são materializados num `Secret` do Kubernetes na hora do deploy — nunca commitados. **Fallback documentado:** tenants de universidade frequentemente bloqueiam o registro de _app_ pelo aluno; se o `az ad app create` for negado, o deploy roda **localmente** via `make cloud-up` sob `az login` — o mesmo IaC, sem CI. O job de CD por OIDC é um bônus, não um pré-requisito da URL pública.

- **Produção de verdade ativa a guarda de segredos.** O _overlay_ cloud seta `ENVIRONMENT=production`, o que **ativa** o `validar_segredos_no_startup` (issue #74): o boot **aborta** se qualquer literal de demonstração vazar para o ambiente exposto, forçando os segredos fortes do Environment. Isso fecha, no alvo público, a porta que o ConfigMap do kind mantém aberta de propósito (`development`, com os literais de `secret.yaml` para a demo local).

- **Pré-requisitos de _go-live_ (antes de expor à internet).** O fix da [#180](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/180) (consulta pública de acompanhamento via POST — CPF/placa fora da URL) já está na `main`; o ambiente público roda **apenas dados fictícios** (seed de demonstração) com _banner_ deixando claro que é demo; NetworkPolicy _default-deny_ no namespace e `requirepass` no Redis entram como itens de _hardening_ do go-live.

## Alternativas Consideradas

* AKS Free tier + node único, aditivo ao kind
* Manter apenas o kind efêmero (status quo do ADR-019)
* Oracle Cloud Always Free (k3s single-node ARM)
* Cluster cloud sempre-ligado com LoadBalancer e TLS gerenciado

### AKS Free tier + node único, aditivo ao kind

* Bom, porque entrega URL pública reusando pipeline, imagens e manifests existentes — o _overlay_ kustomize é o único delta de deploy, e o Job de migração + a ordem de rollout são os mesmos do kind
* Bom, porque é Kubernetes **gerenciado de verdade** (control plane Free), o que conversa com o currículo da pós e com as fases seguintes melhor que um k3s self-managed
* Bom, porque a conta sem cartão dá **risco financeiro zero absoluto** — propriedade que nenhuma outra opção gerenciada tem
* Bom, porque os nodes são amd64: o GHCR já publica amd64, sem retrabalho de imagem multi-arch
* Ruim, porque depende de renovação anual do crédito de estudante — mitigado pelo trilho OCI de longa duração, já previsto
* Ruim, porque o registro de _app_ para OIDC pode ser barrado pelo tenant institucional — mitigado pelo fallback `make cloud-up` local

### Manter apenas o kind efêmero (status quo do ADR-019)

* Bom, porque é o que já cumpre o RNF-022 com custo zero e zero esforço adicional
* Ruim, porque não oferece URL pública alguma — a banca não tem instância viva para abrir, só o vídeo e o repositório

### Oracle Cloud Always Free (k3s single-node ARM)

* Bom, porque é **gratuito para sempre** (2 OCPU / 12 GB ARM) — o destino natural de um ambiente permanente de portfólio
* Ruim, porque é k3s self-managed (não gerenciado) e exige build **arm64** (buildx multi-arch), além de a capacidade ARM esgotar em regiões concorridas — fica como trilho de longa duração, não como alvo desta entrega

### Cluster cloud sempre-ligado com LoadBalancer e TLS gerenciado

* Bom, porque daria hostname estável e TLS automático — o cenário de produção real
* Ruim, porque o _sempre-ligado_ com hostname e TLS gerenciados consome o crédito continuamente (~2 meses só de node + LB) e agrega complexidade (cert-manager, DNS, ingress-nginx) que uma demo não exige; a janela de julho + destruição em agosto entregam o mesmo valor de avaliação a uma fração do custo

## Consequências

### Positivas

* URL pública de demonstração durante a avaliação, sem tocar no CD canônico do kind — o RNF-022 segue coberto pelo caminho de custo zero, e o cloud é um adendo
* Reuso máximo: mesmas imagens por SHA, mesmos manifests, mesmo Job de migração — o _overlay_ kustomize isola o pouco que difere (ENVIRONMENT, tipo dos `Service`s expostos, storage class, secrets reais)
* IaC preservado como requisito vivo (RNF-021): `infra/azure/` é `terraform apply`/`destroy` como o kind, e `make cloud-up`/`make cloud-down` espelham `k8s-up`/`k8s-down`
* Sem credencial de longa duração no repositório (OIDC) e sem segredo de demo no alvo público (guarda de startup em `production`)

### Negativas

* Depende de um benefício de estudante renovável anualmente; a permanência de longo prazo exige migrar para o trilho OCI (previsto, mesmo pipeline)
* Fora da janela de julho o ambiente é destruído: reabri-lo custa ~10 min de provisionamento — aceitável para demos agendadas, inadequado para uma vitrine sempre-no-ar (que seria o papel do trilho OCI)
* As quatro superfícies são expostas por IP público em HTTP, sem hostname estável nem TLS gerenciado (domínio + cert-manager ficam como evolução de go-live) — apropriado para demo com dados fictícios, não para produção

### Neutras

* O plano de execução detalhado (fases, estimativas, sequência de PRs) vive na [issue #188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188); este ADR fixa a decisão, não o passo a passo
* O trilho OCI (k3s ARM) e a promoção a hostname/TLS estáveis ficam como evolução, decididos quando/se um ambiente permanente for necessário
* O `infra/` do kind e os workflows `ci.yml`/`cd.yml` do RNF-022 permanecem como estão; `deploy-cloud` entra como job novo, opt-in por `workflow_dispatch`

## Decisões Relacionadas

- [ADR-019](019-pipeline-cicd-deploy.md): reabre — de forma aditiva — a alternativa "CD para cluster cloud persistente" que aquele ADR rejeitou, agora que custo, conta e credencial deixaram de ser impeditivos; o kind efêmero segue como CD canônico do RNF-022
- [ADR-016](016-plataforma-kubernetes.md): o AKS é o alvo cloud irmão do kind decidido lá — a plataforma Kubernetes passa a ter dois provisionamentos (kind local/CI, AKS demo pública)
- [ADR-017](017-provisionamento-banco.md): o PostgreSQL segue como StatefulSet in-cluster também no AKS, com PVC em _storage class_ gerenciada; a decisão de banco no cluster (paridade, sem dependência externa) é preservada
- [ADR-015](015-arquitetura-alvo-fase-2.md): o _overlay_ cloud é só configuração de deploy — não cruza nem afrouxa as camadas da Clean Architecture nem os contratos do import-linter

## Notas

* Plano de execução completo, estimativas de custo e sequência de PRs: [issue #188](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/188). Pré-requisitos de _go-live_: [#180](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/180) (fechada) e [#184](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/184) (gating do CD); a UI no cluster ([#186](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/186)) já entregue, herdada pelo overlay
* Este ambiente **não é exigido pelo enunciado** da fase 2 — o aceite (vídeo + repositório + IaC do kind) está coberto sem ele; é um diferencial de demonstração, e sua ausência não bloqueia a submissão
* Azure for Students e a elegibilidade do e-mail FIAP verificados em 2026-07; o crédito observado foi US$ 100 com validade de 365 dias e sem cartão

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
