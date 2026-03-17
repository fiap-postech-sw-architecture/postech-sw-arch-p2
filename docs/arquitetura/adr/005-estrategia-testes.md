# Estratégia de testes com cobertura realista

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O Tech Challenge exige cobertura de testes acima de 80% nos domínios críticos. O domínio utiliza tipos do PostgreSQL como ENUM e operações como SELECT FOR UPDATE que não existem em bancos in-memory. Como garantir que os testes reflitam o comportamento real do banco de dados em produção?

## Decisão

Adotar pytest com testcontainers (PostgreSQL real em container Docker) como base da estratégia de testes.

Ferramentas e práticas:

- **pytest + testcontainers**: cada sessão de teste sobe um container PostgreSQL real, garantindo que ENUM, SELECT FOR UPDATE e demais funcionalidades específicas do PostgreSQL sejam exercitadas
- **polyfactory**: geração de fixtures tipadas a partir dos modelos de domínio, eliminando fixtures manuais
- **pytest-xdist**: execução paralela de testes com isolamento por SAVEPOINT — cada teste roda dentro de uma transação com SAVEPOINT que sofre rollback ao final, sem interferência entre testes paralelos
- **mutmut**: testes de mutação com meta de 70%+ de mutantes mortos, validando a qualidade das asserções
- **schemathesis**: testes de contrato gerados a partir da especificação OpenAPI do FastAPI, validando que a API respeita o schema documentado

Metas de cobertura:

- 90%+ para os domínios principais (OrdemDeServico e Estoque)
- 80%+ para os demais domínios (Cliente+Veiculo, Catalogo)
- 65%+ para infraestrutura e interfaces

## Alternativas Consideradas

* pytest + testcontainers (PostgreSQL real)
* SQLite in-memory
* Mocking extensivo do banco de dados

### pytest + testcontainers (PostgreSQL real)

Testes executados contra um container PostgreSQL idêntico ao de produção, com isolamento por SAVEPOINT e execução paralela via pytest-xdist.

* Bom, porque exercita ENUM, SELECT FOR UPDATE, JSONB e demais funcionalidades específicas do PostgreSQL
* Bom, porque o isolamento por SAVEPOINT permite paralelismo sem interferência entre testes
* Bom, porque detecta problemas reais de migração, constraints e tipos antes de chegar à produção
* Ruim, porque é mais lento que testes in-memory (mitigado pelo paralelismo com pytest-xdist)
* Ruim, porque exige Docker disponível no ambiente de desenvolvimento e CI

### SQLite in-memory

Substituir o PostgreSQL por SQLite em memória durante os testes para ganhar velocidade.

* Bom, porque é extremamente rápido e não requer infraestrutura adicional
* Ruim, porque não suporta ENUM nativo do PostgreSQL
* Ruim, porque não suporta SELECT FOR UPDATE (bloqueio pessimista)
* Ruim, porque diferenças de comportamento entre SQLite e PostgreSQL já causaram bugs em projetos anteriores

### Mocking extensivo do banco de dados

Substituir o repositório real por mocks em todos os testes de integração.

* Bom, porque testes são rápidos e não dependem de infraestrutura
* Ruim, porque incidentes anteriores demonstraram divergência entre mocks e comportamento real do PostgreSQL
* Ruim, porque mocks não exercitam queries SQL, constraints ou triggers
* Ruim, porque dá falsa sensação de segurança — testes passam mas o sistema falha em produção

## Consequências

### Positivas

* Testes realistas que exercitam o mesmo banco de produção, incluindo ENUM, JSONB e SELECT FOR UPDATE
* Detecção antecipada de problemas de schema, migração e constraints
* Execução paralela com pytest-xdist compensa o custo do container real
* Testes de mutação com mutmut garantem que as asserções são significativas, não apenas cobertura de linhas
* Testes de contrato com schemathesis validam que a API respeita a documentação Swagger

### Negativas

* Testes são mais lentos que alternativas in-memory, mesmo com paralelismo
* Testcontainers exige Docker instalado e em execução no ambiente de desenvolvimento e no CI
* Configuração inicial do ambiente de testes é mais complexa que SQLite ou mocks

## Decisões Relacionadas

- [ADR-002](002-banco-postgresql.md): PostgreSQL como banco de dados — testcontainers garante que testes exercitam o mesmo banco de produção, incluindo ENUM e SELECT FOR UPDATE
- [ADR-008](008-bloqueio-pessimista-estoque.md): Bloqueio pessimista — testes de integração com PostgreSQL real validam o comportamento de SELECT FOR UPDATE NOWAIT
