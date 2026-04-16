# Estrategia de Testes

* Versao: 1.0
* Data: 2026-03-29

---

## 1. Objetivo

Estrategia de testes do projeto, consolidando [ADR-005](../arquitetura/adr/005-estrategia-testes.md) e [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md).

## 2. Piramide de Testes

Piramide de testes adaptada para DDD com Onion Architecture:

```
        /\
       /  \        E2E / BDD (poucos)
      /    \       Feature files Gherkin, fluxos completos
     /------\
    /        \     Integracao (medio)
   /          \    Endpoints HTTP, repositorios, ports/adapters
  /------------\
 /              \  Unitarios (maioria)
/________________\ Value Objects, Entities, Aggregates, Services
```

| Nivel       | Proporcao | Tempo de execucao | Infraestrutura       | Ferramentas                   |
|-------------|-----------|-------------------|----------------------|-------------------------------|
| Unitarios   | ~70%      | Milissegundos     | Nenhuma              | pytest, polyfactory           |
| Integracao  | ~20%      | Segundos/minutos  | Docker (testcontainers) | pytest, testcontainers, FastAPI TestClient |
| E2E / BDD   | ~10%      | Minutos           | Docker + aplicacao   | pytest-bdd, Gherkin           |

## 3. Test-Driven Development (TDD)

Red-Green-Refactor aplicado ao desenvolvimento dos artefatos de dominio:

### Ciclo Red-Green-Refactor

1. **Red**: escrever um teste que falha, expressando o comportamento esperado do dominio
2. **Green**: implementar o minimo de codigo necessario para o teste passar
3. **Refactor**: melhorar a estrutura do codigo mantendo todos os testes verdes

### Ordem de aplicacao ao DDD

TDD segue a ordem de dependencia dos artefatos DDD:

| Fase | Artefato         | Foco                                      | Exemplos                                    |
|------|------------------|--------------------------------------------|---------------------------------------------|
| 1    | Value Objects    | Validacoes, igualdade, imutabilidade       | CPF invalido, Dinheiro negativo, Placa      |
| 2    | Entities         | Identidade, ciclo de vida                  | Cliente com CPF, Veiculo com placa          |
| 3    | Aggregates       | Invariantes, maquina de estados            | OrdemDeServico: transicoes, reserva estoque |
| 4    | Domain Services  | Orquestracao com test doubles              | MaquinaDeStatus: transicoes validas         |

Comecar pelos Value Objects garante que os blocos basicos estao corretos antes de compor Entities e Aggregates.

## 4. Test Doubles

Test doubles utilizados no projeto, com exemplos por camada:

### Tipos

| Tipo  | Descricao                              | Quando usar                                          |
|-------|----------------------------------------|------------------------------------------------------|
| Stub  | Retorna respostas pre-definidas        | Isolar dependencias cujo comportamento nao e o foco  |
| Fake  | Implementacao funcional simplificada   | Substituir infraestrutura mantendo semantica          |
| Spy   | Registra chamadas para verificacao     | Verificar que interacoes ocorreram                    |
| Mock  | Define e valida comportamento esperado | Verificar orquestracao precisa entre componentes      |

### Aplicacao por camada DDD

**Camada de Dominio**:
- Fakes para repositories — `FakeOrdemDeServicoRepository` com dicionario em memoria, suportando `salvar()`, `buscar_por_id()` e `listar()`
- Stubs para ports — `StubEstoquePort` que sempre retorna estoque disponivel

**Camada de Aplicacao**:
- Mocks para servicos de dominio — verificar que o caso de uso chama `MaquinaDeStatus.transitar()` com os argumentos corretos
- Spies para event publishers — verificar que `OrcamentoAprovadoEvent` foi emitido apos aprovacao

**Camada de Infraestrutura**:
- Testcontainers com PostgreSQL real — validar SQL, ENUM, SELECT FOR UPDATE, constraints
- Sem mocks de banco — divergencia entre mocks e PostgreSQL real ja causou bugs em projetos anteriores

### Padrao Arrange-Act-Assert-Verify

1. **Arrange**: preparar dados de entrada, configurar test doubles
2. **Act**: executar a acao sob teste
3. **Assert**: validar o resultado direto (retorno, estado, excecao)
4. **Verify**: verificar interacoes com test doubles (chamadas, argumentos)

## 5. Testes Unitarios

Dominio puro, sem dependencias externas. Cada teste executa em milissegundos.

### Value Objects

Testar validacao na criacao, igualdade estrutural e imutabilidade:

- `Cpf`: rejeitar digitos invalidos, aceitar CPF valido, igualdade por valor
- `Cnpj`: rejeitar CNPJ invalido, aceitar CNPJ valido, formatacao
- `Placa`: aceitar formato antigo (AAA-0000) e Mercosul (AAA0A00), rejeitar invalidos
- `Dinheiro`: rejeitar valor negativo, operacoes aritmeticas, igualdade por valor
- `StatusOrdem`: validar transicoes permitidas na maquina de estados

### Entities

Testar identidade, ciclo de vida e regras de negocio locais:

- `Cliente`: criacao com CPF valido, associacao de veiculos
- `Veiculo`: criacao com placa valida, vinculo a cliente
- `ItemEstoque`: reserva, liberacao, verificacao de disponibilidade

### Aggregates

Testar invariantes e consistencia do aggregate root:

- `OrdemDeServico`: transicoes de status (Recebida → EmDiagnostico → Orcada → ...), rejeitar transicoes invalidas, adicionar itens ao orcamento, aprovar/rejeitar orcamento

### Domain Services

Testar orquestracao entre aggregates usando test doubles:

- `MaquinaDeStatus`: transicoes validas entre todos os estados, excecao em transicoes invalidas

## 6. Testes de Integracao

FastAPI TestClient com testcontainers para PostgreSQL real.

### Endpoints HTTP

- Validar status codes para operacoes CRUD (201 Created, 200 OK, 404 Not Found, 422 Unprocessable Entity)
- Validar response bodies conforme schema OpenAPI
- Validar headers de autenticacao (JWT) e autorizacao
- Schemathesis para testes de contrato gerados a partir da especificacao OpenAPI

### Repositorios

- Validar persistencia com PostgreSQL real, incluindo ENUM nativo, JSONB e constraints
- Testar SELECT FOR UPDATE NOWAIT para bloqueio pessimista de estoque (ADR-008)
- Testar isolamento por SAVEPOINT com execucao paralela (pytest-xdist)

### Cross-context (ports and adapters)

- Validar que adapters implementam corretamente as interfaces definidas pelos ports
- Testar comunicacao entre bounded contexts via ports

## 7. Testes E2E / BDD

Testes end-to-end com pytest-bdd e feature files Gherkin em portugues (ADR-013).

### Organizacao

Feature files organizados por bounded context:

```
tests/e2e/features/
  ordem_de_servico/
    ciclo_de_vida_os.feature
    orcamento.feature
  cliente_veiculo/
    cadastro_cliente.feature
  estoque/
    reserva_pecas.feature
```

### Cenarios e rastreabilidade

Cada cenario mapeia para uma ou mais user stories / requisitos funcionais:

| Feature file              | Cenarios                        | Requisitos       |
|---------------------------|---------------------------------|------------------|
| ciclo_de_vida_os.feature  | Criar OS, avancar diagnostico   | RF-007, RF-008   |
| orcamento.feature         | Aprovar/rejeitar orcamento      | RF-009           |
| cadastro_cliente.feature  | Cadastrar cliente com CPF       | RF-001           |
| reserva_pecas.feature     | Reservar pecas para OS          | RF-006           |

### Linguagem

Feature files escritos em portugues (`# language: pt`). Steps reutilizaveis entre cenarios.

## 8. Perfis de Execucao

Tres perfis via pytest markers:

```bash
# Unitarios: rapido, sem infraestrutura
pytest -m unit

# Integracao: requer Docker (testcontainers)
pytest -m integration

# E2E: fluxos completos com BDD
pytest -m e2e

# Todos os perfis
pytest
```

### Estrategia por ambiente

| Ambiente            | Perfis executados           | Trigger                       |
|---------------------|-----------------------------|-------------------------------|
| Desenvolvimento     | unit                        | Cada alteracao de codigo      |
| Pre-push            | unit + integration          | Antes de push para remote     |
| CI pipeline         | unit + integration + e2e    | Push / merge request          |
| Pre-merge           | Todos + cobertura + mutacao | Aprovacao de merge request    |

CI executa em sequencia (`unit` → `integration` → `e2e`). Falha em qualquer perfil interrompe o pipeline.

## 9. Qualidade de Codigo

Analise estatica no desenvolvimento e CI:

| Ferramenta | Finalidade                          | Configuracao          |
|------------|-------------------------------------|-----------------------|
| ruff       | Lint + formatacao                            | `pyproject.toml` [tool.ruff] |
| mypy       | Verificacao de tipos (modo strict)  | `pyproject.toml` [tool.mypy]  |
| bandit     | Vulnerabilidades de seguranca (ADR-011) | `.bandit.yml`     |
| SonarQube  | Quality gate em PR (quando disponivel) | CI pipeline        |

Execucao local:

```bash
ruff check src/                # Lint
ruff format --check src/       # Formatacao
mypy src/                      # Tipos
bandit -r src/ -c .bandit.yml  # Seguranca
```

## 10. Metas de Cobertura

Conforme ADR-005, diferenciadas por criticidade:

| Escopo                                     | Meta (linha) | Justificativa                                           |
|--------------------------------------------|-------------|----------------------------------------------------------|
| Dominios principais (OrdemDeServico, Estoque) | 90%+     | Core business, maior risco de regressao                  |
| Demais dominios (Cliente+Veiculo, Catalogo)   | 80%+     | Requisito do Tech Challenge                              |
| Infraestrutura e interfaces                   | 65%+     | Codigo de integracao, testado via integracao              |

### Testes de mutacao

mutmut com meta de 70%+ de mutantes mortos. Meta indicativa, nao bloqueante (TD-006).

## 11. Relatorios

| Ferramenta   | Tipo de relatorio           | Comando                           |
|-------------|-----------------------------|------------------------------------|
| pytest-cov  | Cobertura de codigo         | `pytest --cov=src --cov-report=html` |
| pytest-html | Relatorio de execucao       | `pytest --html=report.html`        |
| mutmut      | Relatorio de mutacao        | `mutmut run && mutmut html`        |
| schemathesis | Relatorio de contrato      | `st run --app=src.main:app`        |

Evolucao futura: Allure como framework de relatorios (TD-014).

## 12. Resultados (Fase 1)

Metricas finais da implementacao (16/04/2026):

| Metrica | Valor |
|---|---|
| Total de testes | 970 |
| Testes unitarios | ~920 |
| Testes de integracao | ~30 |
| Testes de seguranca | ~20 |
| Cobertura global | 97.75% |
| Meta global | 80% |
| Cobertura dominios criticos | 95%+ |
| Meta dominios criticos | 90% |
| Tempo de execucao (unitarios) | ~6s |

Todas as metas de cobertura atingidas. Testes de integracao usam testcontainers com PostgreSQL real e isolamento via SAVEPOINT.

## 13. Referencias

- [ADR-005](../arquitetura/adr/005-estrategia-testes.md): Estrategia de testes com cobertura realista
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md): Pipeline de seguranca e analise estatica — bandit, pip-audit, gitleaks, trivy
- [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md): Testes BDD com pytest-bdd e Gherkin
- [Requisitos](../requisitos/requisitos.md): RNF-009 (cobertura de testes), RNF-010 (scanning de seguranca)
- [Tech Debt](../tech-debt.md): TD-006 (mutation testing), TD-014 (Allure reports)
