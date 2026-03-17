# Modelo de Domínio

Diagramas de classes por agregado.

## Agregado: OrdemDeServico (Principal)

```mermaid
classDiagram
    class OrdemDeServico {
        <<AggregateRoot>>
        -id: UUID
        -cliente_id: UUID
        -veiculo_id: UUID
        -status: StatusOrdem
        -itens: list~ItemDaOrdem~
        -orcamento: Orcamento | None
        -criado_em: datetime
        -atualizado_em: datetime
        +iniciar_diagnostico()
        +gerar_orcamento()
        +aprovar_orcamento()
        +finalizar_servico()
        +registrar_entrega()
        +cancelar(motivo: str | None)
        +gerar_orcamento_complementar()
        +aprovar_orcamento_complementar()
        +rejeitar_orcamento_complementar()
        +adicionar_item(item: ItemDaOrdem)
        +remover_item(item_id: UUID)
    }

    class ItemDaOrdem {
        <<Entity>>
        -id: UUID
        -servico_catalogo_id: UUID
        -item_estoque_id: UUID | None
        -descricao: str
        -quantidade: int
        -preco_unitario: Dinheiro
    }

    class Orcamento {
        <<ValueObject>>
        -itens: tuple~LinhaOrcamento~
        -total: Dinheiro
        -gerado_em: datetime
        -versao_schema: int
    }

    class LinhaOrcamento {
        <<ValueObject>>
        -descricao: str
        -quantidade: int
        -preco_unitario: Dinheiro
        -subtotal: Dinheiro
    }

    class StatusOrdem {
        <<Enum>>
        Recebida
        EmDiagnostico
        AguardandoAprovacao
        EmExecucao
        Finalizada
        Entregue
        Cancelada
        AguardandoAprovacaoComplementar
        +transicoes_validas() dict
    }

    class MaquinaDeStatus {
        <<Colaborador>>
        +transicionar_para(atual, novo, contexto) tuple
        +transicoes_validas(status) set
    }

    OrdemDeServico *-- ItemDaOrdem : contém
    OrdemDeServico *-- Orcamento : possui
    OrdemDeServico --> StatusOrdem : status
    OrdemDeServico --> MaquinaDeStatus : delega
    Orcamento *-- LinhaOrcamento : itens
```

## Agregado: Cliente (Suporte)

```mermaid
classDiagram
    class Cliente {
        <<AggregateRoot>>
        -id: UUID
        -nome: str
        -documento: Documento
        -contato: str
        -veiculos: list~Veiculo~
        -ativo: bool
        +adicionar_veiculo(placa, marca, modelo, ano)
        +remover_veiculo(veiculo_id: UUID)
    }

    class Veiculo {
        <<Entity>>
        -id: UUID
        -placa: Placa
        -marca: str
        -modelo: str
        -ano: int
    }

    class CPF {
        <<ValueObject>>
        -numero: str
        +formatado() str
        +mascarado() str
    }

    class CNPJ {
        <<ValueObject>>
        -numero: str
        +formatado() str
        +mascarado() str
    }

    class Placa {
        <<ValueObject>>
        -valor: str
    }

    class Documento {
        <<Protocol>>
        +formatado() str
        +mascarado() str
    }

    Cliente *-- Veiculo : possui
    Cliente --> Documento : documento
    CPF ..|> Documento : implementa
    CNPJ ..|> Documento : implementa
    Veiculo --> Placa : placa
```

## Agregado: ItemEstoque (Principal)

```mermaid
classDiagram
    class ItemEstoque {
        <<AggregateRoot>>
        -id: UUID
        -nome: str
        -descricao: str
        -quantidade: int
        -preco_unitario: Dinheiro
        -ativo: bool
        +reservar(qtd: int)
        +liberar(qtd: int)
    }

    class Dinheiro {
        <<ValueObject>>
        -valor: Decimal
        -moeda: str
        +__add__(outro: Dinheiro) Dinheiro
        +__sub__(outro: Dinheiro) Dinheiro
        +__mul__(fator: int) Dinheiro
        +__rmul__(fator: int) Dinheiro
    }

    ItemEstoque --> Dinheiro : preco_unitario
```

## Agregado: ServicoOferecido (Suporte)

```mermaid
classDiagram
    class ServicoOferecido {
        <<AggregateRoot>>
        -id: UUID
        -nome: str
        -descricao: str
        -preco: Dinheiro
        -ativo: bool
    }

    ServicoOferecido --> Dinheiro : preco
```

## Agregado: Usuario (Genérico)

```mermaid
classDiagram
    class Usuario {
        <<AggregateRoot>>
        -id: UUID
        -email: str
        -senha_hash: str
        -papel: Papel
    }

    class Papel {
        <<Enum>>
        Admin
    }

    Usuario --> Papel : papel
```

## Classes Base (Compartilhado)

```mermaid
classDiagram
    class Entity {
        <<Abstract>>
        #id: UUID
        +__eq__(outro) bool
        +__hash__() int
    }

    class AggregateRoot {
        <<Abstract>>
        #_eventos_pendentes: list~DomainEvent~
        +coletar_eventos() list
        +limpar_eventos()
    }

    class ValueObject {
        <<Abstract, frozen>>
        +__eq__(outro) bool
        +__hash__() int
    }

    class DomainEvent {
        <<Abstract, frozen>>
        +ocorrido_em: datetime
        +agregado_id: UUID
    }

    AggregateRoot --|> Entity : estende
```

## Referências entre Agregados

Agregados referenciam-se exclusivamente por ID (UUID), nunca por referência direta:

| Agregado Origem | Campo | Agregado Destino |
|---|---|---|
| `OrdemDeServico` | `cliente_id: UUID` | `Cliente` |
| `OrdemDeServico` | `veiculo_id: UUID` | `Veiculo` (via Cliente) |
| `ItemDaOrdem` | `servico_catalogo_id: UUID` | `ServicoOferecido` |
| `ItemDaOrdem` | `item_estoque_id: UUID \| None` | `ItemEstoque` |

A comunicação cross-agregado acontece via portas na camada de aplicação (`EstoquePort`, `CatalogoPort`, `ClientePort`), nunca por referência direta entre entidades de domínio.
