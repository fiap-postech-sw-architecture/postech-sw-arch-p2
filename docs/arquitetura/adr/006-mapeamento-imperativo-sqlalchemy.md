# Mapeamento imperativo do SQLAlchemy para entidades de domínio

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O DDD exige que as entidades de domínio sejam classes Python puras, sem dependência de frameworks ou ORM. O SQLAlchemy 2.0 oferece duas formas de mapeamento: declarativo (entidades herdam de `DeclarativeBase`) e imperativo (`registry.map_imperatively()`). Como mapear entidades de domínio para o banco sem acoplá-las ao SQLAlchemy?

## Decisão

Adotar o mapeamento imperativo do SQLAlchemy 2.0 via `registry.map_imperatively()`, precedido por um spike de 4 horas com critérios go/no-go.

O mapeamento imperativo permite que as entidades de domínio permaneçam como classes Python puras — sem herança de `DeclarativeBase`, sem decorators do ORM, sem imports do SQLAlchemy. A definição das tabelas e o mapeamento entre classes e tabelas ficam isolados na camada de infraestrutura (`infraestrutura/persistencia/`).

**Spike de 4 horas com critérios go/no-go:**

A decisão está condicionada a um spike técnico que deve validar os seguintes critérios antes de adotar o mapeamento imperativo em todo o projeto:

1. Relacionamentos `relationship()` funcionam entre entidades mapeadas imperativamente
2. `composite()` funciona para o Value Object `Dinheiro` (valor + moeda)
3. Colunas JSONB funcionam para persistir o agregado `Orcamento`
4. `lazy="selectin"` funciona para carregamento de coleções

Se qualquer critério falhar, o fallback é o mapeamento declarativo com entidades herdando de `DeclarativeBase`.

**Detalhes de implementação:**

- A função `iniciar_mapeamentos()` é chamada uma única vez na inicialização da aplicação
- Um guard de idempotência impede mapeamentos duplicados caso a função seja chamada mais de uma vez
- As tabelas são definidas com `Table()` explícito, separadas das classes de domínio

## Alternativas Consideradas

* Mapeamento imperativo (registry.map_imperatively)
* Mapeamento declarativo (DeclarativeBase)
* SQL puro sem ORM

### Mapeamento imperativo (registry.map_imperatively)

As entidades de domínio são classes Python puras. O mapeamento entre classes e tabelas é definido na camada de infraestrutura via `registry.map_imperatively()`.

* Bom, porque as entidades de domínio não têm nenhuma dependência do SQLAlchemy
* Bom, porque permite testar entidades de domínio sem banco de dados
* Bom, porque a separação entre domínio e persistência segue Ports & Adapters
* Ruim, porque tem menos documentação e exemplos na comunidade comparado ao declarativo
* Ruim, porque a definição de relacionamentos em `iniciar_mapeamentos()` é mais verbosa
* Ruim, porque exige guard de idempotência para evitar mapeamentos duplicados

### Mapeamento declarativo (DeclarativeBase)

As entidades herdam de `DeclarativeBase` e definem colunas como atributos de classe com `mapped_column()`.

* Bom, porque é a abordagem padrão e mais documentada do SQLAlchemy 2.0
* Bom, porque a definição de colunas e relacionamentos é concisa e familiar
* Ruim, porque acopla as entidades de domínio ao SQLAlchemy via herança
* Ruim, porque imports do SQLAlchemy vazam para a camada de domínio
* Ruim, porque dificulta testar entidades isoladamente sem o ORM carregado

### SQL puro sem ORM

Usar queries SQL diretamente nos repositórios, sem mapeamento objeto-relacional.

* Bom, porque dá controle total sobre as queries executadas
* Bom, porque não há nenhuma camada de abstração entre o código e o banco
* Ruim, porque perde os benefícios de Unit of Work e Identity Map do SQLAlchemy
* Ruim, porque exige mapeamento manual entre resultados de queries e objetos de domínio
* Ruim, porque aumenta significativamente o volume de código nos repositórios

## Consequências

### Positivas

* Entidades de domínio são classes Python puras, sem herança de ORM
* A camada de domínio não importa nada do SQLAlchemy
* Testes unitários de domínio rodam sem banco de dados e sem configuração de ORM
* A separação explícita entre domínio e persistência respeita a Arquitetura Hexagonal

### Negativas

* Menos exemplos e documentação na comunidade para o padrão imperativo
* A função `iniciar_mapeamentos()` concentra toda a configuração de relacionamentos, podendo ficar extensa
* O guard de idempotência adiciona complexidade na inicialização
* Desenvolvedores familiarizados apenas com o declarativo precisarão de tempo de adaptação

## Decisões Relacionadas

- [ADR-003](003-arquitetura-ddd-onion.md): DDD com Arquitetura Onion — o mapeamento imperativo é a técnica que viabiliza o isolamento do domínio exigido pela Onion Architecture
- [ADR-002](002-banco-postgresql.md): PostgreSQL como banco de dados — o mapeamento imperativo usa Table() com tipos específicos do PostgreSQL (ENUM, JSONB)
