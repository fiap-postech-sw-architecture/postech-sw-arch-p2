# Transactional Outbox + relay para entrega de eventos de integração

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)

* Status: Aceita
* Data: 2026-06-25

## Contexto e Problema

A [RF-018](../../../requisitos/requisitos.md) exige entrega real de eventos de integração — na fase 2, a notificação por e-mail ao cliente quando o estado da Ordem de Serviço muda ([ADR-018](018-notificacao-email.md)). Até então (registrado como TD-008 na [dívida técnica](../../../tech-debt/README.md)), os domain events eram despachados **sincronamente, in-process, dentro da transação da requisição**: o caso de uso alterava a OS e, no mesmo fluxo, chamava o dispatcher que entregava a notificação.

Esse arranjo sofre do problema clássico de **dual-write**: persistir o estado de negócio e entregar a notificação são dois efeitos colaterais distintos, e não há transação que os torne atômicos.

- Entregar **dentro** da transação acopla o commit do negócio ao SMTP: uma falha de e-mail faz rollback de uma mudança de OS legítima, e a latência da requisição passa a depender de um sistema externo.
- Entregar **depois** do commit perde o evento se o processo cair entre o commit e a entrega — a notificação some sem rastro, e não há retry nem durabilidade.

Em ambos os casos, estado e evento podem divergir: notificações perdidas ou espúrias. O sistema roda sob HPA ([ADR-016](016-plataforma-kubernetes.md)) com mais de uma réplica, o que agrava a janela de inconsistência.

**Como garantir entrega confiável (at-least-once), durável e desacoplada dos eventos de integração, sem o dual-write, mantendo a stack mínima da fase?**

## Decisão

**Adotar o padrão Transactional Outbox**, com a fila materializada no próprio PostgreSQL ([ADR-002](../002-banco-postgresql.md)) e um processo *relay* dedicado fazendo a entrega.

- **Escrita atômica**: a Unit of Work grava os `IntegrationEvent` numa tabela `outbox` **na mesma transação** da mudança de estado da OS. Estado e intenção de notificar commitam juntos ou não commitam — o dual-write deixa de existir.
- **Relay separado** (`python -m relay`, Deployment próprio no cluster — [ADR-019](019-pipeline-cicd-deploy.md)): faz **claim-then-deliver**. Reivindica um lote de linhas pendentes com `FOR UPDATE SKIP LOCKED` sob um *lease* (visibility timeout), entrega via o handler de e-mail ([ADR-018](018-notificacao-email.md)) e marca a linha como entregue.
- **Ordenação head-of-line por agregado**: eventos do mesmo agregado são entregues em ordem; um evento preso não deixa um posterior do mesmo agregado furar a fila.
- **At-least-once + idempotência**: a entrega é garantida ao menos uma vez; a deduplicação fica do lado do consumidor, via a tabela `processed_events` (um evento já processado é reconhecido e pulado).
- **Falha e DLQ**: falha de entrega agenda retry com backoff; esgotadas as tentativas, a linha vai para a *dead-letter* (`dead`), com endpoint/CLI administrativo para inspeção e reprocessamento.
- **Wake-up proativo via LISTEN/NOTIFY**: a escrita na outbox emite um `NOTIFY` **na mesma transação**; o relay fica em `LISTEN` e acorda na hora, em vez de só depender do polling. O polling periódico permanece como rede de segurança (um `NOTIFY` perdido não perde o evento — só atrasa até o próximo ciclo).
- **Zero infra nova**: a outbox, o lease e o NOTIFY são tudo PostgreSQL. Nenhum broker, fila gerenciada ou dependência externa entra na fase.

Detalhes de implementação em [relay/processador.py](../../../../relay/processador.py), [relay/listener.py](../../../../relay/listener.py) e na migração [003_outbox](../../../../migrations/versions/003_outbox.py). Entregue no PR #56.

## Alternativas Consideradas

* Outbox no PostgreSQL + relay (escolhida)
* Dispatch síncrono in-process (status quo — TD-008)
* Message broker dedicado (Kafka/RabbitMQ/SQS)
* LISTEN/NOTIFY puro, sem outbox

### Outbox no PostgreSQL + relay

* Bom, porque a escrita do evento é atômica com o estado — elimina o dual-write na raiz, que é a causa das notificações perdidas/espúrias
* Bom, porque não adiciona infraestrutura: reaproveita o PostgreSQL que já é o banco do sistema (ADR-002), mantendo o envelope de custo-zero dos ADRs de infra da fase
* Bom, porque dá durabilidade, retry, DLQ e idempotência — propriedades de produção — com mecanismos padrão de banco (`FOR UPDATE SKIP LOCKED`, lease, NOTIFY)
* Ruim, porque introduz um segundo processo (o relay) a empacotar, deployar e operar
* Ruim, porque a entrega é at-least-once e eventualmente consistente, não síncrona nem exactly-once — exige consumidores idempotentes

### Dispatch síncrono in-process (status quo)

* Bom, porque é o mais simples: nenhuma tabela, processo ou mecanismo de fila
* Ruim, porque sofre do dual-write — perde ou duplica eventos em falha/crash, exatamente o problema que a RF-018 não tolera
* Ruim, porque acopla a latência e o sucesso da requisição ao SMTP, e não tem retry nem durabilidade

### Message broker dedicado (Kafka/RabbitMQ/SQS)

* Bom, porque é a solução canônica de mensageria, com throughput e durabilidade de primeira classe
* Bom, porque desacopla produtor e consumidor por completo
* Ruim, porque adiciona um sistema distribuído inteiro à fase — provisionamento, operação, modos de falha — desproporcional a "enviar e-mail quando a OS muda", e em colisão com o risco de prazo do [gap analysis](../../../requisitos/fase2/gap-analysis-fase-2.md)
* Ruim, porque **não resolve sozinho o dual-write**: publicar no broker e commitar no banco continuam sendo duas escritas — a recomendação de produção é justamente um outbox **na frente** do broker. Para o MVP, o broker é a parte adiada; o outbox é a parte necessária

### LISTEN/NOTIFY puro, sem outbox

* Bom, porque é o mais leve para baixa latência: o consumidor acorda no evento sem tabela intermediária
* Ruim, porque `NOTIFY` é efêmero — um consumidor offline, um crash ou um reconnect perde a notificação sem rastro: zero durabilidade
* Ruim, porque sem uma linha persistida não há retry, DLQ nem idempotência. Por isso o NOTIFY aqui é só o **gatilho** sobre a outbox durável, não o transporte

## Consequências

### Positivas

* Estado e evento são atômicos: acabam as notificações perdidas (entrega pós-commit que o crash engole) e espúrias (rollback após entrega) do modelo síncrono
* Durabilidade real: o evento sobrevive a crash do relay, do consumidor e a indisponibilidade do SMTP — é reentregue
* A latência e a disponibilidade da API ficam independentes do SMTP; o pico de notificação não pressiona o caminho da requisição
* Retry com backoff e DLQ dão um caminho operacional para falha de entrega, em vez de perda silenciosa
* Baixa latência de entrega no caminho feliz, via NOTIFY, sem abrir mão da garantia (o polling cobre o NOTIFY perdido)
* Custo de infraestrutura zero: nenhum componente novo no cluster além do próprio processo relay

### Negativas

* Entrega **at-least-once**, não exactly-once: o consumidor precisa ser idempotente — resolvido com `processed_events`, mas é disciplina obrigatória para todo handler novo
* Consistência **eventual**: a notificação chega logo após o commit, não dentro dele — aceitável para e-mail, a registrar caso surja um consumidor que exija sincronia
* Um processo a mais para empacotar, deployar e observar
* O relay roda com `replicas: 1` como default conservador, mas `replicas>1` já é **seguro**: o *fencing* de lease na entrega (re-lock `FOR UPDATE SKIP LOCKED` + checagem de status `pendente` na transação por-linha — `bloquear_para_entrega` em [relay/processador.py](../../../../relay/processador.py)) serializa réplicas concorrentes sobre a mesma linha, sem duplicar a entrega mesmo se um lease vencer no meio de uma entrega lenta (**TD-021**, fechado no PR #66, sem mudança de schema). Permanece em aberto a ausência de métricas OTel no processo do relay (só structlog), registrada como **TD-022**

### Neutras

* Parâmetros operacionais — duração do lease/visibility timeout, política de backoff, tamanho do lote, intervalo de polling — ficam em configuração, fora deste ADR
* O único handler de entrega hoje é o de e-mail (ADR-018); novos tipos de evento/handler entram pelo mapa de handlers do relay sem tocar no domínio nem no core
* A política da DLQ (uma linha `dead` não bloqueia sucessores pendentes do mesmo agregado) é deliberada e alertável — refinável se o domínio exigir bloqueio estrito

## Decisões Relacionadas

- [ADR-002](../002-banco-postgresql.md): a outbox, o lease (`FOR UPDATE SKIP LOCKED`) e o `LISTEN/NOTIFY` são todos PostgreSQL — a decisão se apoia em não adicionar banco/fila
- [ADR-003](../003-arquitetura-ddd-onion.md): `IntegrationEvent` é conceito de domínio; a serialização e a entrega vivem na borda (infraestrutura/relay), sem o domínio conhecer o transporte
- [ADR-015](015-arquitetura-alvo-fase-2.md): o relay é o processo separado previsto na arquitetura alvo da fase
- [ADR-018](018-notificacao-email.md): o handler de e-mail é o consumidor que o relay aciona
- [ADR-019](019-pipeline-cicd-deploy.md): o relay tem build e deploy próprios no pipeline de CD
- [ADR-020](020-observabilidade-opentelemetry.md): a API tem OTel; o relay emite structlog — a paridade de OTel no relay é o débito TD-022

## Notas

* Requisito: [RF-018](../../../requisitos/requisitos.md). Resolve **TD-008** e, depois, **TD-021** (fencing de lease na entrega, PR #66 — `replicas>1` agora é seguro); deixa em aberto **TD-022** (métricas OTel + alerting no relay) — ver [tech-debt.md](../../../tech-debt/README.md)
* Implementação: PR #56 (outbox + relay); fencing de lease no PR #66 (TD-021)
* Gatilhos de revisão: escalar o relay para `replicas>1` já é seguro com o fencing de lease (TD-021); o gatilho remanescente é volume ou requisito de integração que justifique promover o broker dedicado, passando a outbox a alimentá-lo em vez do SMTP direto

> [↑ Raiz do projeto](../../../../README.md) · [↑ Arquitetura](../../README.md)
