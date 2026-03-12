# Bloqueio pessimista para reserva de estoque

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

Quando multiplas Ordens de Servico sao aprovadas simultaneamente, elas podem tentar reservar as mesmas pecas do estoque. Sem controle de concorrencia, o sistema pode aprovar reservas que excedem a quantidade disponivel. Como garantir a atomicidade da reserva de estoque sob concorrencia?

## Decisao

Adotar bloqueio pessimista com `SELECT FOR UPDATE NOWAIT` sobre `ItemEstoque`, com ordenacao de locks e transacao unica compartilhada entre OS e Estoque.

**Mecanismo:**

1. Ao aprovar uma OS que consome pecas, o sistema executa `SELECT FOR UPDATE NOWAIT` nos registros de `ItemEstoque` envolvidos
2. Se algum item ja estiver bloqueado por outra transacao, o `NOWAIT` faz a operacao falhar imediatamente em vez de aguardar, levantando `EstoqueInsuficienteException`
3. Se todos os itens estiverem disponiveis e em quantidade suficiente, a reserva e efetuada atomicamente

**Prevencao de deadlock:**

Todos os locks sao adquiridos em ordem crescente de `item_id`, independentemente da ordem em que os itens aparecem na OS. Isso garante que duas transacoes concorrentes nunca adquiram locks em ordens opostas, eliminando deadlocks por definicao.

**Atomicidade com UnitOfWork compartilhado:**

A reserva de estoque e a atualizacao do status da OS compartilham o mesmo `UnitOfWork`. Se a reserva falhar, a OS nao avanca de status. Se a OS falhar apos a reserva, o estoque e revertido. Tudo acontece em uma unica transacao.

**Semantica all-or-nothing:**

Ou todos os itens da OS sao reservados com sucesso, ou nenhum e reservado. Nao ha reserva parcial.

## Alternativas Consideradas

* SELECT FOR UPDATE NOWAIT (bloqueio pessimista)
* Locking otimista com coluna de versao
* Mutex na camada de aplicacao

### SELECT FOR UPDATE NOWAIT (bloqueio pessimista)

Bloqueia as linhas de `ItemEstoque` no banco durante a transacao, falhando imediatamente se o lock nao puder ser adquirido.

* Bom, porque garante consistencia forte — nao ha janela para oversell
* Bom, porque o modelo mental e simples: quem chega primeiro reserva
* Bom, porque a ordenacao por `item_id` elimina deadlocks por construcao
* Bom, porque `NOWAIT` falha rapido em vez de bloquear threads indefinidamente
* Ruim, porque gera contencao sob alta concorrencia (aceitavel para escala de oficina mecanica)

### Locking otimista com coluna de versao

Cada `ItemEstoque` tem uma coluna `versao`. Ao atualizar, o sistema verifica se a versao nao mudou desde a leitura.

* Bom, porque nao bloqueia linhas no banco durante a leitura
* Bom, porque funciona bem quando colisoes sao raras
* Ruim, porque exige logica de retry quando a versao diverge
* Ruim, porque o retry para multiplos itens e complexo — todos os itens precisam ser re-verificados a cada tentativa
* Ruim, porque sob concorrencia moderada os retries degradam a experiencia do usuario

### Mutex na camada de aplicacao

Lock em memoria (ou distribuido) na camada de aplicacao para serializar acessos ao estoque.

* Bom, porque e simples de implementar em uma unica instancia
* Ruim, porque nao funciona com multiplas instancias da aplicacao
* Ruim, porque um mutex distribuido (Redis, ZooKeeper) adiciona infraestrutura e complexidade
* Ruim, porque serializa todas as operacoes de estoque, mesmo as que nao competem pelos mesmos itens

## Consequencias

### Positivas

* Consistencia forte garantida pelo banco de dados — impossivel aprovar reservas que excedam o estoque
* Modelo mental simples para desenvolvedores: lock, verifica, reserva ou falha
* Deadlock eliminado por construcao graças a ordenacao por `item_id`
* Fail-fast com `NOWAIT` evita threads bloqueadas e timeouts longos
* Atomicidade garantida pelo `UnitOfWork` compartilhado entre OS e Estoque

### Negativas

* Contencao sob alta concorrencia em itens populares (aceitavel para a escala de uma oficina mecanica no MVP)
* Depende de funcionalidade especifica do PostgreSQL (`SELECT FOR UPDATE NOWAIT`) — nao portavel para bancos que nao suportam essa sintaxe
* O `UnitOfWork` compartilhado entre BCs (OS e Estoque) cria acoplamento transacional que pode precisar ser revisado em arquiteturas distribuidas futuras
