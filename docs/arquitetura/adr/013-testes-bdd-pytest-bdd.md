# Testes BDD com pytest-bdd e Gherkin

* Status: Proposta
* Data: 2026-03-29

## Contexto e Problema

O projeto utiliza linguagem ubiqua em portugues (ADR-009). Feature files Gherkin (Given-When-Then) permitem documentacao viva dos requisitos em linguagem natural. Como implementar testes E2E que sirvam como validacao automatizada e documentacao dos fluxos de negocio?

## Decisao

Adotar pytest-bdd para testes E2E com feature files em portugues. Feature files organizados por bounded context em `tests/e2e/features/`. Steps implementados em Python, reutilizando fixtures do pytest.

Estrutura de diretorios:

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

* Bom, porque comunidade ativa e boa documentacao
* Bom, porque suporte nativo a Gherkin em portugues
* Ruim, porque nao integra nativamente com pytest — requer runner separado (`behave` CLI)
* Ruim, porque nao compartilha fixtures do pytest, exigindo mecanismo proprio de setup/teardown
* Ruim, porque duplica infraestrutura de testes (conftest.py para pytest + environment.py para behave)

### Apenas testes de API com pytest (sem Gherkin)

Testes E2E escritos diretamente em Python com pytest, sem camada Gherkin.

* Bom, porque simples, sem overhead de feature files e steps
* Bom, porque aproveita toda a infraestrutura existente do pytest
* Ruim, porque perde rastreabilidade direta entre cenarios e requisitos em linguagem de negocio
* Ruim, porque testes sao legiveis apenas por desenvolvedores, nao por stakeholders
* Ruim, porque nao produz documentacao viva dos fluxos de negocio

### pytest-bdd (escolhido)

Plugin pytest que implementa BDD com feature files Gherkin, integrando-se ao ecossistema pytest.

* Bom, porque integra nativamente com pytest — fixtures, markers, plugins compartilhados
* Bom, porque cenarios em portugues (`# language: pt`) alinham com a linguagem ubiqua (ADR-009)
* Bom, porque feature files servem como documentacao viva dos requisitos
* Bom, porque steps reutilizaveis entre cenarios reduzem duplicacao
* Ruim, porque feature files adicionais para manter em sincronia com o codigo
* Ruim, porque curva de aprendizado do Gherkin para a equipe

## Consequencias

### Positivas

* Feature files legiveis por stakeholders nao tecnicos, funcionando como documentacao viva
* Rastreabilidade entre feature files e requisitos funcionais (RF-xxx)
* Linguagem ubiqua nos testes, alinhada com ADR-009
* Reutilizacao de fixtures pytest existentes (testcontainers, factories, API client)
* Cenarios Gherkin facilitam validacao de requisitos com especialistas de dominio

### Negativas

* Mais arquivos para manter: feature files (`.feature`) e step definitions (`.py`) em paralelo
* Curva de aprendizado do Gherkin para membros da equipe nao familiarizados
* Risco de feature files desatualizados se nao houver disciplina de manutencao
* Steps mal granularizados podem gerar duplicacao ou acoplamento entre cenarios

## Decisoes Relacionadas

- [ADR-005](005-estrategia-testes.md): Estrategia de testes — pytest-bdd integra o perfil E2E da piramide de testes
- [ADR-009](009-decisao-de-idioma.md): Modelo hibrido de idioma — feature files em portugues alinham com a linguagem ubiqua

## Notas

* pytest-bdd docs: https://pytest-bdd.readthedocs.io/
* Gherkin em portugues: https://cucumber.io/docs/gherkin/languages/
* Marker pytest: `@pytest.mark.e2e` para identificar testes BDD no perfil de execucao
