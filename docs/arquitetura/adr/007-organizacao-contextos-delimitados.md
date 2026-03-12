# Organizacao dos contextos delimitados do dominio

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O sistema de oficina mecanica precisa de fronteiras claras entre seus subdominios. Como organizar os Bounded Contexts para refletir a realidade do negocio, manter o acoplamento baixo entre contextos e definir qual e o dominio core do projeto?

## Decisao

Organizar o dominio em 5 Bounded Contexts com responsabilidades bem definidas:

| Bounded Context | Tipo | Responsabilidade |
|---|---|---|
| **Cliente + Veiculo** | Suporte | Cadastro de clientes e seus veiculos |
| **Catalogo de Servicos** | Suporte | Servicos oferecidos pela oficina, com ciclo de vida proprio (ativacao/desativacao) |
| **Estoque** | Suporte | Pecas e insumos disponiveis, com controle de quantidade e reserva |
| **Ordem de Servico** | Core | Fluxo completo da OS: abertura, diagnostico, orcamento, aprovacao, execucao, conclusao |
| **Autenticacao** | Generico | Autenticacao e autorizacao via JWT |

**Veiculo dentro de Cliente:**

Veiculos nao tem ciclo de vida independente do cliente. Um veiculo nao existe no sistema sem um cliente associado. Por isso, `Veiculo` e uma entidade dentro do Bounded Context de `Cliente`, nao um BC separado.

**Catalogo de Servicos como BC separado:**

`ServicoOferecido` nao e uma propriedade da Ordem de Servico. O catalogo tem ciclo de vida proprio — servicos podem ser ativados, desativados e ter preco atualizado independentemente de qualquer OS. A Ordem de Servico referencia itens do catalogo, mas nao os controla.

**Status Cancelada como 7o status:**

O Tech Challenge define 6 status para a OS. A decisao inclui `Cancelada` como 7o status para cobrir dois cenarios que nao tem saida nos 6 status originais:

1. Cliente rejeita o orcamento — a OS precisa de um estado terminal
2. Veiculo abandonado — apos periodo sem contato, a oficina precisa encerrar a OS

Sem `Cancelada`, a OS ficaria presa em um estado intermediario indefinidamente.

## Alternativas Consideradas

* 5 BCs (Cliente+Veiculo, Catalogo, Estoque, OS, Autenticacao)
* Veiculo como BC separado
* Apenas 6 status (sem Cancelada)

### 5 BCs (Cliente+Veiculo, Catalogo, Estoque, OS, Autenticacao)

Organizacao com Veiculo dentro do BC de Cliente, Catalogo como BC proprio e Cancelada como status adicional.

* Bom, porque reflete a realidade do negocio — veiculos pertencem a clientes
* Bom, porque o Catalogo tem autonomia para evoluir sem afetar a OS
* Bom, porque Cancelada resolve cenarios reais de rejeicao e abandono
* Ruim, porque o Value Object `Dinheiro` e compartilhado entre BCs, podendo evoluir para Shared Kernel

### Veiculo como BC separado

Tratar Veiculo como um Bounded Context independente, com seu proprio repositorio e ciclo de vida.

* Bom, porque isola completamente a logica de veiculos
* Ruim, porque veiculos nao tem ciclo de vida independente do cliente no dominio da oficina
* Ruim, porque aumenta a complexidade de integracao entre BCs sem beneficio real
* Ruim, porque cria um BC artificial para uma entidade que e naturalmente subordinada ao cliente

### Apenas 6 status (sem Cancelada)

Manter apenas os 6 status definidos no enunciado do Tech Challenge, sem adicionar Cancelada.

* Bom, porque segue estritamente o enunciado do Tech Challenge
* Ruim, porque nao ha caminho de saida para orcamento rejeitado pelo cliente
* Ruim, porque veiculos abandonados mantem a OS em estado intermediario indefinidamente
* Ruim, porque a oficina nao consegue encerrar OSs que nao vao progredir

## Consequencias

### Positivas

* Fronteiras claras entre contextos, com um unico dominio core (Ordem de Servico)
* Complexidade gerenciavel — 5 BCs e suficiente para o escopo do MVP sem fragmentacao excessiva
* Veiculo dentro de Cliente simplifica o modelo e reflete a realidade do negocio
* Catalogo separado permite evolucao independente de precos e servicos oferecidos
* Cancelada resolve cenarios reais sem forcar o dominio a estados inconsistentes

### Negativas

* O Value Object `Dinheiro` e usado em multiplos BCs (Catalogo, Estoque, OS), podendo se tornar um Shared Kernel se divergir entre contextos
* A comunicacao entre BCs exige contratos claros (eventos de dominio ou interfaces anti-corrupcao)
* A inclusao de Cancelada como 7o status precisa ser justificada explicitamente na entrega do Tech Challenge
