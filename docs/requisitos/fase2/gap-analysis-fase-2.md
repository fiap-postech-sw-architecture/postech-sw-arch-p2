# Gap Analysis — Tech Challenge Fase 2 × Código da Fase 1

> [↑ Raiz do projeto](../../../README.md) · [↑ Requisitos](../README.md)

> Origem dos requisitos: [desafio-tech-fase-2.md](desafio-tech-fase-2.md). IDs continuam a numeração
> da fase 1 (últimos: RF-019, RNF-016, RN-017 — ver [requisitos.md](../requisitos.md)).

## 1. Tabela de gaps

| ID | Requisito (challenge) | Estado no p1 (evidência file:line) | Gap | Ação na fase 2 |
|----|----------------------|-------------------------------------|-----|----------------|
| RNF-017 | Refatorar aplicando Clean Code + Clean Architecture ou Arquitetura Hexagonal | Cada contexto já segue camadas `dominio/aplicacao/infraestrutura/interfaces` com Ports e UnitOfWork (`src/ordem_servico/aplicacao/use_cases.py:1-14,47-51`; queries cross-context via Ports em `src/ordem_servico/aplicacao/queries.py:36-64`) | Parcial: estrutura já é ports & adapters, mas falta decisão formal Clean vs Hexagonal e auditoria de conformidade | ADR escolhendo a abordagem, auditoria de dependências entre camadas, refatorações pontuais — IMPLEMENTADO (PR #12) |
| RNF-018 | Testes automatizados (unitários e/ou integração) nos fluxos críticos | Gate de cobertura 95% (`.coveragerc:29`); CI roda unitários + integração com Postgres de serviço (`.github/workflows/ci.yml:63-121`); harness E2E separado (`full-test/README.md:5-7`) | Nenhum gap estrutural; novos fluxos da fase 2 ainda sem testes | Manter gate na refatoração; cobrir listagem ordenada, endpoint externo de orçamento e notificação por e-mail — IMPLEMENTADO (transversal: gate de 95% mantido nos PRs #12–#22) |
| RF-020 | Abertura de OS recebendo cliente, veículo, serviços e peças, retornando identificação única | `POST /api/v1/ordens-de-servico/` aceita apenas `cliente_id` + `veiculo_id` (`src/ordem_servico/interfaces/router.py:86-101`; `src/ordem_servico/aplicacao/use_cases.py:142-168`); itens entram depois via `POST /{ordem_id}/itens` (`router.py:163-184`); ID único UUID já existe (`src/compartilhado/dominio/entity.py:9`) | Payload de criação não aceita serviços/peças | Estender `CriarOrdemDTO`/`CriarOrdemRequest` com itens opcionais e compor criação + itens na mesma transação — IMPLEMENTADO (PR #15) |
| RF-021 | Consulta de status da OS (Recebida, Diagnóstico, Aguardando Aprovação, Execução, Finalizada, Entregue) | `GET /{ordem_id}` autenticado (`src/ordem_servico/interfaces/router.py:145-160`) e consulta pública por placa + documento (`src/compartilhado/interfaces/router_publico.py:41-86`; `src/ordem_servico/aplicacao/use_cases.py:539-555`) | Parcial: endpoints existem, mas expõem o enum de 8 estados em snake_case (`src/ordem_servico/dominio/status.py:15-22`), não os 6 rótulos do challenge | Manter endpoints; mapear rótulos de exibição para o vocabulário do challenge (ver §2) — IMPLEMENTADO (PR #14) |
| RF-022 | Aprovação de orçamento: endpoint para notificações **externas** de aprovação ou recusa | Aprovação é interna, admin-only via JWT (`src/ordem_servico/interfaces/router.py:240-253`; `use_cases.py:310-343`); não existe recusa do orçamento inicial — só cancelamento (`router.py:288-302`) e rejeição do complementar (`router.py:337-350`) | Total para o canal externo; recusa do orçamento inicial inexistente | Novo endpoint externo (token próprio via Secret K8s) cobrindo aprovação e recusa; nova transição de recusa na `MaquinaDeStatus` (`maquina_de_status.py:33-38`) — IMPLEMENTADO (PR #16) |
| RF-023 | Listagem ordenada por status (Em Execução > Aguardando Aprovação > Diagnóstico > Recebida), mais antigas primeiro, excluindo finalizadas/entregues (lógica, não física) | Listagem pagina por `criado_em DESC, id` sem filtro de status (`src/ordem_servico/infraestrutura/repository.py:68-77`; `use_cases.py:513-516`; `router.py:104-127` só aceita `offset`/`limit`) | Total na ordenação por prioridade e na exclusão lógica | Ordenação SQL por prioridade de status + `criado_em ASC`; filtro padrão excluindo `FINALIZADA`/`ENTREGUE` (RN-018, RN-019, RN-020) — IMPLEMENTADO (PR #13) |
| RF-024 | Atualização de status da OS via alguma ferramenta como e-mail | Nenhum SMTP/envio de e-mail no backend (grep `email\|smtp` em `src/` só encontra credencial de login, ex.: `src/autenticacao/aplicacao/use_cases.py:35-58`); RN-014 da fase 1 adiou e-mail explicitamente (`docs/requisitos/requisitos.md:76`); dispatch de eventos de domínio ficou deferido (`src/ordem_servico/aplicacao/use_cases.py:10-13`) | Total | `NotificacaoPort` + adapter de e-mail disparado nas transições de status; credenciais via Secret K8s — IMPLEMENTADO (PR #17) |
| RNF-019 | Docker: Dockerfile atualizado + docker-compose para desenvolvimento local | Dockerfile multi-stage com uv (`Dockerfile:1-57`); compose com `app` + `postgres` + `ui` (`docker-compose.yml:1-69`), healthcheck só no postgres (`docker-compose.yml:46-50`) | Pequeno: revisão para a fase 2 (healthcheck do app, imagem alvo do deploy K8s) | Revisar Dockerfile/compose; adicionar healthcheck do serviço `app` — IMPLEMENTADO (PR #18) |
| RNF-020 | Manifestos K8s: Deployments, Services, ConfigMaps/Secrets, HPA por CPU/memória | Diretório `k8s/` inexistente (`ls k8s` falha); única preparação é o health probe `GET /api/v1/saude` (`src/compartilhado/interfaces/router_publico.py:35-38`) | Total | Criar `/k8s` com Deployment, Service, ConfigMap, Secret e HPA; probes e resources conforme RNF-023 — IMPLEMENTADO (PR #19) |
| RNF-021 | Terraform para provisionar cluster K8s (local ou cloud) + banco de dados, documentado | Diretório `infra/` inexistente (`ls infra` falha) | Total | Criar `/infra` com módulos de cluster e banco + documentação de recursos e de aplicação — IMPLEMENTADO (PR #20) |
| RNF-022 | CI/CD: build, testes, build de imagem Docker, deploy no cluster, deploy do banco, aplicação dos manifests | CI cobre lint, type-check, bandit e testes com cobertura (`.github/workflows/ci.yml:17-127`); o E2E builda imagens apenas ad-hoc via compose (`.github/workflows/full-test-ci.yml:57`); nenhum workflow publica imagem em registry nem executa deploy | Parcial: CI maduro, CD inexistente | Adicionar jobs de build/push de imagem (GHCR) e deploy (manifests K8s + banco) condicionados à branch principal — IMPLEMENTADO (PR #21) |
| RNF-023 | HPA-readiness: liveness/readiness probes e resource requests/limits no Deployment | Endpoint de saúde pronto (`src/compartilhado/interfaces/router_publico.py:35-38`); sem manifests, logo sem probes nem resources | Total | Probes apontando para `GET /api/v1/saude`; requests/limits iniciais via medição de carga local (reusar `full-test/`); metrics-server ativo no cluster — IMPLEMENTADO (PR #19) |
| RNF-024 | Statelessness para escala horizontal: comportamento correto com N réplicas | JWT stateless com denylist compartilhada no Postgres (`src/autenticacao/interfaces/middleware.py:39-47`); rate limiter slowapi in-memory por processo (`src/compartilhado/interfaces/middleware.py:87`); pool SQLAlchemy com defaults sem dimensionamento (`src/compartilhado/infraestrutura/database.py:16`) | Parcial: rate limiter diverge entre réplicas; pool não dimensionado | Storage compartilhado do rate limiter (ex.: Redis) ou documentar limite por-réplica; configurar `pool_size`/`max_overflow`/`pool_pre_ping` validando `max_connections` no pior caso do HPA — PARCIAL: limite do rate limiter documentado como por-réplica ([TD-016](../../tech-debt.md)); pool segue nos defaults do SQLAlchemy |

## 2. Modelo de status

O challenge cita 6 situações: Recebida, Em diagnóstico, Aguardando aprovação, Em execução, Finalizada, Entregue. O p1 tem **8 estados** em `src/ordem_servico/dominio/status.py:15-22`: os 6 acima mais `CANCELADA` e `AGUARDANDO_APROVACAO_COMPLEMENTAR`. As transições são allow-list em `src/ordem_servico/dominio/maquina_de_status.py:20-59` (`CANCELADA` alcançável de qualquer estado ativo; `AGUARDANDO_APROVACAO_COMPLEMENTAR` é ida-e-volta de `EM_EXECUCAO`).

**Decisão proposta: manter os 8 estados.** Os 2 extras realizam requisitos de negócio da fase 1 que continuam válidos (cancelamento: RN-002/RN-003 — `docs/requisitos/requisitos.md:142`; orçamento complementar: RF-016 — `requisitos.md:201` — e RN-015 — `requisitos.md:77`), e o challenge não proíbe estados adicionais — exige apenas que a consulta informe a situação atual e que a listagem siga a ordenação dos 4 estados ativos.

Impactos:

- **Listagem ordenada**: a regra do challenge só ordena 4 estados. Destino dos extras (proposta, a ratificar em ADR): `AGUARDANDO_APROVACAO_COMPLEMENTAR` ordena junto de `AGUARDANDO_APROVACAO` (mesma semântica de espera de aprovação); `CANCELADA` é excluída da listagem padrão junto com `FINALIZADA`/`ENTREGUE`, por ser estado encerrado (RN-020).
- **Migração de dados**: mantendo os valores persistidos em snake_case (`status.py:12` documenta que os valores existem para persistência), **nenhuma migração é necessária**. Renomear valores (ex.: `em_diagnostico` → `diagnostico`) exigiria migration Alembic de dados + atualização de consumidores; a recomendação é não renomear e tratar os rótulos do challenge na camada de apresentação (RF-021).

## 3. Requisitos novos detalhados

### RF-020 — Abertura de OS com dados completos

- **Descrição**: a criação da OS recebe cliente, veículo e, opcionalmente, serviços e peças numa única chamada, retornando a identificação única da OS.
- **Critério de aceite**: `POST /api/v1/ordens-de-servico/` com itens no payload cria a OS já com itens na mesma transação e responde 201 com `id`; payload sem itens continua funcionando (compatibilidade fase 1).
- **Estado atual**: criação só com `cliente_id`/`veiculo_id` (`src/ordem_servico/interfaces/router.py:86-101`; `use_cases.py:142-168`); itens via endpoint separado (`router.py:163-184`); UUID gerado no agregado (`src/compartilhado/dominio/entity.py:9`; `ordem_de_servico.py:102`).
- **Mudança**: estender DTO/Request de criação com lista opcional de itens e orquestrar `CriarOrdem` + adição de itens sob a mesma UnitOfWork.

### RF-021 — Consulta de status no vocabulário do challenge

- **Descrição**: a consulta de status informa a situação atual usando os rótulos do challenge.
- **Critério de aceite**: consulta autenticada e consulta pública retornam o status atual; documentação OpenAPI lista os rótulos esperados.
- **Estado atual**: `GET /{ordem_id}` (`router.py:145-160`) e `GET /api/v1/acompanhamento` público com rate limit (`src/compartilhado/interfaces/router_publico.py:41-86`) retornam `status` snake_case do enum de 8 valores (`use_cases.py:551-555`; `status.py:15-22`).
- **Mudança**: mapear rótulos de exibição (sem renomear valores persistidos — ver §2); manter os dois canais de consulta.

### RF-022 — Aprovação/recusa externa de orçamento

- **Descrição**: endpoint que recebe notificações externas (cliente) de aprovação **ou recusa** do orçamento.
- **Critério de aceite**: chamada externa autenticada por credencial própria (não JWT de admin) aprova ou recusa a OS em `AGUARDANDO_APROVACAO`; recusa leva a OS a um estado terminal ou de retrabalho definido em ADR; tentativas em estado inválido retornam 409/422.
- **Estado atual**: `POST /{ordem_id}/aprovacao` é admin-only (`router.py:240-253`); `AprovarOrcamento` reserva estoque e transita para `EM_EXECUCAO` (`use_cases.py:310-343`); não há recusa do orçamento inicial — `AGUARDANDO_APROVACAO` só transita para `EM_EXECUCAO` ou `CANCELADA` (`maquina_de_status.py:33-38`).
- **Mudança**: novo endpoint externo (token em Secret K8s, fora do RBAC interno), caso de uso de recusa (provável reuso da transição para `CANCELADA` com motivo, a decidir em ADR) e auditoria da origem da decisão.

### RF-023 — Listagem ordenada por prioridade de status

- **Descrição**: listagem ordena por Em execução > Aguardando aprovação > Em diagnóstico > Recebida, mais antigas primeiro, sem OS finalizadas/entregues (exclusão lógica).
- **Critério de aceite**: resposta da listagem padrão segue RN-018/RN-019/RN-020; paginação continua determinística; nenhuma linha é apagada fisicamente.
- **Estado atual**: `order_by(criado_em DESC, id)` sem filtro (`src/ordem_servico/infraestrutura/repository.py:68-77`); use case repassa sem ordenação própria (`use_cases.py:513-516`); router só expõe `offset`/`limit` (`router.py:104-127`).
- **Mudança**: ordenação SQL por prioridade (CASE no status) + `criado_em ASC` + desempate por `id`; filtro padrão excluindo estados encerrados; avaliar parâmetro opt-in para visão completa (admin).

### RF-024 — Notificação de atualização de status por e-mail

- **Descrição**: a cada atualização de status relevante, o sistema notifica via ferramenta externa (e-mail). *Interpretação adotada*: o enunciado ("atualização de status da OS via alguma ferramenta como email") é ambíguo; lemos como **notificar** a atualização por e-mail, não como alterar status respondendo e-mail — interpretação a confirmar com a banca/professores antes da implementação.
- **Critério de aceite**: transições de status disparam e-mail ao cliente (no mínimo: orçamento disponível e OS finalizada/entregue); falha de envio não bloqueia a transição; credenciais fora do código (Secret).
- **Estado atual**: zero integração de e-mail em `src/` (grep `email|smtp` só encontra login de usuário, ex.: `src/autenticacao/aplicacao/use_cases.py:35-58`); RN-014 adiou e-mail no MVP (`docs/requisitos/requisitos.md:76`); eventos de domínio são coletados mas o dispatch ficou deferido (`src/ordem_servico/aplicacao/use_cases.py:10-13`; `src/compartilhado/dominio/aggregate_root.py:20`).
- **Mudança**: criar `NotificacaoPort` + adapter SMTP (ou provedor gerenciado); ligar o dispatch dos eventos já emitidos pelo agregado ou chamar a porta nos casos de uso de transição.

### RNF-017 — Arquitetura: Clean Architecture ou Hexagonal formalizada

- **Descrição**: refatoração guiada por uma das duas abordagens, com separação de camadas e dependências auditável.
- **Critério de aceite**: ADR registrando a escolha; nenhuma importação de `infraestrutura` em `dominio`/`aplicacao`; regra verificada por lint/teste de arquitetura.
- **Estado atual**: camadas por contexto + Ports/UoW já praticadas (`src/ordem_servico/aplicacao/use_cases.py:1-14,47-51`; composition root descrito em `src/compartilhado/interfaces/router_publico.py:9-15`).
- **Mudança**: formalizar (ADR + verificação automática) e corrigir desvios encontrados na auditoria.

### RNF-018 — Testes dos fluxos críticos mantidos na refatoração

- **Descrição**: a refatoração e os fluxos novos mantêm a cobertura dos fluxos críticos.
- **Critério de aceite**: gate de 95% segue passando (`.coveragerc:29`); fluxos novos (RF-020 a RF-024) com testes unitários e de integração.
- **Estado atual**: CI com unitários, integração e cobertura (`.github/workflows/ci.yml:63-121`); E2E em `full-test/` (`full-test/README.md:5-7`).
- **Mudança**: somente extensão para os fluxos novos.

### RNF-019 — Conteinerização revisada

- **Descrição**: Dockerfile atualizado e docker-compose funcional para desenvolvimento local.
- **Critério de aceite**: imagem build-ável pelo pipeline; compose sobe stack local com healthcheck no app.
- **Estado atual**: Dockerfile multi-stage uv (`Dockerfile:1-57`); compose app+postgres+ui (`docker-compose.yml:1-69`) com healthcheck apenas no postgres (`docker-compose.yml:46-50`).
- **Mudança**: healthcheck do `app` (reusar `GET /api/v1/saude`), revisão de tags/labels para o fluxo de deploy.

### RNF-020 — Manifests Kubernetes completos

- **Descrição**: `/k8s` com Deployments, Services, ConfigMaps, Secrets e HPA (CPU/memória).
- **Critério de aceite**: `kubectl apply -f k8s/` sobe a aplicação; HPA escala sob carga; segredos fora de ConfigMap.
- **Estado atual**: inexistente (`ls k8s` falha); health probe pronto (`router_publico.py:35-38`).
- **Mudança**: criar manifests do zero, parametrizando env vars já usadas (`DATABASE_URL`, `JWT_SECRET` — ver `.github/workflows/ci.yml:11-14`).

### RNF-021 — IaC com Terraform

- **Descrição**: `/infra` com Terraform para cluster K8s (local ou cloud) e banco de dados, com documentação de recursos e aplicação.
- **Critério de aceite**: `terraform apply` provisiona cluster + banco; README de `/infra` documenta recursos e ordem de aplicação.
- **Estado atual**: inexistente (`ls infra` falha); banco hoje só via compose (`docker-compose.yml:20-50`, `postgres:16`) — o Terraform passa a provisioná-lo no cluster.
- **Mudança**: módulos Terraform novos; decidir alvo local (kind/k3d) vs cloud (ver §5).

### RNF-022 — Pipeline CI/CD com deploy

- **Descrição**: pipeline executa build, testes, build de imagem Docker, deploy no cluster (app + banco) e aplicação dos manifests.
- **Critério de aceite**: push na branch principal produz imagem versionada e aplica manifests no cluster alvo; falha de teste bloqueia o deploy.
- **Estado atual**: CI sem CD — lint/type-check/bandit/testes (`.github/workflows/ci.yml:17-127`); o E2E sobe a stack com `docker compose up` (build local ad-hoc, `.github/workflows/full-test-ci.yml:57`), mas nenhum workflow publica imagem versionada nem faz deploy.
- **Mudança**: estender workflow com build/push GHCR + etapa de deploy via kubectl/kustomize.

### RNF-023 — HPA-readiness: probes e resources

- **Descrição**: Deployment com liveness/readiness probes e resource requests/limits, pré-requisitos para o HPA por CPU/memória funcionar.
- **Critério de aceite**: probes apontando para `GET /api/v1/saude`; requests/limits definidos; HPA com métricas válidas (metrics-server ativo no cluster).
- **Estado atual**: endpoint de saúde existe (`src/compartilhado/interfaces/router_publico.py:35-38`); não há manifests, logo não há probes/resources.
- **Mudança**: definir valores iniciais de requests/limits a partir de medição local de carga (reusar `full-test/`).

### RNF-024 — Statelessness para escala horizontal

- **Descrição**: a aplicação deve se comportar corretamente com N réplicas.
- **Critério de aceite**: nenhuma funcionalidade depende de estado em memória de um pod específico; pool de conexões dimensionado para N réplicas.
- **Estado atual**: JWT já é stateless com denylist de revogação compartilhada no Postgres (`src/autenticacao/interfaces/middleware.py:39-47`; `src/autenticacao/infraestrutura/token_revogado_repository.py`); **exceções**: rate limiter slowapi com storage in-memory por processo (`src/compartilhado/interfaces/middleware.py:87`) — limites por IP divergem entre réplicas — e pool de conexões com defaults do SQLAlchemy sem dimensionamento (`src/compartilhado/infraestrutura/database.py:16`).
- **Mudança**: storage compartilhado para o rate limiter (ex.: Redis) **ou** documentar o limite como por-réplica; configurar `pool_size`/`max_overflow`/`pool_pre_ping` e validar contra `max_connections` do Postgres no pior caso do HPA.

### RN-018 — Prioridade de ordenação da listagem

Em execução > Aguardando aprovação > Em diagnóstico > Recebida; dentro da mesma prioridade, mais antiga primeiro (`criado_em ASC`), com desempate determinístico por `id` (preserva a lição de paginação de `src/ordem_servico/infraestrutura/repository.py:68-69`).

### RN-019 — Exclusão lógica de estados encerrados na listagem

`FINALIZADA` e `ENTREGUE` não aparecem na listagem padrão; a exclusão é por filtro de consulta (nenhum delete físico, nenhuma coluna de soft-delete necessária — o próprio status é o marcador).

### RN-020 — Destino dos status extras na listagem (proposta)

`AGUARDANDO_APROVACAO_COMPLEMENTAR` ordena com a prioridade de `AGUARDANDO_APROVACAO`; `CANCELADA` é excluída da listagem padrão como estado encerrado. A ratificar em ADR junto com RF-022 (ver §2).

## 4. Componentes auxiliares da fase 1

| Componente | O que é | Decisão | Justificativa |
|------------|---------|---------|---------------|
| `ui/` | Sandbox NiceGUI dev-only, fora do deploy do backend (`ui/README.md:7`) | **Manter, com adaptação mínima** | Útil para demonstrar consumo de API no vídeo de forma visual, mas o challenge aceita Postman/Swagger para isso; não recebe manifest K8s (continua dev-only). Adaptar apenas as chamadas afetadas por RF-020/RF-023; se o custo de manutenção crescer na refatoração, rebaixar o gate de cobertura dela é preferível a apagá-la. |
| `full-test/` | Harness E2E concorrente contra instância viva, multiusuário, 45 endpoints (`full-test/README.md:5-7`) | **Adaptar (promover)** | Vira a ferramenta de geração de carga para demonstrar o HPA escalando no vídeo (múltiplos usuários paralelos = pico de OS) e smoke test pós-deploy no pipeline. Precisa absorver os novos contratos (criação com itens, listagem ordenada, endpoint externo). |
| `db-image/` | Imagem Postgres seedada no GHCR + compose standalone, herdado da fase 1 | **Removido** | Aposentado no fechamento da fase 2 ([TD-018](../../tech-debt.md)): confundia (imagens `-p1` sem RF-020..024/Mailpit) e não agregava — o deploy oficial do banco é Terraform + pipeline (RNF-021/RNF-022) e o desenvolvimento local roda `postgres:16` via compose. Cluster e compose cobrem os dois cenários sem o atalho. |

**Veredito final aplicado (fechamento da fase 2)**: `ui/` e `full-test/` foram adaptados aos contratos da fase 2. A `ui/` (PR #28) exibe `situacao` nos badges (RF-021), ganhou o toggle "Mostrar encerradas" que passa `incluir_encerradas` (resolve [TD-020](../../tech-debt.md)) e cria OS com serviços/peças inline (RF-020) — segue dev-only, sem manifest K8s. O `full-test/` (PR #27) ganhou a `Fase2ContratosJourney` cobrindo RF-020..023 (criação inline, situação, decisão externa por webhook, listagem com `incluir_encerradas`) e segue como harness E2E e gerador de carga. O `db-image/` foi removido do repo da fase 2 ([TD-018](../../tech-debt.md) fechado por remoção): era o fast-check da fase 1, com imagens `-p1` sem RF-020..024, e não agregava sobre o compose `postgres:16` e o cluster.

## 5. Riscos

| # | Risco | Impacto | Mitigação |
|---|-------|---------|-----------|
| 1 | Migração de status: renomear valores persistidos para casar com os rótulos do challenge exigiria migration Alembic de dados + quebra de consumidores | Alto se renomear | Não renomear: valores snake_case continuam persistidos (`status.py:12`); rótulos do challenge entram só na apresentação (RF-021). Risco residual zero. |
| 2 | Compatibilidade de API: mudar o payload de criação (RF-020) e o default da listagem (RF-023) quebra consumidores da fase 1 (`ui/`, `full-test/`, collection da banca) | Médio | Mudanças aditivas (itens opcionais; novo default de ordenação documentado + parâmetro para visão completa); atualizar `ui/` e `full-test/` no mesmo PR; regerar a collection. |
| 3 | Custo de infraestrutura: cluster gerenciado em cloud tem custo recorrente; o challenge aceita "local ou cloud" | Médio | Default local (kind/k3d + metrics-server) para desenvolvimento e vídeo; cloud apenas se sobrar prazo. Decidir cedo na ADR de infraestrutura, pois muda os módulos Terraform. |
| 4 | Prazo: escopo de infra (K8s + Terraform + CI/CD + e-mail) somado à refatoração é grande para uma fase, e o vídeo exige ambiente estável de ponta a ponta | Alto | Sequenciar infra primeiro em modo incremental (deploy manual → pipeline), cortar opcionais cedo (ex.: Redis do rate limiter pode virar limitação documentada — RNF-024) e ensaiar o roteiro do vídeo com antecedência. |
| 5 | Demo do HPA: rate limiter in-memory por pod (`src/compartilhado/interfaces/middleware.py:87`) gera 429 inconsistentes sob carga distribuída, podendo poluir a demonstração de escalabilidade | Médio | Resolver RNF-024 antes do vídeo ou isolar o teste de carga em endpoints sem limite agressivo; validar o roteiro de carga com `full-test/` contra o cluster. |

> [↑ Raiz do projeto](../../../README.md) · [↑ Requisitos](../README.md)
