# C4 — Diagrama de Componentes (Level 3)

> **Status**: DRAFT — documento em elaboracao, sujeito a revisao pela equipe PytStop.

Detalha os componentes internos do bounded context principal (Ordem de Servico) dentro da Aplicacao FastAPI. Os demais bounded contexts sao mostrados em nivel resumido. Baseado no modelo C4 de Simon Brown (Software Architecture — Aula 2).

## Diagrama — Contexto Ordem de Servico (Detalhado)

```mermaid
graph TB
    subgraph "Interfaces (interfaces/)"
        CTRL[OrdemDeServicoController<br/><i>FastAPI Router</i>]
        SCHEMAS[Schemas Pydantic<br/><i>Request / Response</i>]
    end

    subgraph "Aplicacao (aplicacao/)"
        UC_CRIAR[CriarOrdemDeServicoUseCase]
        UC_DIAG[IniciarDiagnosticoUseCase]
        UC_ORC[GerarOrcamentoUseCase]
        UC_APROV[AprovarOrcamentoUseCase]
        UC_FIN[FinalizarServicoUseCase]
        UC_ENTREG[RegistrarEntregaUseCase]
        UC_CANCEL[CancelarOrdemUseCase]
    end

    subgraph "Dominio (dominio/)"
        AGG[OrdemDeServico<br/><i>AggregateRoot</i>]
        ENT[ItemDaOrdem<br/><i>Entity</i>]
        VO_ORC[Orcamento<br/><i>ValueObject</i>]
        VO_LINHA[LinhaOrcamento<br/><i>ValueObject</i>]
        ENUM[StatusOrdem<br/><i>Enum — 7+1 estados</i>]
        MAQ[MaquinaDeStatus<br/><i>Colaborador stateless</i>]
        EVENTS[Domain Events<br/><i>OrcamentoAprovadoEvent, etc.</i>]
        REPO_PORT[OrdemDeServicoRepository<br/><i>Port — interface</i>]
    end

    subgraph "Infraestrutura (infraestrutura/)"
        REPO_IMPL[OrdemDeServicoRepositoryImpl<br/><i>SQLAlchemy</i>]
        CLIENTE_ADAPTER[ClienteAdapter<br/><i>implementa ClientePort</i>]
        CATALOGO_ADAPTER[CatalogoAdapter<br/><i>implementa CatalogoPort</i>]
        ESTOQUE_ADAPTER[EstoqueAdapter<br/><i>implementa EstoquePort</i>]
    end

    CTRL --> UC_CRIAR
    CTRL --> UC_DIAG
    CTRL --> UC_ORC
    CTRL --> UC_APROV
    CTRL --> UC_FIN
    CTRL --> UC_ENTREG
    CTRL --> UC_CANCEL
    CTRL --> SCHEMAS

    UC_CRIAR --> AGG
    UC_CRIAR --> REPO_PORT
    UC_DIAG --> AGG
    UC_ORC --> AGG
    UC_APROV --> AGG
    UC_FIN --> AGG
    UC_ENTREG --> AGG
    UC_ENTREG --> REPO_PORT
    UC_CANCEL --> AGG
    UC_CANCEL --> REPO_PORT

    AGG --> ENT
    AGG --> VO_ORC
    AGG --> ENUM
    AGG --> MAQ
    AGG --> EVENTS
    VO_ORC --> VO_LINHA

    REPO_PORT -.->|implementado por| REPO_IMPL
    REPO_IMPL -->|SQLAlchemy 2.0<br/>mapeamento imperativo| DB[(PostgreSQL 16)]
```

## Bounded Contexts — Visao Resumida

Os demais bounded contexts sao mostrados sem detalhar seus componentes internos. Level 3 separado por BC pode ser produzido na fase de implementacao.

```mermaid
graph LR
    subgraph "Ordem de Servico (Principal)"
        OS[OrdemDeServico<br/><i>AggregateRoot</i>]
    end

    subgraph "Cliente + Veiculo (Suporte)"
        CLI[Cliente<br/><i>AggregateRoot</i>]
        VEI[Veiculo<br/><i>Entity</i>]
    end

    subgraph "Catalogo de Servicos (Suporte)"
        SERV[ServicoOferecido<br/><i>AggregateRoot</i>]
    end

    subgraph "Estoque (Principal)"
        ITEM[ItemEstoque<br/><i>AggregateRoot</i>]
    end

    subgraph "Autenticacao (Generico)"
        USR[Usuario<br/><i>AggregateRoot</i>]
    end

    CLI -->|ClientePort<br/>Cliente-Fornecedor| OS
    SERV -->|CatalogoPort<br/>OHS / Linguagem Publicada| OS
    ITEM -->|EstoquePort<br/>OHS / Linguagem Publicada| OS
    USR -.->|middleware JWT| OS
```

## Portas e Adaptadores

### Portas do contexto Ordem de Servico (consumidor)

| Porta | Definida em | Metodos | Adaptador |
|---|---|---|---|
| `ClientePort` | `aplicacao/` de OS | `cliente_existe()`, `veiculo_existe()`, `obter_veiculo_por_placa_e_documento()` | `ClienteAdapter` em `infraestrutura/` de OS |
| `CatalogoPort` | `aplicacao/` de OS | `obter_servico()` | `CatalogoAdapter` em `infraestrutura/` de OS |
| `EstoquePort` | `aplicacao/` de OS | `reservar()`, `liberar()` | `EstoqueAdapter` em `infraestrutura/` de OS |

### Porta reversa (consumida por Cliente e Estoque)

| Porta | Definida em | Metodos | Adaptador |
|---|---|---|---|
| `OrdemDeServicoPort` | `aplicacao/` de Cliente | `existe_os_ativa_para_cliente()`, `existe_os_ativa_para_veiculo()` | `OSAdapter` em `infraestrutura/` de Cliente |
| `OrdemDeServicoPort` | `aplicacao/` de Estoque | `existe_os_ativa_com_item_estoque()` | `OSAdapter` em `infraestrutura/` de Estoque |

No diagrama resumido, `OrdemDeServicoPort` e mostrada como uma unica porta. Na implementacao, cada contexto consumidor (Cliente, Estoque) define sua propria interface com apenas os metodos que necessita — ver [mapa-contextos.md](../mapa-contextos.md).

## Rastreabilidade

- Bounded contexts: [mapa-contextos.md](../mapa-contextos.md)
- Agregados e entidades: [modelo-dominio.md](../modelo-dominio.md)
- Nomenclatura hibrida: [ADR-009](../adr/009-decisao-de-idioma.md)
- Organizacao dos contextos: [ADR-007](../adr/007-organizacao-contextos-delimitados.md)
- Arquitetura Onion: [ADR-003](../adr/003-arquitetura-ddd-onion.md)
