# Usar FastAPI como framework web

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O projeto precisa de um framework web Python para expor a API REST do sistema de oficina mecânica. Quais são os requisitos técnicos que o framework deve atender?

- Geração automática de documentação OpenAPI/Swagger (requisito do Tech Challenge)
- Suporte a operações assíncronas
- Injeção de dependências nativa
- Validação de tipos com type hints do Python

## Decisão

Adotar o FastAPI como framework web do projeto.

O FastAPI atende a todos os requisitos técnicos levantados de forma nativa, sem necessidade de extensões ou configuração adicional. A geração automática de documentação Swagger a partir dos type hints do Python elimina o trabalho manual de manter a especificação OpenAPI sincronizada com o código.

## Alternativas Consideradas

* FastAPI
* Flask
* Django REST Framework

### FastAPI

Framework moderno baseado em Starlette e Pydantic, com suporte nativo a async, type hints e geração automática de documentação OpenAPI.

* Bom, porque gera documentação Swagger automaticamente a partir dos type hints
* Bom, porque tem injeção de dependências nativa, facilitando a inversão de dependências do DDD
* Bom, porque usa Pydantic para validação de entrada, reduzindo código boilerplate
* Bom, porque tem alto desempenho graças ao Starlette e ao suporte a async/await
* Ruim, porque tem ecossistema menor que o Django em termos de pacotes prontos

### Flask

Microframework minimalista e amplamente adotado, com grande ecossistema de extensões.

* Bom, porque é maduro e amplamente documentado
* Bom, porque tem grande quantidade de extensões disponíveis
* Ruim, porque não tem suporte nativo a async (requer extensões)
* Ruim, porque não gera documentação OpenAPI nativamente (requer flask-smorest ou similar)
* Ruim, porque não tem injeção de dependências nativa

### Django REST Framework

Framework completo construído sobre o Django, com serializers, viewsets e browsable API.

* Bom, porque é extremamente maduro e battle-tested para aplicações grandes
* Bom, porque tem ecossistema vasto com soluções prontas para autenticação, admin, ORM
* Ruim, porque o ORM acoplado do Django conflita com a abordagem de mapeamento imperativo do SQLAlchemy
* Ruim, porque a estrutura opinada do Django dificulta a organização em camadas DDD
* Ruim, porque traz complexidade desnecessária para o escopo do projeto

## Consequências

### Positivas

* Documentação Swagger gerada automaticamente, cumprindo o requisito do Tech Challenge sem esforço adicional
* Validação de dados de entrada com Pydantic integrada ao framework
* Injeção de dependências nativa facilita a implementação de Ports & Adapters na camada de interfaces
* Type hints do Python são aproveitados como contrato de API, não apenas como anotações
* Suporte a async permite operações de I/O concorrentes sem threads

### Negativas

* Ecossistema menor que o Django para funcionalidades prontas (admin, CMS, etc.)
* Menos battle-tested para monolitos grandes em produção comparado ao Django
* Equipe pode precisar de tempo de adaptação se tiver experiência apenas com Flask ou Django

## Decisões Relacionadas

- [ADR-003](003-arquitetura-ddd-onion.md): DDD com Arquitetura Onion — a injeção de dependências nativa do FastAPI facilita a inversão de dependências exigida pela Onion Architecture
