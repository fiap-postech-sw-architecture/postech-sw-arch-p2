# PostgreSQL no cluster como StatefulSet provisionado pelo Terraform

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Proposta
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 exige scripts Terraform para o provisionamento do cluster Kubernetes **e do banco de dados**, com documentação dos recursos criados e de como aplicar — ver a seção de IaC do [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md). O RNF-021 do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) fixa o aceite: `terraform apply` provisiona cluster + banco, com README de `/infra` documentando recursos e ordem de aplicação. O pipeline (RNF-022) lista "deploy do banco de dados" como etapa própria, separada da aplicação dos manifests da aplicação.

Estado atual: o banco roda apenas via docker-compose (`postgres:16` com volume nomeado — `docker-compose.yml`) e via imagem seedada `db-image/` para o fast-check da banca (gap analysis, §4); o diretório `/infra` não existe. O [ADR-002](../002-banco-postgresql.md) fixou o PostgreSQL 16 como SGBD — este ADR não reabre a escolha do banco, decide apenas onde ele vive na fase 2 e como o Terraform o provisiona. O [ADR-016](016-plataforma-kubernetes.md) fixou o kind como plataforma (cluster local em dev/vídeo, efêmero no CI); a decisão do banco precisa ser coerente com esse alvo.

Critérios: persistência suficiente para a demo — o fichamento aponta a demonstração de dados sobrevivendo à reinicialização do Pod como o caso de uso canônico de volumes e provável item de avaliação (Kubernetes, Aula 06); simplicidade do Terraform exigido pelo challenge; paridade com o docker-compose local (RNF-019); e custo.

**Onde vive o PostgreSQL da fase 2 e como o Terraform o provisiona?**

## Decisão

Provisionar o **PostgreSQL 16 dentro do cluster, como StatefulSet com PVC**, com os recursos declarados pelo **provider `kubernetes` do Terraform** em `/infra` — providers são exatamente o mecanismo que traduz blocos HCL em chamadas de API de plataformas específicas, incluindo Kubernetes (Terraform, Aula 02). Tudo no mesmo fluxo `terraform apply` que cria o cluster kind (ADR-016), com o provider configurado a partir do kubeconfig que o recurso do cluster exporta.

- **Fronteira IaC × manifests**: o banco é infraestrutura-base e pertence ao Terraform (`/infra`) — StatefulSet, Service, volume e Secret de credenciais —, satisfazendo literalmente o RNF-021; a aplicação (Deployments, Services, ConfigMaps, Secrets e HPA do app) permanece em manifests YAML em `/k8s`, aplicados pelo pipeline (RNF-020/RNF-022). A divisão espelha o próprio challenge, que separa "deploy do banco de dados" de "aplicação dos manifestos YAML no cluster".
- **Persistência**: volume via PVC com modo `ReadWriteOnce` e a StorageClass padrão do kind, conforme o desenho de PV/PVC/StorageClass do material — que descarta `emptyDir` para dados de banco (Kubernetes, Aula 06). A demo de persistência (matar o Pod do banco e mostrar os dados intactos) segue o caso de uso canônico ensinado.
- **Padrão StatefulSet**: o material demonstra workload stateful no cluster exatamente assim — o Elasticsearch do stack EFK é um StatefulSet com `volumeClaimTemplates` e Service headless (Kubernetes-II, Aula 02); o PostgreSQL segue o mesmo padrão, com réplica única.
- **Paridade com o compose**: mesma imagem `postgres:16` do `docker-compose.yml` e mesmas variáveis `POSTGRES_*` (movidas para Secret no cluster); o compose continua sendo o caminho de desenvolvimento local rápido (RNF-019).
- **No CI**: o banco nasce e morre com o cluster efêmero do runner (ADR-016), populado por migrations/seed no pipeline — sem estado entre execuções.

## Alternativas Consideradas

* PostgreSQL como StatefulSet + PVC dentro do cluster
* Container externo ao cluster provisionado pelo Terraform
* Serviço gerenciado em cloud (RDS e equivalentes)

### PostgreSQL como StatefulSet + PVC dentro do cluster

* Bom, porque um único `terraform apply` entrega cluster + banco — o aceite do RNF-021 sem segunda ferramenta nem sequência manual de operações
* Bom, porque realiza o caso de uso canônico de volumes do material: PVC `ReadWriteOnce` para banco, persistência independente do ciclo de vida do Pod (Kubernetes, Aula 06)
* Bom, porque segue o padrão stateful ensinado — StatefulSet com `volumeClaimTemplates` (Kubernetes-II, Aula 02)
* Bom, porque custo zero e coerência total com o ADR-016: tudo dentro do mesmo cluster local/efêmero
* Ruim, porque a durabilidade é a do cluster: o PV da StorageClass padrão do kind vive nos containers do nó — suficiente para a demo, inadequado para produção real
* Ruim, porque operar banco em Kubernetes sem operator é artesanal: backup, upgrade e replicação ficam fora do escopo — aceitável no contexto de demonstração acadêmica

### Container externo ao cluster provisionado pelo Terraform

PostgreSQL como container Docker fora do cluster, criado por `terraform apply` (provider `docker`), alcançado pelos Pods via rede.

* Bom, porque paridade máxima com o docker-compose — literalmente o mesmo container do ambiente de dev
* Bom, porque o banco sobreviveria à recriação do cluster local
* Ruim, porque exige costura de rede entre o cluster kind e um container externo (conectar redes Docker, resolver o endereço do host) que nenhuma aula cobre e que fragiliza o job no runner do CI
* Ruim, porque abre mão de PV/PVC/StorageClass — perde o sinal de avaliação central da disciplina, que trata a persistência de banco como o caso de uso canônico de volumes (Kubernetes, Aula 06)
* Ruim, porque cria dois ciclos de vida (cluster e banco) para o pipeline orquestrar

### Serviço gerenciado em cloud (RDS e equivalentes)

* Bom, porque terceiriza durabilidade, backup e upgrade — e é o destino que o arco AWS do material sugere quando o alvo é cloud (Kubernetes-II, Aulas 04–09; o fichamento de Terraform aponta RDS como o caminho natural nesse cenário)
* Ruim, porque custo recorrente e conta cloud com billing pessoal — o mesmo critério que eliminou o cluster gerenciado no ADR-016
* Ruim, porque é incoerente com o cluster local: a aplicação no kind alcançando um RDS atravessaria a internet, exigindo configuração de rede e segurança fora do escopo e somando latência à demo
* Ruim, porque o CI efêmero ganharia uma dependência externa persistente, com segredo pessoal no repositório

## Consequências

### Positivas

* `terraform apply` único sobe cluster + banco e `terraform destroy` desmonta tudo — o ciclo completo do material (Terraform, Aula 03) demonstrável no vídeo
* A demo de persistência apontada pelo fichamento (dados após reinicialização do Pod — Kubernetes, Aula 06) fica trivial: `kubectl delete pod` do banco e nova consulta
* Zero custo e zero segredo pessoal, em linha com o ADR-016
* Paridade de imagem e variáveis entre compose e cluster reduz drift de configuração entre dev e demo

### Negativas

* Banco autogerido em cluster local/efêmero: sem backup, alta disponibilidade ou tuning — limitação aceita e documentada; produção real exigiria operator ou serviço gerenciado
* Réplica única: reinício do Pod do banco gera indisponibilidade breve — irrelevante para a demo, inaceitável em produção
* Configurar o provider `kubernetes` a partir do kubeconfig gerado no mesmo apply cria encadeamento sensível à ordem de inicialização dos providers; se travar, a mitigação padrão é separar cluster e banco em módulos/applies sequenciais, documentados no README de `/infra`

### Neutras

* Dimensionamento do volume, resources do Pod do banco, política de seed (migrations no pipeline vs imagem seedada) e valores de Secret ficam deferidos ao plano de execução da infraestrutura (fase de implementação), fora deste ADR
* `db-image/` permanece com escopo reduzido, para o fast-check local da banca (gap analysis, §4) — o caminho oficial de deploy do banco passa a ser o Terraform

## Decisões Relacionadas

- [ADR-002](../002-banco-postgresql.md): PostgreSQL 16 como banco — mantido; este ADR decide provisionamento, não SGBD
- [ADR-015](015-arquitetura-alvo-fase-2.md): o banco permanece detalhe de Frameworks & Drivers — a aplicação o alcança pela mesma `DATABASE_URL`, indiferente a onde ele roda
- [ADR-016](016-plataforma-kubernetes.md): plataforma kind — o banco vive no cluster decidido lá; mudar aquela decisão reabre esta

## Notas

* Fonte das evidências: fichamentos das disciplinas Kubernetes (Aula 06), Kubernetes-II (Aula 02) e Terraform (Aulas 02 e 03) da fase 2 (FIAP Pos Tech). As citações "(Disciplina, Aula NN)" referem-se ao material oficial
* Requisito formal: RNF-021 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md)); exigência original na seção "Infraestrutura como Código (IaC)" do [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md)
* O fichamento de Terraform registra que o material não cobre banco local provisionado via Terraform (o arco da disciplina é AWS/RDS); o provider `kubernetes` preenche essa lacuna mantendo o requisito literal — é o Terraform que provisiona o banco

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
