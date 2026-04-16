# Event Storming

> **Versao**: 1.0 — Fase 1 MVP.

Documentação do Event Storming do projeto, conforme exigido pelo Tech Challenge Fase 1.

## Fluxos

| Fluxo | Arquivo | Descrição |
|---|---|---|
| 1 | [fluxo-1-ciclo-os.md](fluxo-1-ciclo-os.md) | Ciclo de vida da Ordem de Serviço — desde o recebimento do veículo até a entrega ao cliente. Inclui cadastro de clientes/veículos, criação da OS, diagnóstico, orçamento, aprovação, execução, finalização e entrega. |
| 2 | [fluxo-2-gestao-estoque.md](fluxo-2-gestao-estoque.md) | Gestão de peças e insumos — cadastro de itens, controle de quantidade, reserva (acionada pela aprovação de orçamento), liberação (acionada por cancelamento) e alertas de estoque baixo. |
| Workshop | [workshop-event-storming.md](workshop-event-storming.md) | Workshop progressivo de 10 passos com 5 especialistas de domínio (Aula 06) — narrativa do processo que gerou os fluxos acima. |

## Convenção de Cores

Segue a convenção padrão de Event Storming (Alberto Brandolini):

| Cor | Elemento | Descrição |
|---|---|---|
| 🟠 Laranja | Evento de Domínio | Fato que aconteceu no passado, nomeado no particípio (ex: `OrcamentoAprovadoEvent`) |
| 🔵 Azul | Comando | Intenção de ação disparada por um ator ou política (ex: `AprovarOrcamento`) |
| 🟡 Amarelo claro | Ator | Pessoa ou papel que dispara um comando (ex: Admin, Mecânico, Cliente) |
| 🟡 Amarelo | Agregado | Entidade raiz que recebe o comando e emite o evento (ex: `OrdemDeServico`) |
| 🟢 Verde | Read Model | Projeção de dados consultada antes de um comando |
| 🟣 Lilás | Política | Regra reativa — ao observar um evento, dispara outro comando |
| 🔴 Vermelho | Hotspot | Ponto de atenção, decisão pendente ou incerteza do domínio |
| 🩷 Rosa | Sistema Externo | Sistema fora da fronteira do domínio |

## Progressão Metodológica

O workshop segue os 10 passos progressivos de Brandolini, cada um adicionando uma camada ao modelo:

1. **Brainstorming** — Eventos soltos (post-its laranja)
2. **Linha do Tempo** — Happy path + caminhos alternativos
3. **Pontos de Atenção** — Hotspots (losangos vermelhos)
4. **Eventos Pivotais** — Marcadores de mudança de fase
5. **Comandos** — Ações dos atores (post-its azuis)
6. **Políticas** — Regras reativas automáticas (post-its lilás)
7. **Modelos de Leitura** — Projeções de dados (post-its verdes)
8. **Sistemas Externos** — Integrações fora do domínio (post-its rosa)
9. **Agregados** — Agrupamento de comandos e eventos
10. **Contextos Delimitados** — Fronteiras e padrões de integração

## Boards Visuais

Os diagramas detalhados estão representados em Mermaid dentro de cada arquivo de fluxo, incluindo:
- Máquina de estados (stateDiagram)
- Sequência de eventos (sequenceDiagram)
- Diagramas progressivos por passo no [workshop](workshop-event-storming.md)

## Relação com Outros Documentos

- [Domain Storytelling — Especialistas](../domain-storytelling/especialistas-de-dominio.md) — Entrevistas com os 5 experts que participaram do workshop
- [Domain Storytelling — Diagramas](../domain-storytelling/) — Diagramas pictográficos derivados das mesmas entrevistas
- [Glossário](../../requisitos/glossario.md) — Linguagem Ubíqua com todos os termos de domínio
- [Mapa de Contextos](../mapa-contextos.md) — Relação entre os 5 contextos delimitados
- [Modelo de Domínio](../modelo-dominio.md) — Diagramas de classes por agregado
