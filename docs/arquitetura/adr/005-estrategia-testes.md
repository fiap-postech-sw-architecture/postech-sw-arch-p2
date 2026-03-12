# Estrategia de testes com cobertura realista

* Status: Aceito
* Data: 2026-03-11

## Contexto e Problema

O Tech Challenge exige cobertura de testes acima de 80% nos dominios criticos. O dominio utiliza tipos do PostgreSQL como ENUM e operacoes como SELECT FOR UPDATE que nao existem em bancos in-memory. Como garantir que os testes reflitam o comportamento real do banco de dados em producao?

## Decisao

Adotar pytest com testcontainers (PostgreSQL real em container Docker) como base da estrategia de testes.

Ferramentas e praticas:

- **pytest + testcontainers**: cada sessao de teste sobe um container PostgreSQL real, garantindo que ENUM, SELECT FOR UPDATE e demais funcionalidades especificas do PostgreSQL sejam exercitadas
- **polyfactory**: geracao de fixtures tipadas a partir dos modelos de dominio, eliminando fixtures manuais
- **pytest-xdist**: execucao paralela de testes com isolamento por SAVEPOINT — cada teste roda dentro de uma transacao com SAVEPOINT que sofre rollback ao final, sem interferencia entre testes paralelos
- **mutmut**: testes de mutacao com meta de 70%+ de mutantes mortos, validando a qualidade das asserções
- **schemathesis**: testes de contrato gerados a partir da especificacao OpenAPI do FastAPI, validando que a API respeita o schema documentado

Metas de cobertura:

- 90%+ para o dominio OrdemDeServico (contexto core)
- 80%+ para os demais dominios (Cliente+Veiculo, Catalogo, Estoque)
- 65%+ para infraestrutura e interfaces

## Alternativas Consideradas

* pytest + testcontainers (PostgreSQL real)
* SQLite in-memory
* Mocking extensivo do banco de dados

### pytest + testcontainers (PostgreSQL real)

Testes executados contra um container PostgreSQL identico ao de producao, com isolamento por SAVEPOINT e execucao paralela via pytest-xdist.

* Bom, porque exercita ENUM, SELECT FOR UPDATE, JSONB e demais funcionalidades especificas do PostgreSQL
* Bom, porque o isolamento por SAVEPOINT permite paralelismo sem interferencia entre testes
* Bom, porque detecta problemas reais de migracao, constraints e tipos antes de chegar a producao
* Ruim, porque e mais lento que testes in-memory (mitigado pelo paralelismo com pytest-xdist)
* Ruim, porque exige Docker disponivel no ambiente de desenvolvimento e CI

### SQLite in-memory

Substituir o PostgreSQL por SQLite em memoria durante os testes para ganhar velocidade.

* Bom, porque e extremamente rapido e nao requer infraestrutura adicional
* Ruim, porque nao suporta ENUM nativo do PostgreSQL
* Ruim, porque nao suporta SELECT FOR UPDATE (bloqueio pessimista)
* Ruim, porque diferenças de comportamento entre SQLite e PostgreSQL ja causaram bugs em projetos anteriores

### Mocking extensivo do banco de dados

Substituir o repositorio real por mocks em todos os testes de integracao.

* Bom, porque testes sao rapidos e nao dependem de infraestrutura
* Ruim, porque incidentes anteriores demonstraram divergencia entre mocks e comportamento real do PostgreSQL
* Ruim, porque mocks nao exercitam queries SQL, constraints ou triggers
* Ruim, porque da falsa sensacao de seguranca — testes passam mas o sistema falha em producao

## Consequencias

### Positivas

* Testes realistas que exercitam o mesmo banco de producao, incluindo ENUM, JSONB e SELECT FOR UPDATE
* Deteccao antecipada de problemas de schema, migracao e constraints
* Execucao paralela com pytest-xdist compensa o custo do container real
* Testes de mutacao com mutmut garantem que as asserções sao significativas, nao apenas cobertura de linhas
* Testes de contrato com schemathesis validam que a API respeita a documentacao Swagger

### Negativas

* Testes sao mais lentos que alternativas in-memory, mesmo com paralelismo
* Testcontainers exige Docker instalado e em execucao no ambiente de desenvolvimento e no CI
* Configuracao inicial do ambiente de testes e mais complexa que SQLite ou mocks
