# Pipeline de CI/CD com deploy em cluster kind efêmero no runner

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-06-10

## Contexto e Problema

O Tech Challenge da fase 2 exige pipeline de CI/CD que execute build da aplicação, testes automatizados, build da imagem Docker, deploy no cluster Kubernetes, deploy do banco de dados e aplicação dos manifests YAML — ver a seção de CI/CD do [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md). O RNF-022 do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md) fixa o aceite: push na branch principal produz imagem versionada e aplica os manifests no cluster alvo; falha de teste bloqueia o deploy.

A fase 1 deixou quatro workflows em `.github/workflows/`:

- **`ci.yml`** — lint (ruff), type-check (mypy), análise de segurança (bandit — [ADR-011](../011-pipeline-seguranca-analise-estatica.md)) e testes unitários + integração com PostgreSQL como service container, com gate de cobertura; gatilhos `push` e `pull_request`, o par canônico do material (GitHub Actions, Aula 02);
- **`full-test-ci.yml`** — E2E: sobe a stack completa via docker compose (build ad-hoc das imagens, sem publicação), aguarda saúde, semeia dados e roda o plano concorrente do harness `full-test/`; gatilhos PR e push na main, manual e nightly;
- **`claude-code-review.yml`** e **`claude-on-demand.yml`** — revisão automatizada de PRs; apoiam o processo, fora do ciclo build→deploy deste ADR.

O diagnóstico do RNF-022 é direto: CI madura, CD inexistente — nenhum workflow publica imagem versionada nem executa deploy. O alvo do deploy, porém, já está decidido: cluster kind efêmero criado no próprio runner do GitHub Actions — `terraform apply` cria cluster e banco, o pipeline aplica os manifests e roda smoke test, e o cluster morre com o job ([ADR-016](016-plataforma-kubernetes.md), [ADR-017](017-provisionamento-banco.md)).

Critérios: cumprir o aceite do RNF-022 com deploy real — o fluxo manual de integração, build, verificação e implantação é "propenso a erros" e deve ser automatizado (DevOps, Aula 01), e o vídeo da entrega exige demonstrar a execução do CI/CD; zero segredo pessoal e custo zero, em linha com os ADRs 016–018; e menor delta — os workflows herdados são estendidos, não recriados.

**Como o pipeline herdado se estende para cumprir o ciclo build → testes → imagem → deploy do RNF-022 — e como a imagem chega ao cluster?**

## Decisão

Estender o pipeline com um **estágio de CD disparado por push na main: build e push da imagem da aplicação no GHCR, deploy em cluster kind efêmero no runner e smoke test** — encadeado após os estágios de CI herdados.

- **Mapeamento dos estágios do challenge sobre o que existe**: build da aplicação (verificação do lockfile e `uv sync` — já existe no `ci.yml`) e testes automatizados (unitários e integração no `ci.yml`, E2E no `full-test-ci.yml`) permanecem como estão; build da imagem Docker (hoje apenas ad-hoc no compose do E2E) e deploy (inexistente) são os jobs novos. Os jobs novos declaram dependência dos estágios de build e teste via `needs` — o padrão de job de deploy dependente do job de build demonstrado pelo material (GitHub Actions, Aula 02); como `needs` só encadeia jobs do mesmo workflow, a acomodação dos jobs nos arquivos fica para o plano. O efeito exigido não muda: falha em qualquer estágio anterior bloqueia o deploy, como pede o aceite e como o material cobra de uma CI eficiente (DevOps, Aula 03).
- **Alvo e natureza do deploy**: o job de CD executa `terraform apply` (cria o cluster kind e o banco StatefulSet — ADR-016/ADR-017), aplica os manifests de `/k8s` com `kubectl apply` (app, ConfigMap/Secret, Mailpit, HPA) e roda smoke test; ao final, o cluster morre com o job. **Este é o deploy demonstrável do challenge**: cada push na main provisiona, implanta e valida o sistema do zero, sem infraestrutura persistente. O mesmo fluxo roda localmente via alvos `make` que envolvem os mesmos comandos — o pipeline executa o que o desenvolvedor executa (DevOps, Aula 03); no vídeo, o deploy é gravado nesse fluxo local e a execução do CI/CD é mostrada na própria interface do GitHub Actions.
- **Imagem**: publicada no **GHCR com tag imutável por SHA do commit** — o aceite pede imagem versionada. O GHCR já é o registry do projeto desde a fase 1, e o push usa o `GITHUB_TOKEN` do próprio job. O material cataloga o Docker Hub e os registries integrados a ecossistemas como alternativas equivalentes (GitHub Actions, Aula 05); o GHCR é o representante nativo do GitHub nessa categoria.
- **Como o kind consome a imagem**: por **`kind load`** da imagem recém-construída, não por pull do GHCR. O repositório é privado (exigência FIAP), então o pull exigiria `imagePullSecret` no cluster — no runner ele até poderia ser montado com o próprio `GITHUB_TOKEN`, mas o mesmo fluxo rodando localmente passaria a exigir PAT pessoal, exatamente o tipo de segredo que o ADR-016 eliminou; `kind load` injeta nos nós a mesma imagem (mesmo SHA) recém-publicada, sem credencial nenhuma, e mantém CI e deploy local idênticos.
- **Credenciais**: somente o `GITHUB_TOKEN` efêmero do job, com permissão de escrita em packages para o push — nenhuma credencial em texto plano no workflow (GitHub Actions, Aula 02) e nenhum kubeconfig externo: o cluster nasce no runner e o kubeconfig sai do `terraform apply`. ConfigMap e Secret da aplicação são aplicados via manifests com valores de demonstração, como o CI atual já faz com as variáveis de teste.
- **Migrações no deploy**: por **Job dedicado pós-apply, antes do rollout** (TD-015). O `entrypoint.sh` ainda executa `alembic upgrade head` no boot quando `RUN_MIGRATIONS_ON_STARTUP=true` — caminho que o `full-test-ci.yml` exercita no compose (container único, sem corrida) —, mas **no cluster a variável entra como `false`** pelo ConfigMap: a migração roda no Job `pytstop-migrate` ([`k8s/jobs/migration-job.yaml`](../../../../k8s/jobs/migration-job.yaml)), aplicado com a tag do SHA depois do `kubectl apply -f k8s/` e antes do `set image`/rollout, com `kubectl wait --for=condition=complete` como gate. Isso elimina a janela de corrida quando N réplicas sobem juntas — o schema já está em head quando os pods da API partem. O initContainer foi descartado por duplicar a lógica do entrypoint em cada pod; o Job migra uma única vez. A versão inicial deste ADR adotou a migração no entrypoint pelo menor delta, com o Job como evolução prevista — corrida materializada e endereçada (ver consequências).
- **Gatilhos**: PR mantém apenas a CI herdada (gate de merge); push na main dispara o ciclo completo com CD; `workflow_dispatch` permite reexecutar o deploy sob demanda — em particular para a gravação do vídeo.

## Alternativas Consideradas

* CD para cluster kind efêmero no runner
* CD para cluster cloud persistente
* Sem CD real — deploy manual documentado

### CD para cluster kind efêmero no runner

* Bom, porque é deploy real a cada push na main — provisiona, implanta e valida do zero — cumprindo o aceite do RNF-022 sem infraestrutura persistente, sem conta cloud e sem segredo pessoal
* Bom, porque materializa a entrega contínua do material: todo artefato validado permanentemente pronto para implantação, sem etapas manuais (GitHub Actions, Aula 01; DevOps, Aula 01)
* Bom, porque é o menor delta: a CI herdada permanece intacta e o CD entra como jobs encadeados, reusando o Terraform e os manifests dos ADRs 016/017
* Ruim, porque o ambiente morre com o job: não existe URL persistente pós-pipeline — a inspeção pós-deploy acontece no cluster local do vídeo, não no do CI
* Ruim, porque não exercita rolling update sobre versão anterior viva — limitação já registrada no ADR-016

### CD para cluster cloud persistente

* Bom, porque daria deploy contínuo a um ambiente estável com URL pública — o cenário de produção real
* Bom, porque exercitaria rolling update e rollback sobre versão viva no próprio pipeline
* Ruim, porque reabre o que o ADR-016 já decidiu, pelos mesmos motivos: custo recorrente, conta cloud pessoal e credenciais de longa duração como secrets no repositório
* Ruim, porque o ciclo provisiona/destrói em cloud é lento e alonga cada execução do pipeline, agravando o risco de prazo (gap analysis, risco 4)

### Sem CD real — deploy manual documentado

* Bom, porque é o esforço mínimo de pipeline — apenas documentação e alvos make para o deploy local
* Ruim, porque não cumpre o aceite do RNF-022: push na main não produziria imagem versionada nem aplicaria manifests — gap direto num requisito obrigatório
* Ruim, porque contradiz o núcleo do material da fase: a automação existe para eliminar o fluxo manual propenso a erros e o desenvolvedor como gargalo (DevOps, Aula 01)

## Consequências

### Positivas

* RNF-022 coberto de ponta a ponta com deploy real e reprodutível; o vídeo demonstra a execução do CI/CD com o pipeline verde
* Imagem versionada por SHA no GHCR: cada deploy é rastreável ao commit que o gerou, e o artefato testado é o artefato implantado — a paridade entre ambientes que motiva o uso de containers (GitHub Actions, Aula 04)
* Zero segredo novo: o `GITHUB_TOKEN` do job cobre o GHCR, e o cluster nasce sem kubeconfig externo
* Fluxo local e CI idênticos (mesmo Terraform, mesmos manifests, mesmos comandos via make) — depurar o pipeline não depende do runner

### Negativas

* O tempo de pipeline na main cresce: build de imagem + provisionamento do cluster + deploy + smoke test a cada push — mitigável com cache de dependências e de camadas (GitHub Actions, Aula 02), mas nunca zero
* A migração roda num Job dedicado (`pytstop-migrate`) antes do rollout, não mais no entrypoint do pod no cluster (TD-015): `kubectl wait --for=condition=complete` garante o schema em head antes de qualquer réplica subir, eliminando a janela de corrida entre migrações concorrentes — N réplicas podem partir juntas com segurança. O entrypoint mantém o caminho gated (`RUN_MIGRATIONS_ON_STARTUP`) só para o compose, onde o container é único
* O smoke test contra cluster recém-nascido valida o caminho feliz do deploy, não a operação continuada — rolling update e rollback ficam para a demonstração local (herança do ADR-016)

### Neutras

* Layout exato dos arquivos de workflow, versões fixadas das actions, estratégia de tags adicionais (ex.: `latest`), cache de build e o conteúdo detalhado do smoke test ficam deferidos ao plano de execução da infraestrutura (fase de implementação), fora deste ADR
* `claude-code-review.yml` e `claude-on-demand.yml` permanecem intocados
* O `full-test-ci.yml` continua como gate E2E baseado em compose; a promoção do harness a smoke test do cluster (gap analysis, §4) é evolução prevista, decidida no plano

## Decisões Relacionadas

- [ADR-011](../011-pipeline-seguranca-analise-estatica.md): a análise de segurança herdada (bandit) permanece entre os estágios que bloqueiam o deploy
- [ADR-015](015-arquitetura-alvo-fase-2.md): o gate de testes que protege a refatoração (RNF-018) é o mesmo que bloqueia o deploy — pipeline e refatoração compartilham a rede de segurança
- [ADR-016](016-plataforma-kubernetes.md): o alvo do deploy é o cluster kind efêmero decidido lá; este ADR realiza o estágio de CD daquele desenho
- [ADR-017](017-provisionamento-banco.md): o "deploy do banco de dados" exigido pelo challenge é o `terraform apply` do StatefulSet, executado pelo job de CD antes dos manifests do app
- [ADR-018](018-notificacao-email.md): o Mailpit entra no cluster pelos mesmos manifests que o job de CD aplica

## Notas

* Fonte das evidências: fichamentos das disciplinas GitHub Actions (Aulas 01, 02, 04 e 05) e DevOps (Aulas 01 e 03) da fase 2 (FIAP Pos Tech). As citações "(Disciplina, Aula NN)" referem-se ao material oficial
* Requisito formal: RNF-022 ([gap-analysis-fase-2.md](../../../requisitos/fase2/gap-analysis-fase-2.md)); exigência original na seção "Integração Contínua/Entrega Contínua (CI/CD)" do [desafio-tech-fase-2.md](../../../requisitos/fase2/desafio-tech-fase-2.md)
* O material não cita o GHCR nominalmente — o catálogo da Aula 05 cobre Docker Hub, GCR, ECR, ACR, GitLab Container Registry, Quay e JFrog; o GHCR ocupa no GitHub o mesmo papel que o GitLab Container Registry ocupa no GitLab, e o projeto já o usa desde a fase 1
* A alternativa "CD para cluster cloud persistente", rejeitada aqui por custo, conta pessoal e credencial de longa duração, foi **revisitada de forma aditiva** no [ADR-025](025-ambiente-cloud-demonstracao.md) — Azure for Students (sem cartão) e OIDC federado derrubam os três impeditivos, e o AKS entra como alvo opcional de demonstração pública sem substituir o kind efêmero deste ADR

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
