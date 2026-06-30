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
| `DomainEvent` (puro) | Não — vive só na sessão | Só `OrdemDeServico` tem dispatcher; os demais **não** |

## Eventos duráveis/consumidos — Ordem de Serviço

O contexto **Ordem de Serviço** (core) é o único que fechou o ciclo completo:
emite `IntegrationEvent`s, grava-os na outbox dentro da mesma transação da
UnitOfWork e os entrega via relay a handlers de notificação
([dispatcher](../../src/ordem_servico/aplicacao/dispatcher.py)):

- `DiagnosticoIniciadoEvent`, `OrcamentoGeradoEvent`, `OrcamentoAprovadoEvent`,
  `ServicoFinalizadoEvent`, `EntregaRegistradaEvent`, `OrdemCanceladaEvent`,
  `OrcamentoComplementarGeradoEvent` — todos `IntegrationEvent` (duráveis).
- `OrdemCriadaEvent` — `DomainEvent` interno, coletado pela transição.

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

1. Trocar a base do evento de `DomainEvent` para `IntegrationEvent`.
2. Gravar o evento na outbox dentro da UnitOfWork do caso de uso que o emite.
3. Registrar um handler no relay (mapa de handlers) para o efeito desejado.

Até lá, mantê-los como `DomainEvent` órfãos é a escolha correta: modelagem
completa, infraestrutura proporcional ao que a fase exige.
