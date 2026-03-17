# Usar DDD com Arquitetura Onion

* Status: Proposta
* Data: 2026-03-11

## Contexto e Problema

O Tech Challenge da FIAP permite uma arquitetura simples em camadas: "é possível criar um Monolito utilizando a arquitetura em camadas". No entanto, o curso avalia conhecimento em Domain-Driven Design. Qual arquitetura adotar para demonstrar domínio de DDD e ao mesmo tempo manter o projeto viável para o escopo de MVP?

## Decisão

Adotar DDD com Arquitetura Onion, organizada em quatro camadas concêntricas:

1. **`dominio/`** — Entidades, Value Objects, Aggregates, Domain Events, Repository ports (interfaces)
2. **`aplicacao/`** — Use Cases (Application Services), DTOs de entrada/saída, orquestração
3. **`infraestrutura/`** — Implementações de Repository, mapeamento SQLAlchemy, adapters externos
4. **`interfaces/`** — Controllers FastAPI, schemas Pydantic de request/response, middlewares

A regra de dependência é estrita: camadas externas dependem das internas, nunca o inverso. O domínio não tem dependência de nenhuma outra camada.

## Alternativas Consideradas

* DDD com Arquitetura Onion
* Arquitetura em camadas simples
* Arquitetura Hexagonal (Ports & Adapters)

### DDD com Arquitetura Onion

Arquitetura em camadas concêntricas onde o domínio ocupa o centro e todas as dependências apontam para dentro.

* Bom, porque demonstra domínio de DDD, agregando valor pedagógico ao Tech Challenge
* Bom, porque isola completamente o domínio de frameworks e infraestrutura
* Bom, porque facilita testes unitários do domínio sem dependências externas
* Bom, porque a inversão de dependências permite trocar infraestrutura sem alterar regras de negócio
* Ruim, porque adiciona complexidade estrutural além do necessário para o escopo de MVP
* Ruim, porque exige disciplina para manter a regra de dependência em equipe

### Arquitetura em camadas simples

Três camadas lineares (apresentação, negócio, dados) com dependências de cima para baixo.

* Bom, porque é simples de implementar e entender
* Bom, porque é suficiente para o escopo funcional do MVP
* Bom, porque é explicitamente permitida pelo enunciado do Tech Challenge
* Ruim, porque não demonstra conhecimento de DDD, perdendo crédito na avaliação
* Ruim, porque a camada de negócio tende a acoplar-se ao ORM com o tempo
* Ruim, porque dificulta testes unitários isolados do domínio

### Arquitetura Hexagonal (Ports & Adapters)

Organização baseada em portas (interfaces) e adaptadores (implementações), sem camadas concêntricas explícitas.

* Bom, porque promove isolamento do domínio equivalente à Onion
* Bom, porque é conceitualmente elegante para sistemas com múltiplos adapters
* Ruim, porque a nomenclatura (portas primárias/secundárias) pode confundir a equipe
* Ruim, porque na prática, para este projeto, a diferença em relação à Onion é apenas organizacional
* Ruim, porque a Onion tem mapeamento mais direto para estrutura de diretórios em Python

## Consequências

### Positivas

* Demonstra domínio de DDD, Domain Events, Aggregates e Bounded Contexts na avaliação do Tech Challenge
* Domínio isolado permite testes unitários com cobertura de 80%+ sem mocks de infraestrutura
* Inversão de dependências via Repository ports permite trocar PostgreSQL por in-memory nos testes
* Estrutura de diretórios reflete as camadas da arquitetura, facilitando a navegação do código
* Preparação para evoluções futuras (microserviços, event sourcing) sem reescrita do domínio

### Negativas

* Complexidade estrutural maior que o necessário para o escopo funcional do MVP
* Curva de aprendizado mais íngreme para membros da equipe sem experiência em DDD
* Mais arquivos e indireções (ports, adapters, use cases) comparado a uma abordagem simples
* Risco de over-engineering se a disciplina de camadas não for mantida ao longo do desenvolvimento

## Decisões Relacionadas

- [ADR-006](006-mapeamento-imperativo-sqlalchemy.md): Mapeamento imperativo do SQLAlchemy — garante que entidades de domínio permanecem como classes puras, sem herança de ORM
- [ADR-007](007-organizacao-contextos-delimitados.md): Organização dos contextos delimitados — define as fronteiras dos Bounded Contexts dentro da estrutura Onion
