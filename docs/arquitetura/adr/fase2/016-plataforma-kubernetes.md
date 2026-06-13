# kind como plataforma Kubernetes da fase 2

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 exige manifests Kubernetes com Deployments, Services, ConfigMaps/Secrets e HPA por CPU/memória (RNF-020), provisionamento do cluster via Terraform — "local ou cloud" (RNF-021), pipeline CI/CD com deploy no cluster (RNF-022) e vídeo demonstrando a escalabilidade automática — ver [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md) e [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md). O RNF-023 acrescenta os pré-requisitos do HPA: probes, resource requests/limits e metrics-server ativo no cluster.

O material da fase aponta dois mundos: o Minikube como único ambiente local ensinado (Kubernetes, Aula 01) e o Amazon EKS como plataforma cloud de referência (Kubernetes-II, Aulas 04–09), incluindo o exemplo completo de provisionamento do EKS via Terraform (Terraform, Aula 08). O enunciado aceita explicitamente cluster "local ou cloud", e o gap analysis (§5, risco 3) propõe default local com cloud apenas se sobrar prazo, pedindo que a decisão seja tomada cedo porque ela molda os módulos Terraform.

Critérios de decisão, em ordem de peso:

1. **Custo zero ou mínimo** — projeto de estudante solo, sem orçamento para infraestrutura recorrente;
2. **Demo convincente de HPA no vídeo** — metrics-server funcional e réplicas escalando sob carga, no fluxo de validação ensinado: criar Deployment, criar HPA, gerar carga, observar `kubectl get hpa` (Kubernetes, Aula 08);
3. **Provisionável via Terraform** — o aceite do RNF-021 é `terraform apply` provisionando cluster + banco;
4. **Alcançável pelo pipeline CI/CD** — deploy executável no runner do GitHub Actions (RNF-022).

**Qual plataforma Kubernetes hospeda o deploy da fase 2 — e qual é o alvo de deploy do pipeline CI/CD?**

## Decisão

Adotar **kind** (Kubernetes in Docker) como plataforma única da fase 2 — desenvolvimento local, demo do vídeo e CI — com o cluster declarado como recurso Terraform.

- **Provisionamento**: o cluster kind é criado por `terraform apply` em `/infra`, usando o provider comunitário de kind do Terraform Registry (`tehcyx/kind`) com versão fixada em `required_providers`, prática obrigatória do material (Terraform, Aula 02). O mesmo código provisiona o cluster na máquina do desenvolvedor e no runner.
- **Alvo de deploy do CI**: o pipeline usa **cluster kind efêmero criado no próprio runner do GitHub Actions** a cada execução — `terraform apply` cria o cluster, o pipeline aplica os manifests e roda smoke test, e o cluster morre com o job. É deploy real (não simulado), sem infraestrutura persistente, sem conta cloud e sem segredo pessoal no repositório.
- **metrics-server**: instalado como parte do provisionamento — o kind não o traz por padrão e, em cluster local, ele exige o ajuste de TLS do kubelet — cumprindo o pré-requisito do HPA (RNF-023).
- **Demo de HPA**: no cluster kind local, seguindo o fluxo da disciplina (Kubernetes, Aula 08; reforçado com teste de carga em Kubernetes-II, Aula 06), com o harness `full-test/` promovido a gerador de carga (gap analysis, §4).

A evidência do material foi pesada e aponta para outras ferramentas — Minikube no local (Kubernetes, Aula 01), EKS na cloud (Kubernetes-II, Aula 04; Terraform, Aula 08). O que as aulas treinam e cobram, porém — kubectl, manifests YAML, Deployment, Service, ConfigMap, probes, HPA — é idêntico em qualquer distribuição conformante: a escolha da plataforma muda onde o cluster roda, não o conteúdo avaliado. Nos critérios de maior peso depois do custo, o kind entrega a mesma demo de HPA e vence com folga em Terraform e CI, como detalham as alternativas.

## Alternativas Consideradas

* kind
* Minikube
* k3d
* Cluster gerenciado em cloud (EKS/GKE/AKS)

### kind

Cluster Kubernetes dentro de containers Docker, projetado para testes locais e CI.

* Bom, porque custo zero e roda sobre o Docker já presente na stack desde a fase 1 (Dockerfile e docker-compose)
* Bom, porque o cluster vira um recurso declarativo do Terraform: um único `terraform apply` cobre o aceite do RNF-021, idêntico em dev e no CI
* Bom, porque é leve o bastante para nascer e morrer dentro do runner do GitHub Actions, dando ao RNF-022 um deploy real a cada pipeline sem cloud nem segredo
* Bom, porque o gap analysis já o apontava como default local (RNF-021 e risco 3)
* Ruim, porque não é a ferramenta ensinada — o ambiente local do material é o Minikube (Kubernetes, Aula 01)
* Ruim, porque o metrics-server exige instalação explícita com ajuste de TLS do kubelet, um passo a mais que o addon do Minikube
* Ruim, porque o provider Terraform é comunitário (não oficial CNCF/HashiCorp) — mitigado pela fixação de versão (Terraform, Aula 02) e pela superfície mínima do recurso (um cluster que exporta kubeconfig)

### Minikube

Cluster local de nó único usado nas aulas da disciplina.

* Bom, porque é o único ambiente local ensinado no material (Kubernetes, Aula 01) — alinhamento direto com o que a banca viu em aula
* Bom, porque o metrics-server é um addon de um comando — o caminho mais curto até a demo de HPA
* Ruim, porque o fluxo canônico é imperativo (`minikube start` — Kubernetes, Aula 01), não declarativo: encaixá-lo no aceite do RNF-021 (`terraform apply` provisiona o cluster) dependeria de provider comunitário de mantenedor único, fora de qualquer fluxo ensinado
* Ruim, porque no runner do CI é mais pesado que o kind e ficaria fora do fluxo Terraform — o IaC validado no pipeline não seria o mesmo aplicado localmente

### k3d

k3s (distribuição Kubernetes leve) dentro de containers Docker.

* Bom, porque custo zero, inicialização rápida e metrics-server já embutido por padrão (herdado do k3s)
* Bom, porque também roda sobre Docker em runner de CI
* Ruim, porque o suporte Terraform é o mais frágil das três opções locais — provider comunitário com baixa atividade de manutenção, arriscado para o entregável central do RNF-021
* Ruim, porque não aparece em nenhuma das três disciplinas — nenhuma evidência de material, somando curva de aprendizado sem contrapartida na avaliação

### Cluster gerenciado em cloud (EKS/GKE/AKS)

* Bom, porque é a plataforma de referência do material para produção: o EKS elimina a gestão do control plane (Kubernetes-II, Aula 04) e a disciplina de Terraform dedica a Aula 08 ao provisionamento completo (VPC + IAM + EKS + Node Group)
* Bom, porque daria um alvo persistente ao CI e Services LoadBalancer/Ingress reais (Kubernetes-II, Aula 05)
* Ruim, porque tem custo recorrente (control plane + nós worker) — falha o critério de maior peso; o gap analysis (risco 3) já restringia cloud a "se sobrar prazo"
* Ruim, porque exige conta cloud com billing pessoal e credenciais como segredos no CI
* Ruim, porque o ciclo de provisionamento e destruição do cluster é lento, alongando a iteração do pipeline e agravando o risco de prazo (gap analysis, risco 4)

## Consequências

### Positivas

* Custo zero de infraestrutura em toda a fase 2 — nada para desligar, nenhuma surpresa de billing
* IaC exercitada de verdade: o mesmo módulo Terraform que o avaliador executa localmente roda no pipeline a cada push — o RNF-021 é demonstrado, não apenas documentado
* Pipeline autossuficiente e reprodutível: cada execução parte de cluster limpo e valida `kubectl apply -f k8s/` do zero (aceite do RNF-020)
* O vídeo demonstra o HPA com o fluxo exato da disciplina (Kubernetes, Aula 08; Kubernetes-II, Aula 06), com `full-test/` gerando a carga

### Negativas

* O cluster efêmero do CI não demonstra operação continuada — rolling update sobre uma versão anterior viva e rollback (Kubernetes, Aula 05) só aparecem na demonstração local, não no pipeline
* Sem cloud, os tópicos gerenciados de Kubernetes-II (IAM, ECR, CloudWatch — Aulas 08–09) não são exercitados; RBAC continua demonstrável no próprio kind, se necessário
* metrics-server com TLS de kubelet relaxado é aceitável apenas em cluster local/efêmero — a configuração não é portável para produção real

### Neutras

* A decisão não fecha a porta para o EKS: manifests e HPA são portáveis, e o módulo Terraform do cluster isola o provider (estrutura `main.tf`/`variables.tf`/`outputs.tf` — Terraform, Aula 06); migrar é trocar o módulo, não o desenho
* Versões de kind/Kubernetes, estrutura dos módulos em `/infra`, configuração do runner e roteiro da demo ficam deferidos ao plano de execução da infraestrutura (fase de implementação), fora deste ADR

## Decisões Relacionadas

- [ADR-015](015-arquitetura-alvo-fase-2.md): Clean Architecture — a plataforma de orquestração é detalhe da borda (Frameworks & Drivers); nenhuma camada interna depende dela
- [ADR-017](017-provisionamento-banco.md): o banco é provisionado dentro deste mesmo cluster e no mesmo `terraform apply` — as duas decisões são acopladas
- [ADR-018](018-notificacao-email.md): o Mailpit entra no cluster como Deployment para a demo de notificação por e-mail

## Notas

* Fonte das evidências: fichamentos das disciplinas Kubernetes (Aulas 01–08), Kubernetes-II (Aulas 01–09) e Terraform (Aulas 01–09) da fase 2 (FIAP Pos Tech). As citações "(Disciplina, Aula NN)" referem-se ao material oficial
* Requisitos formais: RNF-020, RNF-021, RNF-022 e RNF-023 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md)); exigência original em [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md)
* "kind" é grafado em minúsculas pelo próprio projeto (Kubernetes in Docker)

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
