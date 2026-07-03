# Mapa de Contextos

> [↑ Raiz do projeto](../../README.md) · [↑ Arquitetura](README.md)

> **Versão**: 1.1 — Fase 2. Corrige assinaturas de portas (`ClientePort`, `EstoquePort`), o agregado Cliente/Veículo e adiciona o caminho assíncrono (outbox + relay).

5 contextos delimitados com padrões de integração DDD. Decisão de organização: [ADR-007](adr/007-organizacao-contextos-delimitados.md).

## Diagrama

```mermaid
graph LR
    subgraph Principal
        OS[Ordem de Servico<br/><i>Principal</i>]
        E[Estoque<br/><i>Principal</i>]
    end
    subgraph Suporte
        C[Cliente + Veiculo<br/><i>Suporte</i>]
        CS[Catalogo de Servicos<br/><i>Suporte</i>]
    end
    subgraph Generico
        A[Autenticacao<br/><i>Generico</i>]
    end

    C -->|Cliente-Fornecedor| OS
    CS -->|OHS / Linguagem Publicada| OS
    E -->|OHS / Linguagem Publicada| OS
    A -.->|middleware| OS
    A -.->|middleware| C
    A -.->|middleware| CS
    A -.->|middleware| E
```

> Direção das setas: fornecedor → consumidor (upstream → downstream).

## Contextos Delimitados

| Contexto | Classificação | Agregados | Responsabilidade |
|---|---|---|---|
| **Ordem de Serviço** | Principal | `OrdemDeServico` | Ciclo de vida da OS (7+1 status), geração de orçamento, orquestração cross-contexto |
| **Cliente + Veículo** | Suporte | `Cliente` (raiz; `Veiculo` é entidade filha) | Cadastro e validação de clientes (CPF/CNPJ) e seus veículos |
| **Catálogo de Serviços** | Suporte | `ServicoOferecido` | Tipos de serviço disponíveis com preços |
| **Estoque** | Principal | `ItemEstoque` | Peças e insumos com reserva pessimista e controle de quantidade |
| **Autenticação** | Genérico | `Usuario` | JWT, credenciais, RBAC. Substituível por Auth0/Keycloak. |

## Padrões de Integração

### Cliente-Fornecedor (Customer-Supplier)

**Fornecedor**: Cliente + Veículo
**Consumidor**: Ordem de Serviço

O contexto Cliente fornece dados para a criação de OS e para notificações. A porta `ClientePort` (definida pelo consumidor) expõe:
- `cliente_existe(cliente_id) -> bool`
- `veiculo_pertence_ao_cliente(cliente_id, veiculo_id) -> bool`
- `obter_contato(cliente_id) -> ClienteContatoDTO | None` — resolve o destinatário do e-mail (RF-024)
- `obter_clientes_em_lote(cliente_ids) -> dict[UUID, ClienteResumoDTO]` — enriquece projeções sem N+1
- `obter_veiculos_em_lote(veiculo_ids) -> dict[UUID, VeiculoResumoDTO]` — idem, para placas

Operações de leitura — não recebem `UnitOfWork`. A consulta pública por placa+documento (acompanhamento sem login) não passa por esta porta — ver o trade-off em [Consulta Reversa](#consulta-reversa-downstream--upstream).

### Open Host Service (OHS) / Linguagem Publicada

**Fornecedores**: Catálogo de Serviços, Estoque
**Consumidor**: Ordem de Serviço

Catálogo expõe serviços via `CatalogoPort`:
- `obter_servico(servico_id) -> ServicoOferecidoDTO | None`
- `obter_servicos_em_lote(servico_ids) -> dict[UUID, ServicoOferecidoDTO]` — enriquece projeções sem N+1

Estoque expõe reserva/liberação/consulta via `EstoquePort`:
- `reservar(item_estoque_id, quantidade) -> None`
- `liberar(item_estoque_id, quantidade) -> None`
- `obter_item(item_estoque_id) -> ItemEstoqueDTO | None` — preço da peça consumida
- `obter_itens_em_lote(item_estoque_ids) -> dict[UUID, ItemEstoqueDTO]` — enriquece projeções sem N+1

Os adaptadores são construídos com a sessão da requisição (session-scoped): a atomicidade vem da transação compartilhada, não de um `UnitOfWork` passado por parâmetro.

A Linguagem Publicada é o conjunto de DTOs imutáveis do módulo de portas (`ServicoOferecidoDTO`, `ItemEstoqueDTO`, `ClienteResumoDTO`, `ClienteContatoDTO`, `VeiculoResumoDTO`) — tipos compartilhados que desacoplam os contextos.

### Consulta Reversa (Downstream → Upstream)

Os contextos Cliente e Estoque precisam consultar vínculos com OS antes de permitir exclusão/desativação (RN-009, RN-011). Como a direção principal de dependência é OS → fornecedores, uma porta reversa é necessária.

A porta `OrdemDeServicoPort` é definida pelos contextos consumidores (Cliente, Estoque) na sua camada de aplicação:
- `existe_os_ativa_para_cliente(cliente_id) -> bool` — usada por Cliente (RN-009)
- `existe_os_para_veiculo(veiculo_id) -> bool` — usada por Cliente (exclusão de veículo preserva histórico/FK)
- `existe_os_ativa_com_item_estoque(item_estoque_id) -> bool` — usada por Estoque (RN-011)

Operações de leitura — não recebem `UnitOfWork`. O adaptador vive na infraestrutura do contexto consumidor e consulta o repositório de OS.

> **Trade-off**: essa porta reversa cria uma dependência cíclica no nível de infraestrutura (adapters). No monolito MVP, isso é aceitável — os contextos de domínio permanecem desacoplados. Em evolução para microsserviços, essa consulta seria substituída por eventos de domínio ou eventual consistency.
>
> Exceção pragmática da mesma natureza: a consulta pública de acompanhamento (`OrdemDeServicoRepository.obter_por_placa_e_documento`) é implementada na infraestrutura de OS como join somente-leitura nas tabelas `clientes` e `veiculos` do contexto vizinho — não atravessa o domínio de Cliente+Veículo nem passa pela `ClientePort`.

### Middleware (Cross-Cutting)

Autenticação é infraestrutura transversal via `Depends()` do FastAPI. Não é comunicação entre contextos de domínio — é enforcement de segurança na camada de interfaces.

## Comunicação

```mermaid
graph TD
    subgraph "Contexto Ordem de Servico"
        OS_APP[Camada de Aplicacao]
        PE[EstoquePort]
        PC[CatalogoPort]
        PCL[ClientePort]
    end
    subgraph "Contexto Cliente"
        CLI_APP[Camada de Aplicacao]
        POS_CLI[OrdemDeServicoPort]
    end
    subgraph "Contexto Estoque"
        EST_APP[Camada de Aplicacao]
        POS_EST[OrdemDeServicoPort]
    end
    subgraph "Contexto Catalogo"
        CAT_APP[Camada de Aplicacao]
    end
    subgraph "Infraestrutura OS"
        AE[EstoqueAdapter]
        AC[CatalogoAdapter]
        ACL[ClienteAdapter]
    end
    subgraph "Infraestrutura Reversa"
        AOS_CLI[OSAdapter - Cliente]
        AOS_EST[OSAdapter - Estoque]
    end

    OS_APP --> PE
    OS_APP --> PC
    OS_APP --> PCL
    PE -.-> AE
    PC -.-> AC
    PCL -.-> ACL
    AE --> EST_APP
    AC --> CAT_APP
    ACL --> CLI_APP

    CLI_APP --> POS_CLI
    EST_APP --> POS_EST
    POS_CLI -.-> AOS_CLI
    POS_EST -.-> AOS_EST
    AOS_CLI --> OS_APP
    AOS_EST --> OS_APP
```

A comunicação **síncrona** entre contextos é in-process via portas e adaptadores. Adaptadores vivem na camada de infraestrutura. A raiz de composição (`main.py`) faz o wiring de DI — único ponto que importa implementações concretas. O caminho assíncrono (notificações) é durável e cruza processos — seção a seguir.

## Integração Assíncrona (Fase 2)

A notificação ao cliente na mudança de status da OS (RF-024) sai do ciclo request/response por um caminho durável:

```mermaid
graph LR
    DE[DomainEvent] --> IE[IntegrationEvent]
    IE -->|UnitOfWork, mesma tx| OB[(outbox)]
    OB --> RL[Relay]
    RL -->|at-least-once| H[Handler de notificacao]
    H --> EP[EmailPort]
```

1. O agregado emite `DomainEvent`; os fatos que cruzam contextos são `IntegrationEvent` (especialização durável).
2. A `UnitOfWork` grava os `IntegrationEvent`s na tabela `outbox` **na mesma transação** do estado de negócio (Transactional Outbox — elimina o dual-write).
3. Um processo *relay* dedicado lê a outbox e entrega aos handlers — semântica at-least-once, com idempotência garantida pela tabela `processed_events` (única por `outbox_id` + handler).
4. O handler de notificação resolve o destinatário via `ClientePort.obter_contato` e envia pelo `EmailPort` — porta de saída para SMTP, realizada por adaptador na infraestrutura de OS.

Detalhes: [ADR-022](adr/fase2/022-transactional-outbox-relay.md) e [eventos de domínio](eventos-de-dominio.md).

## Código Compartilhado

`compartilhado/dominio/` contém:
- Classes base: `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent`
- Objeto de valor `Dinheiro` (usado por vários contextos)
- Hierarquia de exceções: `DomainException` e subclasses

Não é um Shared Kernel — é código utilitário sem regras de negócio específicas de um contexto.

> [↑ Raiz do projeto](../../README.md) · [↑ Arquitetura](README.md)
