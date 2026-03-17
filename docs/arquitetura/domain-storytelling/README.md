# Domain Storytelling

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

Diagramas pictográficos que capturam histórias do dia a dia da oficina: quem faz o quê, com quais objetos de trabalho, em que sequência.

> Diagramas gerados com assistência de IA (Claude) e revisados manualmente pela equipe no [egon.io](https://egon.io).
> As histórias foram derivadas de [entrevistas simuladas com especialistas de domínio](especialistas-de-dominio.md).

## Diagramas

| # | Arquivo | Cenário | Atores | Atividades |
|---|---|---|---|---|
| 1 | [oficina-recepcao-os.egn](oficina-recepcao-os.egn) | Recepção e abertura de OS | Cliente, Recepcionista, Mecânico-Chefe | Chegada do cliente, coleta de dados, abertura da OS, distribuição ao mecânico |
| 2 | [oficina-diagnostico-orcamento.egn](oficina-diagnostico-orcamento.egn) | Diagnóstico e orçamento | Mecânico, Orçamentista, Recepcionista, Cliente | Diagnóstico técnico, cotação de peças, montagem do orçamento, aprovação |
| 3 | [oficina-execucao-entrega.egn](oficina-execucao-entrega.egn) | Execução e entrega | Mecânico, Recepcionista, Cliente | Execução do serviço, teste, comunicação ao cliente, entrega e pagamento |
| 4 | [oficina-gestao-estoque.egn](oficina-gestao-estoque.egn) | Gestão de estoque | Mecânico-Chefe, Comprador, Fornecedor | Verificação visual, pedido de reposição, recebimento, conferência |
| 5 | [oficina-acompanhamento-cliente.egn](oficina-acompanhamento-cliente.egn) | Acompanhamento pelo cliente | Cliente, Recepcionista | Consulta de status, follow-up de orçamento, notificação de conclusão |

## Como abrir os diagramas

1. Acesse [egon.io](https://egon.io)
2. Clique em **Open** (ícone de pasta)
3. Selecione o arquivo `.egn` desejado
4. O diagrama será renderizado automaticamente

Os arquivos `.egn` são JSON — podem ser versionados normalmente no Git.

## Especialistas de Domínio

As histórias vieram de entrevistas com 5 especialistas de domínio fictícios (dono, recepcionista, mecânico, orçamentista, cliente). Perfis, entrevistas e mapeamento com os diagramas: [especialistas-de-dominio.md](especialistas-de-dominio.md)

## Cobertura dos Contextos Delimitados

| Contexto Delimitado | Diagramas |
|---|---|
| Ordem de Serviço | Recepção (#1), Diagnóstico (#2), Execução (#3) |
| Cliente + Veículo | Recepção (#1), Acompanhamento (#5) |
| Catálogo de Serviços | Diagnóstico (#2) |
| Estoque | Gestão de Estoque (#4), Diagnóstico (#2) |
| Autenticação | — (contexto genérico, sem história de domínio) |

## Relação com Outros Documentos

- [Event Storming](../event-storming/) — Fluxos detalhados derivados das mesmas histórias
- [Workshop de Event Storming](../event-storming/workshop-event-storming.md) — Workshop progressivo com os mesmos especialistas
- [Glossário](../../requisitos/glossario.md) — Linguagem Ubíqua com todos os termos de domínio
- [Mapa de Contextos](../mapa-contextos.md) — Relação entre os 5 contextos delimitados
- [ADR-007](../adr/007-organizacao-contextos-delimitados.md) — Organização dos contextos delimitados
