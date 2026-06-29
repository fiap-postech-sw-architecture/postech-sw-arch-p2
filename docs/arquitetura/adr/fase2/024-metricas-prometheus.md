# Métricas de observabilidade com Prometheus e OpenTelemetry no relay

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-06-28

## Contexto e Problema

A [ADR-020](020-observabilidade-opentelemetry.md) entregou observabilidade em **escopo mínimo condicional**: instrumentação automática de FastAPI e SQLAlchemy exportando **traces** para o Jaeger, e excluiu **conscientemente** métricas (Prometheus/Grafana), logs correlacionados (Loki) e o Collector dedicado — a "stack completa" foi avaliada e rejeitada como desproporcional ao prazo e ao risco do demo (ADR-020, Decisão e alternativa "stack completa"). Aquele ADR registrou o gatilho de reabertura: "se a banca vier a exigir os três pilares, a reabertura deste ADR parte da alternativa de stack completa" (ADR-020, Neutras).

O **relay** de eventos ([ADR-022](022-transactional-outbox-relay.md)) é o processo que mais demanda visibilidade operacional da fase: entrega assíncrona at-least-once, com retry/backoff, *dead-letter* e fencing de lease para `replicas>1`. Hoje ele emite apenas um *gauge* via structlog — suficiente para um log, insuficiente para responder às perguntas que mantêm a entrega saudável:

- Quantos eventos estão **pendentes** na outbox agora (profundidade da fila)?
- Qual a **idade do mais antigo pendente** — há acúmulo, há um evento preso?
- Quantos eventos foram para a **dead-letter** (DLQ)?
- Qual a vazão de **entrega/falha/retry** ao longo do tempo?

Traces respondem "como foi *esta* requisição"; nenhuma dessas perguntas — todas de **tendência e estado agregado** — é respondível por traces. São exatamente o pilar de **métricas** que a ADR-020 deixou de fora. O débito ficou registrado como **TD-022** ([dívida técnica](../../../tech-debt/README.md)) e citado na própria ADR-022 ("permanece em aberto a ausência de métricas OTel no processo do relay (só structlog)").

**Como dar ao relay (e, por extensão, ao sistema) o pilar de métricas — profundidade da outbox, idade do pendente mais antigo, tamanho da DLQ, contadores de entrega/falha/retry — reabrindo a ADR-020 na parte de métricas sem cair na stack completa que ela rejeitou para o demo?**

## Decisão

**Adicionar o Prometheus como workload no cluster e instrumentar o relay com um `MeterProvider` do OpenTelemetry exportando via `PrometheusMetricReader`** num endpoint `/metrics` que o Prometheus faz *scrape*. Esta decisão **supersede parcialmente a [ADR-020](020-observabilidade-opentelemetry.md) na parte de métricas** — os traces continuam exatamente como a ADR-020 os definiu (auto-instrumentação → Jaeger, sem mudança).

- **Prometheus como mais um workload de demo**: um `Deployment` + `Service` (porta 9090) no cluster kind, seguindo o **mesmo padrão dos demais workloads de apoio da fase** — Mailpit ([ADR-018](018-notificacao-email.md)), Jaeger ([ADR-020](020-observabilidade-opentelemetry.md)) e Redis ([ADR-023](023-rate-limiter-storage-compartilhado.md)). Nenhuma infraestrutura gerenciada nova; sobe e desce com o cluster, UI por port-forward na gravação.
- **Relay instrumentado com OTel `MeterProvider` + `PrometheusMetricReader`**: o relay ([ADR-022](022-transactional-outbox-relay.md)) ganha um `MeterProvider` com um `PrometheusMetricReader`, expondo `/metrics` no formato Prometheus na **porta 9100**, servido por um Service `pytstop-relay-metrics`. Um Service dedicado às métricas (em vez de o relay virar um Deployment com Service de tráfego) mantém o relay como o processo *headless* que já é — o `/metrics` é só um alvo de *scrape*, não uma porta de serviço de negócio.
- **Opt-in por env `RELAY_METRICS_ENABLED`**: quando habilitada, o relay sobe o `MeterProvider` e o servidor de `/metrics`; **quando ausente/falsa, a instrumentação fica inerte** — sem servidor, sem porta, sem custo. Isso preserva o desenvolvimento local, o `docker compose` e o CI (onde não há Prometheus para fazer *scrape*), no mesmo molde do *opt-in* por env que a ADR-020 adota para o endpoint OTLP e a ADR-023 para o `storage_uri` do Redis.
- **Métricas expostas** — os sinais operacionais da entrega:
  - **Gauges**, alimentados por *callback* sobre a query de profundidade da outbox: `outbox_pendentes` (pendentes agora), `outbox_idade_mais_antigo_seconds` (idade do pendente mais antigo; o instrumento é `outbox_idade_mais_antigo` com `unit="s"`, e o exportador Prometheus anexa o sufixo `_seconds` ao nome da série) e `outbox_dead` (tamanho da DLQ).
  - **Counters**, incrementados no caminho de entrega: `outbox_entregue_total`, `outbox_falha_total`, `outbox_dead_total` e `outbox_retry_total`.
- **Métricas só do relay, por ora**: a API não ganha métricas nesta onda — a instrumentação RED da API (latência p95, taxa de erro) fica como evolução natural (ver Consequências/Notas). O alvo desta decisão é o processo cuja saúde operacional é hoje opaca: o relay.
- **Alerting e dashboards ficam como evolução**: o Prometheus passa a **coletar e armazenar** as séries; regras de alerta (ex.: DLQ crescente, idade do pendente acima de limite) e dashboards (Grafana) ficam fora desta onda, agora **possíveis** porque a base de métricas existe (ver Notas).

O `MeterProvider` e o servidor de `/metrics` vivem na **borda** (infraestrutura do relay), no mesmo princípio da ADR-020: telemetria é detalhe de borda — o domínio e os casos de uso não conhecem OTel nem Prometheus ([ADR-015](015-arquitetura-alvo-fase-2.md)).

## Alternativas Consideradas

* Prometheus faz *scrape* do `/metrics` do relay (escolhida)
* *Push* OTLP de métricas para o Jaeger
* Manter só o *gauge* via structlog (status quo — TD-022)
* Stack completa: Collector + Prometheus + Grafana + Loki

### Prometheus faz *scrape* do `/metrics` do relay

* Bom, porque entrega o **pilar de métricas** que a ADR-020 deixou de fora, com o backend padrão de métricas (Prometheus) e o `PrometheusMetricReader` que é o caminho nativo do OTel para esse modelo *pull*
* Bom, porque reusa um **padrão de workload já estabelecido** na fase (Deployment+Service de demo, como Mailpit, Jaeger e Redis) — nenhuma operação nova a aprender
* Bom, porque é **opt-in e sem custo** para dev/CI: ausente `RELAY_METRICS_ENABLED`, o relay não sobe o `/metrics` e nada muda no fluxo local ou no compose
* Bom, porque o modelo *pull* (o Prometheus busca) dá ao próprio Prometheus o sinal de `up`/`down` do alvo — a indisponibilidade do relay vira métrica, sem o relay precisar saber para onde empurrar
* Ruim, porque adiciona **um workload** (Prometheus) a subir e operar no cluster
* Ruim, porque, no modelo *pull*, processos de vida curta ou sem porta exposta exigiriam *pushgateway* — não é o caso do relay (processo longevo), mas é uma restrição do modelo a registrar

### *Push* OTLP de métricas para o Jaeger

* Bom, porque reusaria o backend de observabilidade já presente (Jaeger) e o mesmo transporte OTLP dos traces — zero workload novo
* Ruim, porque **o Jaeger não armazena métricas**: é um backend de *tracing*, não de séries temporais — não há onde as métricas pousarem nem como consultá-las. Tecnicamente inviável; **descartada**

### Manter só o *gauge* via structlog (status quo — TD-022)

* Bom, porque é o mais simples: nenhuma dependência, nenhum workload — o relay já emite o *gauge* no log
* Ruim, porque um valor no log **não dá dashboards nem alerting**: não há série temporal consultável, não há agregação, não há gatilho automático sobre DLQ crescente ou pendente envelhecendo — era exatamente o débito **TD-022**
* Ruim, porque deixa a saúde operacional do processo mais crítico da fase (o relay) **opaca** para qualquer pergunta de tendência

### Stack completa: Collector + Prometheus + Grafana + Loki

* Bom, porque cobre os três pilares com correlação por TraceId e usa o Collector como intermediário, conforme a recomendação de produção — o objetivo final da disciplina (era a alternativa "stack completa" da ADR-020)
* Ruim, porque adiciona **quatro ou cinco workloads**, pipeline de telemetria e dashboards — o mesmo **exagero para o demo** que a ADR-020 já rejeitou; reabri-lo inteiro contraria o gatilho registrado (reabrir *pela parte de métricas*, não pela stack completa)
* Ruim, porque mais partes móveis no cluster significam mais modos de falha na gravação do vídeo — o argumento da ADR-020 segue valendo

## Consequências

### Positivas

* O sistema passa a ter o **terceiro pilar de observabilidade** (métricas), somando-se aos traces da ADR-020 — os três pilares deixam de ser uma lacuna conhecida da fase na parte que mais importava operacionalmente
* A entrega do relay fica **observável em estado e tendência**: profundidade da outbox, idade do pendente mais antigo, tamanho da DLQ e vazão de entrega/falha/retry — as perguntas que traces não respondem
* **Dashboards e alerting tornam-se possíveis**: com as séries no Prometheus, montar um painel (Grafana) ou uma regra de alerta sobre DLQ/idade do pendente passa a ser configuração, não novo desenvolvimento de instrumentação
* O relay em **HA (`replicas>1`, já seguro pelo fencing de lease da TD-021)** fica observável — as métricas dão o sinal operacional que faltava para operar o relay escalado com confiança
* **Opt-in sem custo** para dev/local/CI: ausente `RELAY_METRICS_ENABLED`, o relay não expõe `/metrics` e o fluxo de um processo só segue idêntico
* Reusa o **padrão de workload de demo** já praticado (Deployment+Service, port-forward), sem operação nova

### Negativas

* **Um workload novo** (Prometheus) a empacotar, subir e operar no cluster — superfície operacional e de falha a mais
* O Prometheus da fase é **de demonstração — sem persistência nem HA**: retenção curta em memória/efêmera, sem réplica nem failover; as séries não sobrevivem a um restart (aceitável para o demo; inadequado para produção)
* **Métricas só do relay nesta onda**: a API segue sem métricas RED — a instrumentação da API fica como evolução, então perguntas de latência/erro *da API* continuam sem resposta por aqui
* A configuração de *scrape* e de retenção é mínima e não endurecida (sem autenticação no `/metrics`, sem NetworkPolicy) — coerente com o cluster de demo, a endurecer se sair do demo (gatilho nas Notas)
* **Counters in-memory por-processo vs. `replicas>1`**: os counters (`outbox_entregue_total`/`outbox_falha_total`/`outbox_dead_total`/`outbox_retry_total`) vivem na memória de cada processo do relay, e o `/metrics` é exposto por um Service **ClusterIP (load-balanced)** (`pytstop-relay-metrics`, definido por esta ADR em [`k8s/relay.yaml`](../../../../k8s/relay.yaml)). Com o relay em `replicas:1` (default do demo) isso não se manifesta. Mas como esta fase **habilita escalar** o relay com segurança (fencing de lease da TD-021, [ADR-022](022-transactional-outbox-relay.md)), registra-se a restrição: a `replicas>1`, cada *scrape* cai num pod aleatório do Service, então `rate()`/`increase()` sobre os counters veriam **resets espúrios** (o contador do pod A não é o do pod B). Operar o relay escalado com os counters corretos exige **scrape por-pod** — Service *headless* + *service-discovery* do Prometheus (um alvo por pod), evolução fora do escopo do demo. Os **gauges** (`outbox_pendentes`/`outbox_idade_mais_antigo_seconds`/`outbox_dead`) **não** têm esse problema: são lidos do banco (estado compartilhado), idênticos em qualquer pod. No demo (`replicas:1`) a limitação não aparece.

### Neutras

* **Alerting via regras do Prometheus** (e dashboards no Grafana) ficam como **evolução** — habilitados pela base de métricas agora existente, fora do escopo desta onda
* Parâmetros operacionais — intervalo de *scrape*, janela de retenção, porta/host do Prometheus e do `/metrics` do relay — ficam em **configuração** (env/ConfigMap/manifest), fora deste ADR
* A escolha do backend é transparente para o relay: o `MeterProvider` exporta no formato Prometheus pelo `PrometheusMetricReader`; trocar para *push* OTLP a um Collector no futuro é mudança de *reader*/exporter, sem tocar a lógica de entrega

## Decisões Relacionadas

- [ADR-020](020-observabilidade-opentelemetry.md): **supersede parcial** — a ADR-020 excluiu métricas de propósito e registrou o gatilho de reabertura; esta ADR reabre **só a parte de métricas** (Prometheus + relay), mantendo os traces (Jaeger) exatamente como a ADR-020 os definiu
- [ADR-022](022-transactional-outbox-relay.md): o relay é o processo instrumentado; as métricas (pendentes/idade/DLQ, entregue/falha/retry) medem o ciclo claim-then-deliver/backoff/DLQ desse ADR — fecha o débito TD-022 que a ADR-022 deixou em aberto
- [ADR-016](016-plataforma-kubernetes.md): o Prometheus é mais um workload no cluster kind da fase — a decisão se apoia na plataforma Kubernetes local já estabelecida
- [ADR-015](015-arquitetura-alvo-fase-2.md): a instrumentação de métricas é preocupação de borda; o `MeterProvider` e o `/metrics` vivem na infraestrutura do relay, sem tocar domínio/aplicação

## Notas

* Resolve **TD-022** ([dívida técnica](../../../tech-debt/README.md)): ausência de métricas OTel no processo do relay (só structlog) — o débito que a [ADR-022](022-transactional-outbox-relay.md) deixou registrado
* Implementação: PR #66 (junto do fencing de lease da TD-021)
* Gatilhos de revisão: **métricas da API** (instrumentação RED — latência p95, taxa de erro), **Grafana/dashboards** sobre as séries do Prometheus, e **alerting** (regras do Prometheus sobre DLQ crescente, idade do pendente acima de limite); endurecimento (persistência/retenção, autenticação do `/metrics`, NetworkPolicy, HA do Prometheus) fica fora do escopo do demo

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
