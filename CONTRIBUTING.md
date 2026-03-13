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

1. Criar branch a partir de `main`: `git checkout -b feat/<descricao>`
2. Fazer as alterações
3. Commitar: `git commit -m "feat: <descrição>"`
4. Push: `git push -u origin feat/<descricao>`
5. Criar PR: `gh pr create`
6. Squash merge: `gh pr merge --squash --delete-branch`
7. Voltar para main: `git checkout main && git pull`

Branch `main` é protegida — todo conteúdo entra via PR com squash merge.

## Testes

```bash
make test              # Testes unitários e integração
make test-docker       # Testes com Docker (testcontainers)
make lint              # Ruff + mypy
make security-scan     # SonarQube + OWASP ZAP + bandit + pip-audit + gitleaks + trivy
```

Cobertura mínima por faixa:
- 90%+ em `ordem_de_servico/dominio/` e `estoque/dominio/` (domínios principais)
- 80%+ nos demais `*/dominio/`
- 65%+ em `*/infraestrutura/` e `*/interfaces/`

## Receitas

### Como adicionar um campo a uma entidade

1. Adicionar o campo na classe de domínio (ex: `cliente/dominio/cliente.py`)
2. Atualizar o mapeamento imperativo em `infraestrutura/mapping.py`
3. Criar migração Alembic: `alembic revision --autogenerate -m "add campo_x to tabela"`
4. Atualizar schemas Pydantic em `interfaces/schemas/`
5. Adicionar testes unitários e de integração

### Como adicionar um novo caso de uso

1. Criar o caso de uso em `aplicacao/` (ex: `aprovar_orcamento.py`)
2. Definir portas necessárias em `aplicacao/ports/` (se cross-contexto)
3. Implementar adaptadores em `infraestrutura/adapters/`
4. Registrar rota em `interfaces/routers/`
5. Registrar dependência em `interfaces/dependencies.py`
6. Adicionar testes (unitário no caso de uso, integração na rota)

### Como adicionar um novo endpoint

1. Criar schema Pydantic de request/response em `interfaces/schemas/`
2. Adicionar rota no router em `interfaces/routers/`
3. Injetar caso de uso via `Depends()`
4. Adicionar testes e2e

### Como adicionar um adaptador cross-contexto

1. Definir porta (Protocol) em `aplicacao/ports/` do contexto consumidor
2. Implementar adaptador em `infraestrutura/adapters/`
3. Registrar no `main.py` (raiz de composição)
4. Portas de leitura não recebem `UnitOfWork`; portas de escrita recebem
