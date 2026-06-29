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
       /  \        E2E / BDD (planejado — ver Seção 7)
      /    \       Feature files Gherkin, fluxos completos
     /------\
    /        \     Integracao (medio)
   /          \    Endpoints HTTP, repositorios, ports/adapters
  /------------\
 /              \  Unitarios (maioria)
/________________\ Value Objects, Entities, Aggregates, Services
```

A distribuição **atual** da suíte é fortemente concentrada em testes unitários, com integração cobrindo as fronteiras de infraestrutura e a camada E2E/BDD ainda não implementada (apenas um smoke test de saúde em `tests/e2e/`):

| Nível       | Proporção atual | Tempo de execução | Infraestrutura       | Ferramentas                   |
|-------------|-----------------|-------------------|----------------------|-------------------------------|
| Unitários   | ~91%            | Milissegundos     | Nenhuma              | pytest, polyfactory           |
| Integração  | ~9%             | Segundos/minutos  | Docker (testcontainers) | pytest, testcontainers, FastAPI TestClient |
| E2E / BDD   | ~0% (planejado) | Minutos           | Docker + aplicação   | pytest-bdd, Gherkin (planejado — [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md), TD-013) |

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

## 7. Testes E2E / BDD (planejado)

> **Status: planejado, não entregue.** Esta seção descreve o *roadmap* da camada E2E/BDD, não o estado atual do código. A decisão está registrada em [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md), ainda com Status **"Proposta"**, e o débito correspondente é o [TD-013](../tech-debt/README.md) (deliberadamente adiado para depois do MVP). Hoje `tests/e2e/` contém apenas um smoke test de saúde (`test_saude.py`); **não há** `pytest-bdd` no `pyproject.toml` nem arquivos `.feature`. Promover esta camada a entregue exige uma issue própria (adicionar a dependência, escrever os feature files/steps e promover a ADR-013 a "Aceita").

### Abordagem proposta

Testes end-to-end com pytest-bdd e feature files Gherkin em português, organizados por bounded context. O objetivo é fornecer documentação viva dos fluxos de negócio (Given-When-Then) aproveitando a linguagem ubíqua em português ([ADR-009](../arquitetura/adr/009-decisao-de-idioma.md)).

A estrutura de diretórios prevista e o mapeamento de cenários para requisitos estão detalhados na [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md). Feature files seriam escritos em português (`# language: pt`), com steps reutilizáveis entre cenários.

## 8. Perfis de Execucao

Os perfis são separados por **diretório** (e, quando aplicável, por marker — os markers reais estão em `pyproject.toml`, `[tool.pytest.ini_options]`):

```bash
# Unitarios: rapido, sem infraestrutura
make test                 # == pytest tests/unitarios/ -m "not lento"

# Integracao: requer Docker (testcontainers)
make test-integ           # == pytest tests/integracao/

# Toda a suite (exceto os marcados como lento)
make test-all             # == pytest tests/ -m "not lento"

# Equivalentes diretos via pytest
pytest tests/unitarios
pytest tests/integracao
```

> A camada E2E/BDD (`pytest -m e2e`) está **planejada** (Seção 7): hoje o marker `e2e` cobre apenas o smoke test de saúde.

### Estratégia por ambiente

| Ambiente            | Perfis executados                       | Trigger                       |
|---------------------|-----------------------------------------|-------------------------------|
| Desenvolvimento     | Unitários                               | Cada alteração de código      |
| Pre-push            | Unitários + integração                  | Antes de push para remote     |
| CI pipeline         | Unitários + integração                  | Push / merge request          |
| Pre-merge           | Toda a suíte + cobertura + mutação      | Aprovação de merge request    |

CI executa unitários e integração; falha em qualquer etapa interrompe o pipeline. A etapa E2E/BDD entra no pipeline quando a camada da Seção 7 for entregue.

## 9. Qualidade de Codigo

Análise estática no desenvolvimento e CI:

| Ferramenta | Finalidade                          | Configuração          |
|------------|-------------------------------------|-----------------------|
| ruff       | Lint + formatação                            | `pyproject.toml` [tool.ruff] |
| mypy       | Verificação de tipos (modo strict)  | `pyproject.toml` [tool.mypy]  |
| bandit     | Vulnerabilidades de segurança (ADR-011) | `pyproject.toml` [tool.bandit] |
| SonarQube  | Análise estática/qualidade — scan **manual** de fechamento (não é gate de CI, ver TD-010) | `sonar-project.properties` |

Execução local:

```bash
ruff check src/                          # Lint
ruff format --check src/                 # Formatacao
mypy src/                                # Tipos
bandit -r src/ -c pyproject.toml         # Seguranca (config em [tool.bandit])
make security                            # Gate de seguranca completo (src/ ui/ relay/ scripts/, severity high)
```

## 10. Metas de Cobertura

Conforme ADR-005, diferenciadas por criticidade:

| Escopo                                     | Meta (linha) | Justificativa                                           |
|--------------------------------------------|-------------|----------------------------------------------------------|
| Domínios principais (OrdemDeServico, Estoque) | 90%+     | Core business, maior risco de regressão                  |
| Demais domínios (Cliente+Veiculo, Catalogo)   | 80%+     | Requisito do Tech Challenge                              |
| Infraestrutura e interfaces                   | 65%+     | Código de integração, testado via integração              |

### Testes de mutacao

Planejado (TD-006, débito deliberado): testes de mutação com meta indicativa de ~70% de mutantes mortos (ex.: mutmut), não bloqueante. Sem tooling instalado nesta fase.

## 11. Relatórios

| Ferramenta   | Tipo de relatório           | Comando                           | Status |
|-------------|-----------------------------|------------------------------------|--------|
| pytest-cov  | Cobertura de código         | `make test-coverage`               | Entregue |
| pytest-html | Relatório de execução       | `pytest --html=report.html`        | Planejado (não instalado) |
| mutmut      | Relatório de mutação        | `mutmut run && mutmut html`        | Planejado (TD-006) |
| schemathesis | Relatório de contrato      | `st run --app=src.main:app`       | Planejado (não instalado) |

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

> **Fase 2:** a suíte cresceu para **~1480 unitários + ~140 de integração** e o gate de cobertura passou a **95%** (`.coveragerc`, `fail_under = 95`), aplicado na CI. Os testes de integração com testcontainers agora também sobem **Redis** (storage do rate limiter — [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md)), além do PostgreSQL. Os números da fase 1 acima permanecem como registro histórico.

## 13. Referências

- [ADR-005](../arquitetura/adr/005-estrategia-testes.md): Estratégia de testes com cobertura realista
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md): Pipeline de segurança e análise estática — bandit, pip-audit, gitleaks, trivy
- [ADR-013](../arquitetura/adr/013-testes-bdd-pytest-bdd.md): Testes BDD com pytest-bdd e Gherkin
- [Requisitos](../requisitos/requisitos.md): RNF-009 (cobertura de testes), RNF-010 (scanning de seguranca)
- [Tech Debt](../tech-debt/README.md): TD-006 (mutation testing), TD-014 (Allure reports)

> [↑ Raiz do projeto](../../README.md)
