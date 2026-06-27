# Estratégia de Testes

> [↑ Raiz do projeto](../../README.md)

* Versão: 1.0
* Data: 2026-03-29

---

## 1. Objetivo

Estratégia de testes do projeto, consolidando [ADR-005](../arquitetura/adr/005-estrategia-testes.md) e [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md).

## 2. Pirâmide de Testes

Pirâmide de testes adaptada para DDD com Onion Architecture (evoluída para Clean Architecture na fase 2 — [ADR-015](../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md)):

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

| Nível       | Proporção | Tempo de execução | Infraestrutura       | Ferramentas                   |
|-------------|-----------|-------------------|----------------------|-------------------------------|
| Unitários   | ~70%      | Milissegundos     | Nenhuma              | pytest, polyfactory           |
| Integração  | ~20%      | Segundos/minutos  | Docker (testcontainers) | pytest, testcontainers, FastAPI TestClient |
| E2E / BDD   | ~10%      | Minutos           | Docker + aplicação   | pytest-bdd, Gherkin           |

## 3. Test-Driven Development (TDD)

Red-Green-Refactor aplicado ao desenvolvimento dos artefatos de domínio:

### Ciclo Red-Green-Refactor

1. **Red**: escrever um teste que falha, expressando o comportamento esperado do domínio
2. **Green**: implementar o mínimo de código necessário para o teste passar
3. **Refactor**: melhorar a estrutura do código mantendo todos os testes verdes

### Ordem de aplicação ao DDD

TDD segue a ordem de dependência dos artefatos DDD:

| Fase | Artefato         | Foco                                      | Exemplos                                    |
|------|------------------|--------------------------------------------|---------------------------------------------|
| 1    | Value Objects    | Validações, igualdade, imutabilidade       | CPF inválido, Dinheiro negativo, Placa      |
| 2    | Entities         | Identidade, ciclo de vida                  | Cliente com CPF, Veículo com placa          |
| 3    | Aggregates       | Invariantes, máquina de estados            | OrdemDeServico: transições, reserva estoque |
| 4    | Domain Services  | Orquestração com test doubles              | MaquinaDeStatus: transições válidas         |

Começar pelos Value Objects garante que os blocos básicos estão corretos antes de compor Entities e Aggregates.

## 4. Test Doubles

Test doubles utilizados no projeto, com exemplos por camada:

### Tipos

| Tipo  | Descrição                              | Quando usar                                          |
|-------|----------------------------------------|------------------------------------------------------|
| Stub  | Retorna respostas pré-definidas        | Isolar dependências cujo comportamento não é o foco  |
| Fake  | Implementação funcional simplificada   | Substituir infraestrutura mantendo semântica          |
| Spy   | Registra chamadas para verificação     | Verificar que interações ocorreram                    |
| Mock  | Define e valida comportamento esperado | Verificar orquestração precisa entre componentes      |

### Aplicacao por camada DDD

**Camada de Dominio**:
- Fakes para repositories — `FakeOrdemDeServicoRepository` com dicionário em memória, suportando `salvar()`, `buscar_por_id()` e `listar()`
- Stubs para ports — `StubEstoquePort` que sempre retorna estoque disponível

**Camada de Aplicacao**:
- Mocks para serviços de domínio — verificar que o caso de uso chama `MaquinaDeStatus.transitar()` com os argumentos corretos
- Spies para event publishers — verificar que `OrcamentoAprovadoEvent` foi emitido após aprovação

**Camada de Infraestrutura**:
- Testcontainers com PostgreSQL real — validar SQL, ENUM, SELECT FOR UPDATE, constraints
- Sem mocks de banco — divergência entre mocks e PostgreSQL real já causou bugs em projetos anteriores

### Padrao Arrange-Act-Assert-Verify

1. **Arrange**: preparar dados de entrada, configurar test doubles
2. **Act**: executar a ação sob teste
3. **Assert**: validar o resultado direto (retorno, estado, exceção)
4. **Verify**: verificar interações com test doubles (chamadas, argumentos)

## 5. Testes Unitarios

Dominio puro, sem dependencias externas. Cada teste executa em milissegundos.

### Value Objects

Testar validação na criação, igualdade estrutural e imutabilidade:

- `Cpf`: rejeitar dígitos inválidos, aceitar CPF válido, igualdade por valor
- `Cnpj`: rejeitar CNPJ inválido, aceitar CNPJ válido, formatação
- `Placa`: aceitar formato antigo (AAA-0000) e Mercosul (AAA0A00), rejeitar inválidos
- `Dinheiro`: rejeitar valor negativo, operações aritméticas, igualdade por valor
- `StatusOrdem`: validar transições permitidas na máquina de estados

### Entities

Testar identidade, ciclo de vida e regras de negócio locais:

- `Cliente`: criação com CPF válido, associação de veículos
- `Veiculo`: criação com placa válida, vínculo a cliente
- `ItemEstoque`: reserva, liberação, verificação de disponibilidade

### Aggregates

Testar invariantes e consistência do aggregate root:

- `OrdemDeServico`: transições de status (Recebida → EmDiagnostico → Orcada → ...), rejeitar transições inválidas, adicionar itens ao orçamento, aprovar/rejeitar orçamento

### Domain Services

Testar orquestração entre aggregates usando test doubles:

- `MaquinaDeStatus`: transições válidas entre todos os estados, exceção em transições inválidas

## 6. Testes de Integracao

FastAPI TestClient com testcontainers para PostgreSQL real.

### Endpoints HTTP

- Validar status codes para operacoes CRUD (201 Created, 200 OK, 404 Not Found, 422 Unprocessable Entity)
- Validar response bodies conforme schema OpenAPI
- Validar headers de autenticacao (JWT) e autorizacao
- Schemathesis para testes de contrato gerados a partir da especificacao OpenAPI

### Repositorios

- Validar persistência com PostgreSQL real, incluindo ENUM nativo, JSONB e constraints
- Testar SELECT FOR UPDATE NOWAIT para bloqueio pessimista de estoque (ADR-008)
- Testar isolamento por SAVEPOINT com execução paralela (pytest-xdist)

### Cross-context (ports and adapters)

- Validar que adapters implementam corretamente as interfaces definidas pelos ports
- Testar comunicação entre bounded contexts via ports

## 7. Testes E2E / BDD

Testes end-to-end com pytest-bdd e feature files Gherkin em português (ADR-013).

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

Cada cenário mapeia para uma ou mais user stories / requisitos funcionais:

| Feature file              | Cenários                        | Requisitos       |
|---------------------------|---------------------------------|------------------|
| ciclo_de_vida_os.feature  | Criar OS, avançar diagnóstico   | RF-007, RF-008   |
| orcamento.feature         | Aprovar/rejeitar orçamento      | RF-009           |
| cadastro_cliente.feature  | Cadastrar cliente com CPF       | RF-001           |
| reserva_pecas.feature     | Reservar peças para OS          | RF-006           |

### Linguagem

Feature files escritos em português (`# language: pt`). Steps reutilizáveis entre cenários.

## 8. Perfis de Execucao

Três perfis via pytest markers:

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

### Estratégia por ambiente

| Ambiente            | Perfis executados           | Trigger                       |
|---------------------|-----------------------------|-------------------------------|
| Desenvolvimento     | unit                        | Cada alteração de código      |
| Pre-push            | unit + integration          | Antes de push para remote     |
| CI pipeline         | unit + integration + e2e    | Push / merge request          |
| Pre-merge           | Todos + cobertura + mutação | Aprovação de merge request    |

CI executa em sequência (`unit` → `integration` → `e2e`). Falha em qualquer perfil interrompe o pipeline.

## 9. Qualidade de Codigo

Análise estática no desenvolvimento e CI:

| Ferramenta | Finalidade                          | Configuração          |
|------------|-------------------------------------|-----------------------|
| ruff       | Lint + formatação                            | `pyproject.toml` [tool.ruff] |
| mypy       | Verificação de tipos (modo strict)  | `pyproject.toml` [tool.mypy]  |
| bandit     | Vulnerabilidades de segurança (ADR-011) | `.bandit.yml`     |
| SonarQube  | Quality gate em PR (quando disponível) | CI pipeline        |

Execução local:

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
| Domínios principais (OrdemDeServico, Estoque) | 90%+     | Core business, maior risco de regressão                  |
| Demais domínios (Cliente+Veiculo, Catalogo)   | 80%+     | Requisito do Tech Challenge                              |
| Infraestrutura e interfaces                   | 65%+     | Código de integração, testado via integração              |

### Testes de mutacao

mutmut com meta de 70%+ de mutantes mortos. Meta indicativa, não bloqueante (TD-006).

## 11. Relatórios

| Ferramenta   | Tipo de relatório           | Comando                           |
|-------------|-----------------------------|------------------------------------|
| pytest-cov  | Cobertura de código         | `make test-coverage`                |
| pytest-html | Relatório de execução       | `pytest --html=report.html`        |
| mutmut      | Relatório de mutação        | `mutmut run && mutmut html`        |
| schemathesis | Relatório de contrato      | `st run --app=src.main:app`        |

Evolução futura: Allure como framework de relatórios (TD-014).

## 12. Resultados (Fase 1)

Métricas finais da implementação (16/04/2026):

| Métrica | Valor |
|---|---|
| Total de testes | 970 |
| Testes unitários | ~920 |
| Testes de integração | ~30 |
| Testes de segurança | ~20 |
| Cobertura global | 97.75% |
| Meta global | 80% |
| Cobertura domínios críticos | 95%+ |
| Meta domínios críticos | 90% |
| Tempo de execução (unitários) | ~6s |

Todas as metas de cobertura atingidas. Testes de integração usam testcontainers com PostgreSQL real e isolamento via SAVEPOINT.

> **Fase 2:** a suíte cresceu para **1426 unitários + 136 de integração** e o gate de cobertura passou a **95%** (`.coveragerc`, `fail_under = 95`), aplicado na CI. Os testes de integração com testcontainers agora também sobem **Redis** (storage do rate limiter — [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md)), além do PostgreSQL. Os números da fase 1 acima permanecem como registro histórico.

## 13. Referências

- [ADR-005](../arquitetura/adr/005-estrategia-testes.md): Estratégia de testes com cobertura realista
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md): Pipeline de segurança e análise estática — bandit, pip-audit, gitleaks, trivy
- [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md): Testes BDD com pytest-bdd e Gherkin
- [Requisitos](../requisitos/requisitos.md): RNF-009 (cobertura de testes), RNF-010 (scanning de seguranca)
- [Tech Debt](../tech-debt/README.md): TD-006 (mutation testing), TD-014 (Allure reports)

> [↑ Raiz do projeto](../../README.md)
