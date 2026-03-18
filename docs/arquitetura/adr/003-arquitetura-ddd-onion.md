# Usar DDD com Arquitetura Onion

* Status: Aceita
* Data: 2026-03-11

## Contexto e Problema

O Tech Challenge da FIAP permite uma arquitetura simples em camadas: "é possível criar um Monolito utilizando a arquitetura em camadas". No entanto, o curso avalia conhecimento em Domain-Driven Design. Qual arquitetura adotar para demonstrar domínio de DDD e ao mesmo tempo manter o projeto viável para o escopo de MVP?

## Decisão

Adotar DDD com Arquitetura Onion, organizada em quatro camadas concêntricas:

1. **`dominio/`** — Entidades, Value Objects, Aggregates, Domain Events, Repository ports (interfaces)
2. **`aplicacao/`** — Use Cases (Application Services), DTOs de entrada/saída, orquestração
3. **`infraestrutura/`** — Implementações de Repository, mapeamento SQLAlchemy, adapters externos
4. **`interfaces/`** — Controllers FastAPI, schemas Pydantic de request/response, middlewares

A regra de dependência é estrita: camadas externas dependem das internas, nunca o inverso. O domínio não tem dependência de nenhuma outra camada — abstrações como `OrdemDeServicoRepository` e `EstoquePort` são definidas no `dominio/` e implementadas pela `infraestrutura/`.

## Alternativas Consideradas

* DDD com Arquitetura Onion
* Arquitetura em camadas simples
* Arquitetura Hexagonal (Ports & Adapters)
* Clean Architecture
* Vertical Slice Architecture
* CQRS com Event Sourcing

### DDD com Arquitetura Onion

Arquitetura em camadas concêntricas onde o domínio (`Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent`) ocupa o centro e todas as dependências apontam para dentro. Proposta por Jeffrey Palermo em 2008 como resposta às limitações das arquiteturas tradicionais em camadas no que diz respeito ao acoplamento entre regras de negócio e infraestrutura.

* Bom, porque demonstra domínio de DDD, agregando valor pedagógico ao Tech Challenge
* Bom, porque isola completamente o domínio de frameworks e infraestrutura
* Bom, porque facilita testes unitários do domínio sem dependências externas
* Bom, porque a inversão de dependências (Dependency Inversion Principle — SOLID) permite trocar infraestrutura sem alterar regras de negócio
* Bom, porque a organização em anéis concêntricos (`dominio/` → `aplicacao/` → `infraestrutura/` → `interfaces/`) mapeia diretamente para a estrutura de diretórios Python
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

Concebida por Alistair Cockburn nos anos 90 e formalizada em 2005, organiza o sistema em portas (interfaces) e adaptadores (implementações), isolando a aplicação no centro do hexágono. O princípio fundamental é o Separation of Concerns: o centro não conhece as tecnologias que o circundam.

* Bom, porque promove isolamento do domínio equivalente à Onion
* Bom, porque é conceitualmente elegante para sistemas com múltiplos adapters
* Bom, porque alto desacoplamento e independência de tecnologia facilitam trocar integrações
* Ruim, porque a nomenclatura (portas primárias/secundárias) pode confundir a equipe
* Ruim, porque na prática, para este projeto, a diferença em relação à Onion é apenas organizacional
* Ruim, porque a Onion tem mapeamento mais direto para estrutura de diretórios em Python

### Clean Architecture

Proposta por Robert C. Martin (Uncle Bob) em 2012 e consolidada em seu livro de 2017. Síntese de boas práticas da Hexagonal e Onion, com nomenclatura mais clara: Entities, Use Cases, Interface Adapters, Frameworks & Drivers.

* Bom, porque oferece clareza na separação de responsabilidades com camadas bem nomeadas
* Bom, porque independência de frameworks permite evolução tecnológica sem reescrita
* Bom, porque é orientada a testes e respeita fortemente os princípios SOLID
* Ruim, porque é mais verbosa — maior esforço inicial de estruturação
* Ruim, porque para este projeto o ganho sobre a Onion não justifica a diferença, já que a nomenclatura Onion já é adequada ao modelo DDD adotado

### Vertical Slice Architecture

Organiza o sistema em fatias verticais por funcionalidade em vez de camadas horizontais por tipo de artefato. Ganhou tração a partir de 2014, especialmente associada ao CQRS e ao feature-based design (Jimmy Bogard).

* Bom, porque organiza por funcionalidade real de negócio, facilitando o entendimento por feature
* Bom, porque cada slice é independente, testável e com baixo acoplamento entre features
* Bom, porque é ideal para CQRS e sistemas orientados a casos de uso
* Ruim, porque risco de duplicação de código entre slices similares
* Ruim, porque pode gerar inconsistência entre slices se mal implementado
* Ruim, porque não é natural para DDD com Bounded Contexts (`OrdemDeServico`, `Cliente`, `Estoque`) — a organização por contexto delimitado já oferece a coesão funcional necessária

### CQRS com Event Sourcing

O padrão CQRS (Command Query Responsibility Segregation) separa operações de escrita (commands) e leitura (queries) em modelos de dados distintos, com write database normalizado e read database desnormalizado, sincronizados via eventos. Combinado com event sourcing, armazena o estado como sequência de eventos.

* Bom, porque permite scaling e otimização independentes para modelos de leitura e escrita
* Bom, porque diferentes tecnologias podem ser usadas para cada necessidade
* Ruim, porque a complexidade de manter write/read stores separados com sincronização eventual é desproporcional para um MVP monolítico
* Ruim, porque event sourcing exige infraestrutura de event store e projeções que não se justificam no escopo atual

A rejeição do CQRS com event sourcing e stores separados não impede o uso de read models leves (projeções para consultas). A arquitetura Onion já suporta consultas otimizadas via `Repository` ports dedicados a leitura, sem necessidade de infraestrutura CQRS completa.

### Tabela Comparativa de Trade-offs

Baseada na análise da disciplina Software Architecture — Aula 1: Arquiteturas da Atualidade e Seus Trade-offs.

| Arquitetura | Principais Benefícios | Principais Desafios | Quando Usar |
|---|---|---|---|
| Hexagonal | Alto desacoplamento; testabilidade facilitada; independência de tecnologia; flexível para múltiplas interfaces | Curva de aprendizado; mais abstrações; overhead em projetos simples | Sistemas que precisam se comunicar com múltiplas interfaces (API, CLI, eventos etc.) |
| Onion | Domínio protegido; organização em camadas concêntricas; facilita manutenção e testes; segue SOLID | Complexidade inicial; conceitos podem ser mal interpretados | Aplicações de médio a grande porte com lógica de negócio rica e múltiplas integrações |
| Clean Architecture | Clareza na separação de responsabilidades; independência de frameworks; orientada a testes; evolutiva | Verbosidade; maior esforço inicial de estruturação | Projetos com expectativa de longo prazo, mudanças tecnológicas e alta exigência de qualidade |
| Vertical Slice | Organização por funcionalidade real; testes mais simples; ideal para CQRS; baixo acoplamento | Risco de duplicação; pode gerar inconsistência entre slices se mal implementado | APIs modernas, microsserviços, sistemas orientados a casos de uso |

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
- [ADR-009](009-decisao-de-idioma.md): Modelo híbrido de idioma — define as convenções de nomenclatura usadas neste ADR
