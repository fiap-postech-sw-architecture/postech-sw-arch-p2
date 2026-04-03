# Organização dos contextos delimitados do domínio

* Status: Aceita
* Data: 2026-03-20

## Contexto e Problema

O sistema de oficina mecânica precisa de fronteiras claras entre seus subdomínios. Como organizar os Bounded Contexts para refletir a realidade do negócio, manter o acoplamento baixo entre contextos e definir quais contextos são de domínio principal?

## Decisão

Organizar o domínio em 5 Bounded Contexts:

| Bounded Context | Tipo | Responsabilidade |
|---|---|---|
| **Cliente + Veiculo** | Suporte | Cadastro de clientes e seus veículos |
| **Catalogo de Servicos** | Suporte | Serviços oferecidos pela oficina, com ciclo de vida próprio (ativação/desativação) |
| **Estoque** | Principal | Peças e insumos disponíveis, com controle de quantidade e reserva |
| **Ordem de Servico** | Principal | Fluxo completo da OS: abertura, diagnóstico, orçamento, aprovação, execução, conclusão |
| **Autenticação** | Genérico | Autenticação e autorização via JWT |

### Classificação dos Subdomínios

A classificação segue a árvore de decisão de subdomínios (Aula 01 — Introdução à DDD). A coluna "Comprável?" indica se a solução poderia ser substituída por produto de mercado — critério que distingue Genérico dos demais tipos.

| Bounded Context | Comprável? | Critério | Classificação |
|---|---|---|---|
| Ordem de Serviço | Não | Lógica complexa: máquina de estados com 8 status (7 base + AguardandoAprovacaoComplementar via RF-016), orçamento e orquestração cross-contexto | **Principal** |
| Cliente + Veículo | Não | Lógica simples: cadastro com validação de CPF/CNPJ | Suporte |
| Catálogo de Serviços | Não | Lógica simples: CRUD com ativação/desativação | Suporte |
| Estoque | Não | Lógica não-trivial: reserva pessimista com SELECT FOR UPDATE NOWAIT na transição AguardandoAprovacao→EmExecucao | **Principal** |
| Autenticação | Sim | Substituível sem impacto no domínio | Genérico |

> **Trade-off documentado — Estoque como Principal:**
>
> Pela teoria de DDD (Evans, Vernon), estoque de peças seria Suporte — não gera vantagem competitiva direta. Neste projeto, foi promovido a Principal por três razões:
>
> 1. O Tech Challenge exige Event Storming dedicado para "Gestão de peças e insumos"
> 2. Reserva pessimista com `SELECT FOR UPDATE NOWAIT` introduz complexidade de domínio real (ADR-008)
> 3. Para uma oficina de médio porte, falta de peça trava o elevador e bloqueia capacidade produtiva
>
> Consequência: aumenta a superfície de testes (90% vs 80%) mas reflete a importância operacional do contexto.

**Veículo dentro de Cliente:**

Veículos não têm ciclo de vida independente do cliente. Um veículo não existe no sistema sem um cliente associado. Por isso, `Veiculo` é uma entidade dentro do Bounded Context de `Cliente`, não um BC separado.

**Catalogo de Servicos como BC separado:**

`ServicoOferecido` não é uma propriedade da Ordem de Servico. O catálogo tem ciclo de vida próprio — serviços podem ser ativados, desativados e ter preço atualizado independentemente de qualquer OS. A Ordem de Servico referencia itens do catálogo, mas não os controla.

**Status Cancelada e AguardandoAprovacaoComplementar:**

O Tech Challenge define 6 status para a OS. A decisão inclui `Cancelada` como sétimo status para cobrir dois cenários que não têm saída nos 6 status originais:

1. Cliente rejeita o orçamento — a OS precisa de um estado terminal
2. Veículo abandonado — após período sem contato, a oficina precisa encerrar a OS

Sem `Cancelada`, a OS ficaria presa em um estado intermediário indefinidamente.

O oitavo status (`AguardandoAprovacaoComplementar`, via RF-016) suporta serviços adicionais descobertos durante a execução.

## Alternativas Consideradas

* 5 BCs (Cliente+Veiculo, Catalogo, Estoque, OS, Autenticação)
* Veículo como BC separado
* Apenas 6 status (sem Cancelada)

### 5 BCs (Cliente+Veiculo, Catalogo, Estoque, OS, Autenticação)

Organização com Veículo dentro do BC de Cliente, Catálogo como BC próprio e Cancelada como status adicional.

* Bom, porque reflete a realidade do negócio — veículos pertencem a clientes
* Bom, porque o Catálogo tem autonomia para evoluir sem afetar a OS
* Bom, porque Cancelada resolve cenários reais de rejeição e abandono
* Ruim, porque o Value Object `Dinheiro` é compartilhado entre BCs, podendo evoluir para Shared Kernel

### Veículo como BC separado

Tratar Veículo como um Bounded Context independente, com seu próprio repositório e ciclo de vida.

* Bom, porque isola completamente a lógica de veículos
* Ruim, porque veículos não têm ciclo de vida independente do cliente no domínio da oficina
* Ruim, porque aumenta a complexidade de integração entre BCs sem benefício real
* Ruim, porque cria um BC artificial para uma entidade que é naturalmente subordinada ao cliente

### Apenas 6 status (sem Cancelada)

Manter apenas os 6 status definidos no enunciado do Tech Challenge, sem adicionar Cancelada.

* Bom, porque segue estritamente o enunciado do Tech Challenge
* Ruim, porque não há caminho de saída para orçamento rejeitado pelo cliente
* Ruim, porque veículos abandonados mantêm a OS em estado intermediário indefinidamente
* Ruim, porque a oficina não consegue encerrar OSs que não vão progredir

## Consequências

### Positivas

* Fronteiras claras entre contextos, com dois domínios principais (Ordem de Servico e Estoque)
* Complexidade gerenciável — 5 BCs é suficiente para o escopo do MVP sem fragmentação excessiva
* Veículo dentro de Cliente simplifica o modelo e reflete a realidade do negócio
* Catálogo separado permite evolução independente de preços e serviços oferecidos
* Cancelada resolve cenários reais sem forçar o domínio a estados inconsistentes

### Negativas

* O Value Object `Dinheiro` é usado em múltiplos BCs (Catalogo, Estoque, OS), podendo se tornar um Shared Kernel se divergir entre contextos
* A comunicação entre BCs exige contratos claros (eventos de domínio ou interfaces anti-corrupção)
* Cancelada e AguardandoAprovacaoComplementar divergem do enunciado original (6 status) — justificativa documentada neste ADR

## Decisões Relacionadas

- [ADR-003](003-arquitetura-ddd-onion.md): DDD com Arquitetura Onion — os Bounded Contexts são organizados dentro da estrutura de camadas Onion
- [ADR-008](008-bloqueio-pessimista-estoque.md): Bloqueio pessimista — detalha a complexidade técnica que justifica Estoque como domínio Principal
