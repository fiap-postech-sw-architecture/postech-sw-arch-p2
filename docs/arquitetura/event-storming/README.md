# Event Storming

Documentação do Event Storming do projeto, conforme exigido pelo Tech Challenge Fase 1.

## Fluxos

| Fluxo | Arquivo | Descrição |
|---|---|---|
| 1 | [fluxo-1-ciclo-os.md](fluxo-1-ciclo-os.md) | Ciclo de vida da Ordem de Serviço — desde o recebimento do veículo até a entrega ao cliente. Inclui cadastro de clientes/veículos, criação da OS, diagnóstico, orçamento, aprovação, execução, finalização e entrega. |
| 2 | [fluxo-2-gestao-estoque.md](fluxo-2-gestao-estoque.md) | Gestão de peças e insumos — cadastro de itens, controle de quantidade, reserva (acionada pela aprovação de orçamento), liberação (acionada por cancelamento) e alertas de estoque baixo. |

## Convenção de Cores

Segue a convenção padrão de Event Storming (Alberto Brandolini):

| Cor | Elemento | Descrição |
|---|---|---|
| 🟠 Laranja | Evento de Domínio | Fato que aconteceu no passado, nomeado no particípio (ex: `OrcamentoAprovadoEvent`) |
| 🔵 Azul | Comando | Intenção de ação disparada por um ator ou política (ex: `AprovarOrcamento`) |
| 🟡 Amarelo | Agregado | Entidade raiz que recebe o comando e emite o evento (ex: `OrdemDeServico`) |
| 🟣 Lilás | Read Model | Projeção de dados para consulta e apresentação |
| 🔴 Vermelho | Hotspot | Ponto de atenção, decisão pendente ou incerteza do domínio |
| 🩷 Rosa | Política | Regra reativa — ao observar um evento, dispara outro comando |

## Boards Visuais

Os diagramas detalhados estão representados em Mermaid dentro de cada arquivo de fluxo, incluindo:
- Máquina de estados (stateDiagram)
- Sequência de eventos (sequenceDiagram)

Boards visuais em Excalidraw (PNG) podem ser adicionados futuramente para apresentação no vídeo.

## Relação com Outros Documentos

- [Glossário](../../requisitos/glossario.md) — Linguagem Ubíqua com todos os termos de domínio
- [Mapa de Contextos](../mapa-contextos.md) — Relação entre os 5 contextos delimitados
- [Modelo de Domínio](../modelo-dominio.md) — Diagramas de classes por agregado
