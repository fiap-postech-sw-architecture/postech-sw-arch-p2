# Eventos de domínio — taxonomia e consumidores (TD-030)

> Registro explícito da decisão de modelagem por trás dos eventos de domínio da
> fase 2: **quais são duráveis/consumidos e quais são emitidos sem consumidor de
> propósito**. Documentado para que a revisão não leia os eventos órfãos como um
> bug — eles são intenção de modelagem (DDD), não dívida acidental.

## Dois tipos de evento

A base `DomainEvent` ([compartilhado/dominio](../../src/compartilhado/dominio))
marca um fato de negócio que um agregado emite ao mudar de estado.
`IntegrationEvent` é a sua especialização: um evento que **cruza bounded
contexts** e exige **durabilidade** — ele é gravado na Transactional Outbox e
entregue pelo relay (RF-018; [ADR-022](adr/fase2/022-transactional-outbox-relay.md)).

| Tipo | Durável? | Consumido na fase 2? |
|------|----------|----------------------|
| `IntegrationEvent` | Sim — Outbox + relay | Sim — notificação por e-mail (Ordem de Serviço) |
| `DomainEvent` (puro) | Não — vive só na sessão | Não — coletado pela transição e descartado (não há dispatcher) |

## Mecanismo de entrega — não há dispatcher síncrono

A fase 2 **não** tem um dispatcher que percorra os eventos e chame handlers
em processo. O caminho é único e durável, e vale para todos os contextos:

1. O agregado **registra** o evento ao mudar de estado (via
   `_registrar_evento`). Um `IntegrationEvent` é a subclasse que deve cruzar o
   processo e ser entregue; um `DomainEvent` puro é só o registro do fato.
2. No `commit`, a `UnitOfWork` **filtra** os `IntegrationEvent`s dos eventos
   registrados e os grava na tabela `outbox` **na mesma transação** do estado
   de negócio (Transactional Outbox — elimina o dual-write). Os `DomainEvent`s
   puros não vão para a outbox: são coletados e descartados no fim da sessão.
3. O processo *relay* (`python -m relay`) lê a outbox e entrega ao handler de
   notificação — semântica at-least-once, idempotência por `processed_events`.
   O registro tipo → handler vive em [`relay/handlers.py`](../../relay/handlers.py).

Não existe `src/ordem_servico/aplicacao/dispatcher.py`: o dispatch síncrono
(código morto) foi removido na revisão pós-entrega; a entrega por evento é
100% outbox + relay.

## Eventos duráveis/consumidos — Ordem de Serviço

O contexto **Ordem de Serviço** (core) é o único que fecha o ciclo completo:
emite `IntegrationEvent`s, a `UnitOfWork` os grava na outbox e o relay os
entrega ao handler de notificação. São **9** os `IntegrationEvent` duráveis
([events.py](../../src/ordem_servico/dominio/events.py), mesmo conjunto do mapa
de handlers em [`relay/handlers.py`](../../relay/handlers.py)):

- `DiagnosticoIniciadoEvent`, `OrcamentoGeradoEvent`, `OrcamentoAprovadoEvent`,
  `ServicoFinalizadoEvent`, `EntregaRegistradaEvent`, `OrdemCanceladaEvent`,
  `OrcamentoComplementarGeradoEvent`, `OrcamentoComplementarAprovadoEvent`,
  `OrcamentoComplementarRejeitadoEvent` — todos `IntegrationEvent` (duráveis).
- `OrdemCriadaEvent` — `DomainEvent` puro, coletado pela transição e descartado
  (nenhum handler o consome: criação não é atualização de status, RF-024).

## Eventos órfãos por design — emitidos, sem consumidor na fase 2

Os agregados dos contextos de apoio **emitem** `DomainEvent`s ao mudar de estado
(completude de modelagem — o agregado declara seus fatos de negócio), mas **na
fase 2 não há dispatcher nem gravação em outbox** para eles: são coletados em
memória e descartados no fim da sessão. Isso é **deliberado** — nenhum requisito
da fase 2 consome esses fatos; promovê-los a `IntegrationEvent` sem um consumidor
real seria infraestrutura sem uso (YAGNI).

| Contexto | Eventos órfãos (emitidos, sem consumidor) |
|----------|--------------------------------------------|
| Catálogo de Serviços | `ServicoCadastradoEvent` |
| Cliente + Veículo | `VeiculoAdicionadoEvent`, `VeiculoRemovidoEvent`, `ClienteAtualizadoEvent`, `ClienteDesativadoEvent`, `ClienteCadastradoEvent` |
| Estoque | `EstoqueReservadoEvent`, `EstoqueLiberadoEvent` |

São **8 eventos** emitidos sem consumidor. Não há perda de comportamento: as
regras de negócio que dependeriam deles (ex.: baixa de estoque) já são tratadas
**sincronamente** dentro do mesmo caso de uso; o evento é o registro do fato, não
o mecanismo da regra.

## Como promover um evento órfão (quando houver consumidor)

Se uma fase futura precisar reagir a um desses fatos com durabilidade
cross-context, o caminho é o padrão já consolidado em Ordem de Serviço:

1. Trocar a base do evento de `DomainEvent` para `IntegrationEvent` — só isso
   já faz a `UnitOfWork` gravá-lo na outbox no `commit` do caso de uso que o
   emite (o filtro é por tipo, não há passo manual de enfileiramento).
2. Registrar um handler no relay (mapa em [`relay/handlers.py`](../../relay/handlers.py))
   para o efeito desejado.

Até lá, mantê-los como `DomainEvent` órfãos é a escolha correta: modelagem
completa, infraestrutura proporcional ao que a fase exige.
