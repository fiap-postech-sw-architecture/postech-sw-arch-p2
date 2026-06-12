# Testes BDD com pytest-bdd e Gherkin

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Proposta
* Data: 2026-03-29

## Contexto e Problema

O projeto utiliza linguagem ubíqua em português (ADR-009). Feature files Gherkin (Given-When-Then) permitem documentação viva dos requisitos em linguagem natural. Como implementar testes E2E que sirvam como validação automatizada e documentação dos fluxos de negócio?

## Decisão

Adotar pytest-bdd para testes E2E com feature files em português. Feature files organizados por bounded context em `tests/e2e/features/`. Steps implementados em Python, reutilizando fixtures do pytest.

Estrutura de diretórios:

```
tests/
  e2e/
    features/
      ordem_de_servico/
        ciclo_de_vida_os.feature
        orcamento.feature
      cliente_veiculo/
        cadastro_cliente.feature
      estoque/
        reserva_pecas.feature
    steps/
      test_ordem_de_servico.py
      test_cliente_veiculo.py
      test_estoque.py
    conftest.py
```

Exemplo de feature file:

```gherkin
# language: pt
Funcionalidade: Ciclo de Vida da Ordem de Servico
  Como administrador da oficina
  Quero gerenciar ordens de servico
  Para controlar o fluxo de trabalho

  Cenario: Criar OS e avancar ate diagnostico
    Dado que existe um cliente cadastrado com CPF valido
    E que o cliente possui um veiculo registrado
    Quando criar uma ordem de servico para o veiculo
    Entao a OS deve ter status "Recebida"
    Quando iniciar o diagnostico da OS
    Entao a OS deve ter status "EmDiagnostico"
```

Exemplo de step definition:

```python
from pytest_bdd import scenario, given, when, then, parsers

@scenario("ordem_de_servico/ciclo_de_vida_os.feature",
          "Criar OS e avancar ate diagnostico")
def test_criar_os_avancar_diagnostico():
    pass

@given("que existe um cliente cadastrado com CPF valido")
def cliente_cadastrado(cliente_factory):
    return cliente_factory.criar()

@when("criar uma ordem de servico para o veiculo")
def criar_os(api_client, veiculo):
    response = api_client.post("/api/v1/ordens-de-servico",
                               json={"veiculo_id": str(veiculo.id)})
    assert response.status_code == 201
    return response.json()

@then(parsers.parse('a OS deve ter status "{status}"'))
def verificar_status(ordem_de_servico, status):
    assert ordem_de_servico["status"] == status
```

## Alternativas Consideradas

* behave
* Apenas testes de API com pytest (sem Gherkin)
* pytest-bdd

### behave

Framework BDD dedicado para Python.

* Bom, porque comunidade ativa e boa documentação
* Bom, porque suporte nativo a Gherkin em português
* Ruim, porque não integra nativamente com pytest — requer runner separado (`behave` CLI)
* Ruim, porque não compartilha fixtures do pytest, exigindo mecanismo próprio de setup/teardown
* Ruim, porque duplica infraestrutura de testes (conftest.py para pytest + environment.py para behave)

### Apenas testes de API com pytest (sem Gherkin)

Testes E2E escritos diretamente em Python com pytest, sem camada Gherkin.

* Bom, porque simples, sem overhead de feature files e steps
* Bom, porque aproveita toda a infraestrutura existente do pytest
* Ruim, porque perde rastreabilidade direta entre cenários e requisitos em linguagem de negócio
* Ruim, porque testes são legíveis apenas por desenvolvedores, não por stakeholders
* Ruim, porque não produz documentação viva dos fluxos de negócio

### pytest-bdd (escolhido)

Plugin pytest que implementa BDD com feature files Gherkin, integrando-se ao ecossistema pytest.

* Bom, porque integra nativamente com pytest — fixtures, markers, plugins compartilhados
* Bom, porque cenários em português (`# language: pt`) alinham com a linguagem ubíqua (ADR-009)
* Bom, porque feature files servem como documentação viva dos requisitos
* Bom, porque steps reutilizáveis entre cenários reduzem duplicação
* Ruim, porque feature files adicionais para manter em sincronia com o código
* Ruim, porque curva de aprendizado do Gherkin para a equipe

## Consequências

### Positivas

* Feature files legíveis por stakeholders não técnicos, funcionando como documentação viva
* Rastreabilidade entre feature files e requisitos funcionais (RF-xxx)
* Linguagem ubíqua nos testes, alinhada com ADR-009
* Reutilização de fixtures pytest existentes (testcontainers, factories, API client)
* Cenários Gherkin facilitam validação de requisitos com especialistas de domínio

### Negativas

* Mais arquivos para manter: feature files (`.feature`) e step definitions (`.py`) em paralelo
* Curva de aprendizado do Gherkin para membros da equipe não familiarizados
* Risco de feature files desatualizados se não houver disciplina de manutenção
* Steps mal granularizados podem gerar duplicação ou acoplamento entre cenários

## Decisões Relacionadas

- [ADR-005](005-estrategia-testes.md): Estratégia de testes — pytest-bdd integra o perfil E2E da pirâmide de testes
- [ADR-009](009-decisao-de-idioma.md): Modelo híbrido de idioma — feature files em português alinham com a linguagem ubíqua

## Notas

* pytest-bdd docs: https://pytest-bdd.readthedocs.io/
* Gherkin em português: https://cucumber.io/docs/gherkin/languages/
* Marker pytest: `@pytest.mark.e2e` para identificar testes BDD no perfil de execução

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
