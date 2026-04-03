# Estratégia de testes com cobertura realista

* Status: Em Proposta
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
- [ADR-013](013-testes-bdd-pytest-bdd.md): Testes BDD com pytest-bdd — testes E2E com feature files Gherkin em português

## Ciclo TDD no Contexto DDD

Ciclo Red-Green-Refactor:

1. **Red**: escrever um teste que falha, expressando o comportamento esperado do dominio
2. **Green**: implementar o minimo de codigo para o teste passar
3. **Refactor**: melhorar estrutura e legibilidade mantendo os testes verdes

Ordem de aplicacao ao DDD:

| Ordem | Artefato DDD       | Foco do TDD                                         | Exemplo                                        |
|-------|--------------------|------------------------------------------------------|-------------------------------------------------|
| 1     | Value Objects      | Validacoes, igualdade estrutural, imutabilidade      | CPF invalido, Dinheiro negativo, Placa invalida |
| 2     | Entities           | Identidade, ciclo de vida, regras de negocio locais  | Cliente com CPF duplicado, Veiculo com placa    |
| 3     | Aggregates         | Invariantes, maquina de estados, consistencia        | OrdemDeServico: transicoes de status            |
| 4     | Domain Services    | Orquestracao entre aggregates, regras transversais   | MaquinaDeStatus: transicoes validas e invalidas |

Comecar pelos Value Objects garante que os blocos basicos estao corretos antes de compor Entities e Aggregates.

## Taxonomia de Test Doubles

Cada tipo de test double tem um proposito distinto:

### Stub

Retorna respostas pre-definidas, sem logica de verificacao.

Exemplo: `StubEstoquePort` que sempre retorna estoque disponivel, independente do item consultado.

### Fake

Implementacao funcional simplificada que reproduz o comportamento real sem infraestrutura.

Exemplo: `FakeOrdemDeServicoRepository` implementado com dicionario em memoria, suportando `salvar()`, `buscar_por_id()` e `listar()`.

### Spy

Registra chamadas recebidas para verificacao posterior.

Exemplo: spy no `DomainEventPublisher` para verificar que `OrcamentoAprovadoEvent` foi emitido apos aprovar o orcamento.

### Mock

Define comportamento esperado antes da execucao e valida que as chamadas ocorreram conforme especificado.

Exemplo: mock do `ClientePort` que espera ser chamado exatamente uma vez com o ID do cliente e levanta excecao se chamado com argumentos diferentes.

### Padrao Arrange-Act-Assert-Verify

1. **Arrange**: preparar dados de entrada, configurar test doubles
2. **Act**: executar a acao sob teste
3. **Assert**: validar o resultado direto (retorno, estado, excecao)
4. **Verify**: verificar interacoes com test doubles (chamadas, argumentos)

Aplicacao por camada DDD:

| Camada         | Test Double preferido | Justificativa                                           |
|----------------|----------------------|---------------------------------------------------------|
| Dominio        | Fake (repositories)  | Repositories em memoria preservam semantica do dominio  |
| Dominio        | Stub (ports)         | Ports externos com respostas fixas isolam o dominio      |
| Aplicacao      | Mock (domain services) | Verificar orquestracao entre servicos                  |
| Infraestrutura | Testcontainers       | PostgreSQL real para validar SQL, ENUM, constraints      |

## Perfis de Execucao de Testes

Tres perfis via pytest markers:

```
pytest -m unit          # Rapido (~segundos), sem infraestrutura
pytest -m integration   # Medio (~minutos), requer Docker (testcontainers)
pytest -m e2e           # Lento, fluxos completos com BDD (pytest-bdd)
```

| Perfil      | Duracao     | Infraestrutura | Escopo                                        | Frequencia                |
|-------------|-------------|----------------|-----------------------------------------------|---------------------------|
| unit        | ~segundos   | Nenhuma        | Value Objects, Entities, Aggregates, Services | Cada alteracao de codigo  |
| integration | ~minutos    | Docker         | Endpoints HTTP, repositorios, ports/adapters  | Antes de push             |
| e2e         | ~minutos    | Docker + app   | Fluxos completos, cenarios BDD                | CI pipeline               |

CI executa `unit` → `integration` → `e2e` em sequencia; falha interrompe o pipeline.
