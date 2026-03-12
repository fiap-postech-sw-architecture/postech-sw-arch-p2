# Mapeamento imperativo do SQLAlchemy para entidades de dominio

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O DDD exige que as entidades de dominio sejam classes Python puras, sem dependencia de frameworks ou ORM. O SQLAlchemy 2.0 oferece duas formas de mapeamento: declarativo (entidades herdam de `DeclarativeBase`) e imperativo (`registry.map_imperatively()`). Como mapear entidades de dominio para o banco sem acopla-las ao SQLAlchemy?

## Decisao

Adotar o mapeamento imperativo do SQLAlchemy 2.0 via `registry.map_imperatively()`, precedido por um spike de 4 horas com criterios go/no-go.

O mapeamento imperativo permite que as entidades de dominio permaneçam como classes Python puras — sem heranca de `DeclarativeBase`, sem decorators do ORM, sem imports do SQLAlchemy. A definicao das tabelas e o mapeamento entre classes e tabelas ficam isolados na camada de infraestrutura (`infraestrutura/persistencia/`).

**Spike de 4 horas com criterios go/no-go:**

A decisao esta condicionada a um spike tecnico que deve validar os seguintes criterios antes de adotar o mapeamento imperativo em todo o projeto:

1. Relacionamentos `relationship()` funcionam entre entidades mapeadas imperativamente
2. `composite()` funciona para o Value Object `Dinheiro` (valor + moeda)
3. Colunas JSONB funcionam para persistir o agregado `Orcamento`
4. `lazy="selectin"` funciona para carregamento de colecoes

Se qualquer criterio falhar, o fallback e o mapeamento declarativo com entidades herdando de `DeclarativeBase`.

**Detalhes de implementacao:**

- A funcao `iniciar_mapeamentos()` e chamada uma unica vez na inicializacao da aplicacao
- Um guard de idempotencia impede mapeamentos duplicados caso a funcao seja chamada mais de uma vez
- As tabelas sao definidas com `Table()` explicito, separadas das classes de dominio

## Alternativas Consideradas

* Mapeamento imperativo (registry.map_imperatively)
* Mapeamento declarativo (DeclarativeBase)
* SQL puro sem ORM

### Mapeamento imperativo (registry.map_imperatively)

As entidades de dominio sao classes Python puras. O mapeamento entre classes e tabelas e definido na camada de infraestrutura via `registry.map_imperatively()`.

* Bom, porque as entidades de dominio nao tem nenhuma dependencia do SQLAlchemy
* Bom, porque permite testar entidades de dominio sem banco de dados
* Bom, porque a separacao entre dominio e persistencia segue Ports & Adapters
* Ruim, porque tem menos documentacao e exemplos na comunidade comparado ao declarativo
* Ruim, porque a definicao de relacionamentos em `iniciar_mapeamentos()` e mais verbosa
* Ruim, porque exige guard de idempotencia para evitar mapeamentos duplicados

### Mapeamento declarativo (DeclarativeBase)

As entidades herdam de `DeclarativeBase` e definem colunas como atributos de classe com `mapped_column()`.

* Bom, porque e a abordagem padrao e mais documentada do SQLAlchemy 2.0
* Bom, porque a definicao de colunas e relacionamentos e concisa e familiar
* Ruim, porque acopla as entidades de dominio ao SQLAlchemy via heranca
* Ruim, porque imports do SQLAlchemy vazam para a camada de dominio
* Ruim, porque dificulta testar entidades isoladamente sem o ORM carregado

### SQL puro sem ORM

Usar queries SQL diretamente nos repositorios, sem mapeamento objeto-relacional.

* Bom, porque da controle total sobre as queries executadas
* Bom, porque nao ha nenhuma camada de abstracao entre o codigo e o banco
* Ruim, porque perde os beneficios de Unit of Work e Identity Map do SQLAlchemy
* Ruim, porque exige mapeamento manual entre resultados de queries e objetos de dominio
* Ruim, porque aumenta significativamente o volume de codigo nos repositorios

## Consequencias

### Positivas

* Entidades de dominio sao classes Python puras, sem heranca de ORM
* A camada de dominio nao importa nada do SQLAlchemy
* Testes unitarios de dominio rodam sem banco de dados e sem configuracao de ORM
* A separacao explicita entre dominio e persistencia respeita a Arquitetura Hexagonal

### Negativas

* Menos exemplos e documentacao na comunidade para o padrao imperativo
* A funcao `iniciar_mapeamentos()` concentra toda a configuracao de relacionamentos, podendo ficar extensa
* O guard de idempotencia adiciona complexidade na inicializacao
* Desenvolvedores familiarizados apenas com o declarativo precisarao de tempo de adaptacao
