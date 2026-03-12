# Glossário — Linguagem Ubíqua

Termos do domínio mapeados para identificadores no código, seguindo o modelo híbrido (ADR-009): termos de negócio em português sem acentos, sufixos de padrão técnico em inglês.

"OS" é a abreviação aceita para "Ordem de Serviço" em documentação, nomes de arquivo e mensagens de log.

## Contexto: Ordem de Serviço (Core)

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Ordem de Serviço (OS) | `OrdemDeServico` | Agregado raiz que representa o ciclo completo de atendimento a um veículo, desde o recebimento até a entrega. Contém itens e orçamento. |
| Status da Ordem | `StatusOrdem` | Enum Python que define os 7 estados possíveis da OS no ciclo de vida. |
| Recebida | `StatusOrdem.Recebida` | Estado inicial da OS, quando o veículo é registrado no sistema. |
| Em diagnóstico | `StatusOrdem.EmDiagnostico` | Mecânico está avaliando o veículo para identificar serviços necessários. |
| Aguardando aprovação | `StatusOrdem.AguardandoAprovacao` | Orçamento gerado e enviado ao cliente para aprovação. |
| Em execução | `StatusOrdem.EmExecucao` | Cliente aprovou o orçamento; serviços estão sendo realizados. Estoque reservado. |
| Finalizada | `StatusOrdem.Finalizada` | Todos os serviços concluídos; veículo pronto para retirada. |
| Entregue | `StatusOrdem.Entregue` | Veículo devolvido ao cliente. Estado terminal. |
| Cancelada | `StatusOrdem.Cancelada` | OS cancelada por rejeição de orçamento ou abandono. Estado terminal. Se cancelada em execução, estoque reservado é liberado. |
| Orçamento | `Orcamento` | Objeto de valor imutável com os itens precificados da OS. Armazenado como JSONB. Substituído integralmente quando itens mudam. |
| Linha do Orçamento | `LinhaOrcamento` | Objeto de valor que representa uma linha individual do orçamento (serviço ou peça com quantidade e preço). |
| Item da OS | `ItemDaOrdem` | Entidade dentro do agregado OrdemDeServico. Referencia um serviço do catálogo e opcionalmente um item de estoque. |
| Máquina de Status | `MaquinaDeStatus` | Colaborador stateless do agregado OrdemDeServico. Valida transições, executa guardas e emite eventos de domínio. |

## Contexto: Cliente + Veículo (Suporte)

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Cliente | `Cliente` | Agregado raiz que representa a pessoa física ou jurídica que traz veículos à oficina. Identificado por CPF ou CNPJ. |
| Veículo | `Veiculo` | Entidade filha do agregado Cliente. Não tem ciclo de vida independente. Criado via `Cliente.adicionar_veiculo()`. |
| Placa | `Placa` | Objeto de valor que representa a placa do veículo. Única entre todos os clientes. |
| Marca | `marca: str` | Atributo do veículo (ex: Fiat, Volkswagen). |
| Modelo | `modelo: str` | Atributo do veículo (ex: Uno, Gol). |
| Ano | `ano: int` | Ano de fabricação do veículo. |
| CPF | `CPF` | Objeto de valor com validação algorítmica. Implementa o protocolo `Documento`. |
| CNPJ | `CNPJ` | Objeto de valor com validação algorítmica. Implementa o protocolo `Documento`. |
| Documento (protocolo) | `Documento` | Protocol Python que define `formatado() -> str` e `mascarado() -> str`. Implementado por CPF e CNPJ. Específico do contexto Cliente. |

## Contexto: Catálogo de Serviços (Suporte)

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Serviço Oferecido | `ServicoOferecido` | Agregado raiz que representa um tipo de serviço disponível na oficina (ex: troca de óleo, alinhamento). Pode ser desativado sem afetar OS históricas. |
| DTO de Serviço Oferecido | `ServicoOferecidoDTO` | Tipo de retorno da `CatalogoPort`. Representa dados do catálogo consumidos pelo contexto Ordem de Serviço. |

## Contexto: Estoque (Suporte)

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Peça / Insumo | `ItemEstoque` | Agregado raiz que representa uma peça ou insumo com controle de quantidade. Bloqueio pessimista via `SELECT FOR UPDATE NOWAIT`. |
| Estoque | — | Conceito do domínio. Não é uma entidade; refere-se ao conjunto de itens gerenciados no contexto Estoque. |
| Reserva | — | Conceito do domínio. Ação `ItemEstoque.reservar(qtd)` que decrementa a quantidade disponível atomicamente no momento da aprovação do orçamento. |

## Contexto: Autenticação (Genérico)

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Usuário | `Usuario` | Entidade que representa um operador do sistema (admin ou mecânico). |
| Papel | `Papel` | Enum Python que define os papéis de acesso (ex: Admin, Mecanico). Usado no payload JWT. |

## Termos Compartilhados

| Termo do Domínio | Identificador no Código | Definição |
|---|---|---|
| Dinheiro | `Dinheiro` | Objeto de valor compartilhado. Campos: `valor: Decimal` (2 casas, `ROUND_HALF_UP`), `moeda: str = "BRL"`. Mapeado via `composite()`. |
| Unidade de Trabalho | `UnitOfWork` | Padrão técnico (EN). Gerencia a transação de banco de dados. Portas de escrita recebem a UdT para garantir atomicidade cross-contexto. |

## Padrões DDD (Termos Técnicos em Inglês)

| Termo | Definição no Contexto do Projeto |
|---|---|
| Entity | Classe base com identidade UUID. Igualdade por identidade. |
| AggregateRoot | Estende Entity. Raiz do agregado com gestão de eventos de domínio pendentes. |
| ValueObject | Classe base imutável (`frozen=True`). Igualdade por todos os campos. |
| DomainEvent | Evento imutável (`frozen=True`) com `ocorrido_em` e `agregado_id`. |
| Repository | Porta de persistência por agregado. Sufixo EN sobre nome PT (ex: `OrdemDeServicoRepository`). |
| Service | Serviço de aplicação ou domínio. Sufixo EN (ex: `CatalogoService`). |
| Port | Interface de comunicação entre contextos, definida pelo consumidor (ex: `EstoquePort`). |
| Open Host Service (OHS) | Padrão de integração DDD: contexto fornecedor expõe serviço padronizado. |
| Published Language | Padrão de integração DDD: linguagem compartilhada via DTOs. |
