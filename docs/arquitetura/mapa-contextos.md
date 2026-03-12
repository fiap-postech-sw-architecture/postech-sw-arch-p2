# Mapa de Contextos

Representação dos 5 contextos delimitados e seus padrões de integração, conforme definido no [ADR-007](adr/007-organizacao-contextos-delimitados.md).

## Diagrama

```mermaid
graph LR
    subgraph Nucleo
        OS[Ordem de Servico<br/><i>Core Domain</i>]
    end
    subgraph Suporte
        C[Cliente + Veiculo<br/><i>Suporte</i>]
        CS[Catalogo de Servicos<br/><i>Suporte</i>]
        E[Estoque<br/><i>Suporte</i>]
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
| **Ordem de Serviço** | Core | `OrdemDeServico` | Ciclo de vida da OS (7 status), geração de orçamento, orquestração cross-contexto |
| **Cliente + Veículo** | Suporte | `Cliente`, `Veiculo` | Cadastro e validação de clientes (CPF/CNPJ) e seus veículos |
| **Catálogo de Serviços** | Suporte | `ServicoOferecido` | Tipos de serviço disponíveis com preços |
| **Estoque** | Suporte | `ItemEstoque` | Peças e insumos com reserva pessimista e controle de quantidade |
| **Autenticação** | Genérico | `Usuario` | JWT, credenciais, RBAC. Substituível por Auth0/Keycloak. |

## Padrões de Integração

### Cliente-Fornecedor (Customer-Supplier)

**Fornecedor**: Cliente + Veículo
**Consumidor**: Ordem de Serviço

O contexto Cliente fornece dados para a criação de OS. A porta `ClientePort` (definida pelo consumidor) expõe:
- `cliente_existe(cliente_id) -> bool`
- `veiculo_existe(veiculo_id) -> bool`
- `obter_veiculo_por_placa_e_documento(placa, documento) -> tuple[UUID, UUID] | None`

Operações de leitura — não recebem `UnitOfWork`.

### Open Host Service (OHS) / Linguagem Publicada

**Fornecedores**: Catálogo de Serviços, Estoque
**Consumidor**: Ordem de Serviço

Catálogo expõe serviços via `CatalogoPort`:
- `obter_servico(servico_id) -> ServicoOferecidoDTO | None`

Estoque expõe reserva/liberação via `EstoquePort`:
- `reservar(itens, udt) -> None` — recebe `UnitOfWork` para atomicidade
- `liberar(itens, udt) -> None` — recebe `UnitOfWork` para atomicidade

A Linguagem Publicada é o `ServicoOferecidoDTO` — tipo compartilhado que desacopla os contextos.

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
    subgraph "Infraestrutura"
        AE[EstoqueAdapter]
        AC[CatalogoAdapter]
        ACL[ClienteAdapter]
    end
    subgraph "Outros Contextos"
        EST[Estoque - Camada App]
        CAT[Catalogo - Camada App]
        CLI[Cliente - Camada App]
    end

    OS_APP --> PE
    OS_APP --> PC
    OS_APP --> PCL
    PE -.-> AE
    PC -.-> AC
    PCL -.-> ACL
    AE --> EST
    AC --> CAT
    ACL --> CLI
```

Toda comunicação é in-process via portas e adaptadores. Adaptadores vivem na camada de infraestrutura. A raiz de composição (`main.py`) faz o wiring de DI — único ponto que importa implementações concretas.

## Código Compartilhado

`compartilhado/dominio/` contém:
- Classes base: `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent`
- Objeto de valor `Dinheiro` (usado por vários contextos)
- Hierarquia de exceções: `DomainException` e subclasses

Não é um Shared Kernel — é código utilitário sem regras de negócio específicas de um contexto.
