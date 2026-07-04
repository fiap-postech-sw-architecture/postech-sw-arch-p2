# Guia de Contribuição

## Convenção de Nomenclatura — Modelo Híbrido (ADR-009)

Termos de **negócio** em português (sem acentos), padrões **técnicos** em inglês.

### Exemplos

| Categoria | Exemplo | Regra |
|---|---|---|
| Agregado | `OrdemDeServico` | PT |
| Objeto de valor | `Dinheiro`, `Orcamento` | PT |
| Repositório | `OrdemDeServicoRepository` | PT + sufixo EN |
| Evento | `OrcamentoAprovadoEvent` | PT + sufixo EN |
| Porta | `EstoquePort` | PT + sufixo EN |
| Classe base | `Entity`, `AggregateRoot` | EN |
| Método de domínio | `iniciar_diagnostico()` | PT |
| Variável | `ordem_id`, `total_aprovado` | PT |
| Arquivo técnico | `entity.py`, `repository.py` | EN |
| Arquivo de negócio | `cliente.py`, `ordem_de_servico.py` | PT |
| Camada (pasta) | `dominio/`, `aplicacao/` | PT |

### Glossário

Consulte [docs/requisitos/glossario.md](docs/requisitos/glossario.md) para a lista completa de termos e seus identificadores no código.

## Fluxo de Contribuição

1. Partir de uma `main` atualizada e criar a branch: `git checkout main && git pull && git checkout -b feat/<descricao>` (evita ramificar de uma `main` desatualizada)
2. Fazer as alterações
3. Commitar: `git commit -m "feat: <descrição>"`
4. Push: `git push -u origin feat/<descricao>`
5. Criar PR: `gh pr create`
6. Squash merge: `gh pr merge --squash --delete-branch`
7. Voltar para main: `git checkout main && git pull`

Branch `main` é protegida — todo conteúdo entra via PR com squash merge.

## Testes

```bash
make test              # Testes unitários (com cobertura)
make test-integ        # Testes de integração com testcontainers (requer Docker)
make lint              # Ruff (lint e format)
make security          # bandit (análise de segurança estática)
```

Cobertura mínima: **95%** em `src/` e `ui/` (gate configurado em `.coveragerc`).

## Receitas

Cada contexto delimitado (ex.: `src/ordem_servico/`) segue as camadas da Clean
Architecture em **arquivos singulares por camada**, não em subpastas de módulos:
`aplicacao/use_cases.py`, `aplicacao/ports.py`, `aplicacao/dtos.py`,
`infraestrutura/adapters.py`, `infraestrutura/mapping.py`,
`interfaces/router.py`, `interfaces/schemas.py` e `interfaces/dependencies.py`.
Casos de uso são **classes dentro de `use_cases.py`** (um arquivo por contexto,
não um arquivo por caso de uso). O wiring de DI vive em
`<contexto>/interfaces/dependencies.py` (factories `obter_*`); o `src/main.py`
só monta os routers de cada contexto (`include_router`), não faz o wiring.

### Como adicionar um campo a uma entidade

1. Adicionar o campo na classe de domínio (ex: `cliente_veiculo/dominio/cliente.py`)
2. Atualizar o mapeamento imperativo em `<contexto>/infraestrutura/mapping.py`
3. Criar migração Alembic: `uv run alembic revision --autogenerate -m "add campo_x to tabela"`
4. Atualizar os schemas Pydantic em `<contexto>/interfaces/schemas.py`
5. Adicionar testes unitários e de integração

### Como adicionar um novo caso de uso

1. Criar a classe do caso de uso em `<contexto>/aplicacao/use_cases.py`
2. Definir as portas necessárias em `<contexto>/aplicacao/ports.py` (se cross-contexto) e os DTOs em `aplicacao/dtos.py`
3. Implementar os adaptadores em `<contexto>/infraestrutura/adapters.py`
4. Adicionar a rota em `<contexto>/interfaces/router.py`
5. Adicionar a factory `obter_<caso_de_uso>(session)` em `<contexto>/interfaces/dependencies.py` e injetá-la no endpoint via `Depends()`
6. Adicionar testes (unitário no caso de uso, integração na rota)

### Como adicionar um novo endpoint

1. Criar os schemas Pydantic de request/response em `<contexto>/interfaces/schemas.py`
2. Adicionar a rota no router em `<contexto>/interfaces/router.py`
3. Injetar o caso de uso pela factory de `interfaces/dependencies.py` via `Depends()`
4. Adicionar testes e2e

### Como adicionar um adaptador cross-contexto

1. Definir a porta (Protocol) em `<contexto-consumidor>/aplicacao/ports.py` — o consumidor define a porta (padrão Anti-Corruption Layer)
2. Implementar o adaptador em `<contexto-consumidor>/infraestrutura/adapters.py`, traduzindo o modelo vizinho para os DTOs da porta
3. Fazer o wiring na factory do caso de uso em `<contexto-consumidor>/interfaces/dependencies.py` (não no `main.py`)
4. Portas de leitura não recebem `UnitOfWork`; portas de escrita recebem
