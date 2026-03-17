# Bloqueio pessimista para reserva de estoque

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

Quando múltiplas Ordens de Servico são aprovadas simultaneamente, elas podem tentar reservar as mesmas peças do estoque. Sem controle de concorrência, o sistema pode aprovar reservas que excedem a quantidade disponível. Como garantir a atomicidade da reserva de estoque sob concorrência?

## Decisão

Adotar bloqueio pessimista com `SELECT FOR UPDATE NOWAIT` sobre `ItemEstoque`, com ordenação de locks e transação única compartilhada entre OS e Estoque.

**Mecanismo:**

1. Ao aprovar uma OS que consome peças, o sistema executa `SELECT FOR UPDATE NOWAIT` nos registros de `ItemEstoque` envolvidos
2. Se algum item já estiver bloqueado por outra transação, o `NOWAIT` faz a operação falhar imediatamente em vez de aguardar, levantando `EstoqueInsuficienteException`
3. Se todos os itens estiverem disponíveis e em quantidade suficiente, a reserva é efetuada atomicamente

**Prevenção de deadlock:**

Todos os locks são adquiridos em ordem crescente de `item_id`, independentemente da ordem em que os itens aparecem na OS. Isso garante que duas transações concorrentes nunca adquiram locks em ordens opostas, eliminando deadlocks por definição.

**Atomicidade com UnitOfWork compartilhado:**

A reserva de estoque e a atualização do status da OS compartilham o mesmo `UnitOfWork`. Se a reserva falhar, a OS não avança de status. Se a OS falhar após a reserva, o estoque é revertido. Tudo acontece em uma única transação.

**Semântica all-or-nothing:**

Ou todos os itens da OS são reservados com sucesso, ou nenhum é reservado. Não há reserva parcial.

## Alternativas Consideradas

* SELECT FOR UPDATE NOWAIT (bloqueio pessimista)
* Locking otimista com coluna de versão
* Mutex na camada de aplicação

### SELECT FOR UPDATE NOWAIT (bloqueio pessimista)

Bloqueia as linhas de `ItemEstoque` no banco durante a transação, falhando imediatamente se o lock não puder ser adquirido.

* Bom, porque garante consistência forte — não há janela para oversell
* Bom, porque o modelo mental é simples: quem chega primeiro reserva
* Bom, porque a ordenação por `item_id` elimina deadlocks por construção
* Bom, porque `NOWAIT` falha rápido em vez de bloquear threads indefinidamente
* Ruim, porque gera contenção sob alta concorrência (aceitável para escala de oficina mecânica)

### Locking otimista com coluna de versão

Cada `ItemEstoque` tem uma coluna `versao`. Ao atualizar, o sistema verifica se a versão não mudou desde a leitura.

* Bom, porque não bloqueia linhas no banco durante a leitura
* Bom, porque funciona bem quando colisões são raras
* Ruim, porque exige lógica de retry quando a versão diverge
* Ruim, porque o retry para múltiplos itens é complexo — todos os itens precisam ser re-verificados a cada tentativa
* Ruim, porque sob concorrência moderada os retries degradam a experiência do usuário

### Mutex na camada de aplicação

Lock em memória (ou distribuído) na camada de aplicação para serializar acessos ao estoque.

* Bom, porque é simples de implementar em uma única instância
* Ruim, porque não funciona com múltiplas instâncias da aplicação
* Ruim, porque um mutex distribuído (Redis, ZooKeeper) adiciona infraestrutura e complexidade
* Ruim, porque serializa todas as operações de estoque, mesmo as que não competem pelos mesmos itens

## Consequências

### Positivas

* Consistência forte garantida pelo banco de dados — impossível aprovar reservas que excedam o estoque
* Modelo mental simples para desenvolvedores: lock, verifica, reserva ou falha
* Deadlock eliminado por construção graças à ordenação por `item_id`
* Fail-fast com `NOWAIT` evita threads bloqueadas e timeouts longos
* Atomicidade garantida pelo `UnitOfWork` compartilhado entre OS e Estoque

### Negativas

* Contenção sob alta concorrência em itens populares (aceitável para a escala de uma oficina mecânica no MVP)
* Depende de funcionalidade específica do PostgreSQL (`SELECT FOR UPDATE NOWAIT`) — não portável para bancos que não suportam essa sintaxe
* O `UnitOfWork` compartilhado entre BCs (OS e Estoque) cria acoplamento transacional que pode precisar ser revisado em arquiteturas distribuídas futuras

## Decisões Relacionadas

- [ADR-002](002-banco-postgresql.md): PostgreSQL como banco de dados — `SELECT FOR UPDATE NOWAIT` é funcionalidade específica do PostgreSQL
- [ADR-007](007-organizacao-contextos-delimitados.md): Organização dos contextos delimitados — a complexidade do bloqueio pessimista justifica Estoque como domínio Principal
