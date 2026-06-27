# Estratégia de testes com cobertura realista

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-11

## Contexto e Problema

O Tech Challenge exige cobertura de testes acima de 80% nos domínios críticos. O domínio utiliza tipos do PostgreSQL como ENUM e operações como SELECT FOR UPDATE que não existem em bancos in-memory. Como garantir que os testes reflitam o comportamento real do banco de dados em produção?

## Decisão

Adotar pytest com testcontainers (PostgreSQL real em container Docker) como base da estratégia de testes.

Ferramentas e práticas:

- **pytest + testcontainers**: cada sessão de teste sobe um container PostgreSQL real, garantindo que ENUM, SELECT FOR UPDATE e demais funcionalidades específicas do PostgreSQL sejam exercitadas
- **polyfactory**: geração de fixtures tipadas a partir dos modelos de domínio, eliminando fixtures manuais
- **pytest-xdist**: execução paralela de testes com isolamento por SAVEPOINT — cada teste roda dentro de uma transação com SAVEPOINT que sofre rollback ao final, sem interferência entre testes paralelos

Evoluções planejadas (ainda não adotadas como dependências do projeto):

- **mutmut**: testes de mutação com meta de 70%+ de mutantes mortos, para validar a qualidade das asserções
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
* Base preparada para evoluções planejadas: testes de mutação (mutmut) reforçariam a significância das asserções e testes de contrato (schemathesis) validariam a API contra a documentação Swagger

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

1. **Red**: escrever um teste que falha, expressando o comportamento esperado do domínio
2. **Green**: implementar o mínimo de código para o teste passar
3. **Refactor**: melhorar estrutura e legibilidade mantendo os testes verdes

Ordem de aplicação ao DDD:

| Ordem | Artefato DDD       | Foco do TDD                                         | Exemplo                                        |
|-------|--------------------|------------------------------------------------------|-------------------------------------------------|
| 1     | Value Objects      | Validações, igualdade estrutural, imutabilidade      | CPF inválido, Dinheiro negativo, Placa inválida |
| 2     | Entities           | Identidade, ciclo de vida, regras de negócio locais  | Cliente com CPF duplicado, Veiculo com placa    |
| 3     | Aggregates         | Invariantes, máquina de estados, consistência        | OrdemDeServico: transições de status            |
| 4     | Domain Services    | Orquestração entre aggregates, regras transversais   | MaquinaDeStatus: transições válidas e inválidas |

Começar pelos Value Objects garante que os blocos básicos estão corretos antes de compor Entities e Aggregates.

## Taxonomia de Test Doubles

Cada tipo de test double tem um propósito distinto:

### Stub

Retorna respostas pré-definidas, sem lógica de verificação.

Exemplo: `StubEstoquePort` que sempre retorna estoque disponível, independente do item consultado.

### Fake

Implementação funcional simplificada que reproduz o comportamento real sem infraestrutura.

Exemplo: `FakeOrdemDeServicoRepository` implementado com dicionário em memória, suportando `salvar()`, `buscar_por_id()` e `listar()`.

### Spy

Registra chamadas recebidas para verificação posterior.

Exemplo: spy no `DomainEventPublisher` para verificar que `OrcamentoAprovadoEvent` foi emitido após aprovar o orcamento.

### Mock

Define comportamento esperado antes da execução e valida que as chamadas ocorreram conforme especificado.

Exemplo: mock do `ClientePort` que espera ser chamado exatamente uma vez com o ID do cliente e levanta exceção se chamado com argumentos diferentes.

### Padrão Arrange-Act-Assert-Verify

1. **Arrange**: preparar dados de entrada, configurar test doubles
2. **Act**: executar a acao sob teste
3. **Assert**: validar o resultado direto (retorno, estado, exceção)
4. **Verify**: verificar interações com test doubles (chamadas, argumentos)

Aplicação por camada DDD:

| Camada         | Test Double preferido | Justificativa                                           |
|----------------|----------------------|---------------------------------------------------------|
| Domínio        | Fake (repositories)  | Repositories em memória preservam semântica do domínio  |
| Domínio        | Stub (ports)         | Ports externos com respostas fixas isolam o domínio      |
| Aplicação      | Mock (domain services) | Verificar orquestração entre serviços                  |
| Infraestrutura | Testcontainers       | PostgreSQL real para validar SQL, ENUM, constraints      |

## Perfis de Execução de Testes

Três perfis via pytest markers:

```
pytest -m unit          # Rapido (~segundos), sem infraestrutura
pytest -m integration   # Medio (~minutos), requer Docker (testcontainers)
pytest -m e2e           # Lento, fluxos completos com BDD (pytest-bdd)
```

| Perfil      | Duração     | Infraestrutura | Escopo                                        | Frequência                |
|-------------|-------------|----------------|-----------------------------------------------|---------------------------|
| unit        | ~segundos   | Nenhuma        | Value Objects, Entities, Aggregates, Services | Cada alteração de código  |
| integration | ~minutos    | Docker         | Endpoints HTTP, repositórios, ports/adapters  | Antes de push             |
| e2e         | ~minutos    | Docker + app   | Fluxos completos, cenários BDD                | CI pipeline               |

CI executa `unit` → `integration` → `e2e` em sequencia; falha interrompe o pipeline.

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
