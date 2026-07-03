# Desenvolvimento Local

> [↑ Raiz do projeto](../README.md)

Workflow para desenvolver o backend fora do container (hot-reload), rodar
checks locais e atualizar dependencias. O ambiente Python é gerenciado via
[`uv`](https://docs.astral.sh/uv/) ([ADR-014](arquitetura/adr/014-gerenciador-pacotes-uv.md)).

> Setup de zero (instalar `uv`, Docker, Git, etc.): veja os guias por plataforma
> [Windows](setup/windows.md) - [macOS](setup/macos.md) - [Linux](setup/linux.md).

## Instalar dependencias

Após clonar o repo, instale o ambiente a partir do lockfile:

```bash
uv sync --extra test --frozen   # usa versoes exatas fixadas em uv.lock
```

`--frozen` garante que a resolução não altere `uv.lock`; se o lockfile
estiver desatualizado em relação a `pyproject.toml`, o comando falha e o
bump precisa ser feito explicitamente (veja
[Atualizando dependencias](#atualizando-dependencias) abaixo). Sem
`--frozen`, `uv sync` reconcilia o lockfile automaticamente -- útil em
primeiras instalações, mas evite em CI e commits do dia a dia.

### Alternativa sem `uv` (pip + venv)

Apenas se `uv` não estiver disponível no seu ambiente:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

Este fluxo não consome `uv.lock` (pip resolve versões novamente), então
pode divergir do ambiente do CI/produção. Use só como fallback.

> **Atenção**: nunca misture os dois fluxos no mesmo `.venv`. Se você já
> rodou `uv sync` e depois rodar `pip install` (ou vice-versa), o ambiente
> fica inconsistente com o lockfile sem nenhum aviso visível. Se isso
> acontecer, apague o `.venv` e recrie com `uv sync --extra test --frozen`.
> Veja também [`docs/setup/troubleshooting.md`](setup/troubleshooting.md#conflito-entre-venv-do-pip-e-ambiente-gerenciado-pelo-uv).

## Loop de desenvolvimento rápido (uvicorn com hot reload)

Para iterar rapidamente sem rebuilds do container da aplicação, rode apenas
o Postgres via `docker compose` e o FastAPI local com `--reload`:

```bash
cp .env.dev.example .env.dev           # (opcional) customize credenciais/porta
docker compose up -d postgres          # Postgres na porta 5432
uv run alembic upgrade head            # aplica migrations (so na primeira vez)
./scripts/run-dev.sh                   # uvicorn em http://localhost:8001 com reload
```

`uv run <cmd>` executa no ambiente criado por `uv sync` sem exigir
`source .venv/bin/activate`. Se preferir o fluxo tradicional, o equivalente
é `.venv/bin/alembic upgrade head`.

Os defaults do `scripts/run-dev.sh` (`DATABASE_URL` apontando para
`localhost:5432`, `JWT_SECRET` de dev com >=32 bytes, etc.) funcionam sem
configuração adicional. Você só precisa do `.env.dev` se quiser sobrescrever
algo (por exemplo, `UVICORN_PORT=9000`) sem editar o script. Ao terminar,
`docker compose down -v` encerra o Postgres.

Usuários com [Claude Code](https://docs.claude.com/en/docs/claude-code) podem
iniciar os servidores diretamente via `.claude/launch.json` (`preview_start`):

- `FastAPI (uvicorn dev server)` -- roda `scripts/run-dev.sh` na porta 8001
- `PostgreSQL (docker compose)` -- sobe apenas o Postgres na porta 5432
- `Full stack (docker compose)` -- sobe app + banco juntos na porta 8000

Troubleshooting do dev loop (Colima, JWT_SECRET, 500s comuns, verificação
end-to-end): [`docs/debugging-guide.md`](debugging-guide.md). Problemas de
runtime do Docker (socket, Compose v2): [`docs/setup/troubleshooting.md`](setup/troubleshooting.md).

## Checks locais (espelham o CI)

```bash
make check         # lint + contratos de arquitetura + mypy + bandit + testes unitarios
make lint-arch     # so os contratos de arquitetura (import-linter, ADR-015)
make test-coverage # testes unitarios + relatorio terminal + coverage.xml
make test-integ    # testes de integracao (requer Docker)
make test-all      # todos os 970+ testes
make format        # auto-formata codigo
make all           # format + check + integracao
```

O gate de lint/type/security roda via `make check` (e nos jobs dedicados
do CI) — `pytest` executa apenas os testes (a flag `--no-lint` foi removida).

Para gerar o arquivo consumido por CI/Sonar localmente, use `make test-coverage`.
Esse alvo roda os testes unitários não lentos com os extras `test` e `ui`, imprime
o relatório de linhas faltantes no terminal e escreve `coverage.xml` na raiz do
repositorio.

## Atualizando dependencias

O `uv.lock` fixa versões exatas e hashes SHA-256 de todas as dependências
(diretas e transitivas). Atualizações são **sempre explícitas** -- nunca
acontecem durante `uv sync --frozen`. Use os comandos abaixo conforme a
intenção:

| Intenção | Comando | O que acontece |
|---|---|---|
| Reinstalar o que está em `uv.lock` (fluxo diário) | `uv sync --extra test --frozen` | Nenhuma mudança em `uv.lock`; falha se o lockfile estiver inconsistente com `pyproject.toml` |
| Atualizar **todas** as transitivas dentro dos ranges de `pyproject.toml` | `uv lock --upgrade && uv sync --extra test` | Regenera `uv.lock` no patch/minor mais novo permitido pelos ranges; commita o `uv.lock` junto |
| Atualizar **uma** dependência específica | `uv lock --upgrade-package <nome> && uv sync --extra test` | Só bumpa `<nome>` (e suas transitivas); útil para patches de segurança pontuais |
| Adicionar nova dependência de produção | `uv add <pacote>` | Atualiza `pyproject.toml` **e** `uv.lock`; commita ambos |
| Adicionar dependência só para testes | `uv add --optional test <pacote>` | Atualiza `[project.optional-dependencies].test` + lockfile |
| Remover dependência | `uv remove <pacote>` | Limpa `pyproject.toml` e `uv.lock` |
| Subir um range (ex.: `fastapi>=0.115` -> `>=0.120`) | Edite `pyproject.toml`, depois `uv lock && uv sync --extra test` | Necessário quando o upgrade exige relaxar o range; review manual obrigatório |
| Ver o que mudaria sem aplicar | `uv lock --upgrade --dry-run` | Mostra o diff de `uv.lock` sem escrever o arquivo |
| Auditoria de vulnerabilidades | `uv run --with pip-audit pip-audit` | Roda `pip-audit` em um ambiente efêmero sem poluir o `.venv` |

**Checklist após qualquer upgrade** (antes de abrir a PR):

1. `uv sync --extra test --frozen` -- confirma que `uv.lock` resolve sem tocar nada.
2. `make check` (lint + contratos de arquitetura + mypy + bandit + unitarios) -- nenhuma regressao de tipo/estilo/seguranca.
3. `make test-integ` -- integracao com Postgres real sob as novas versoes.
4. `uv run --with pip-audit pip-audit` -- sem CVEs de severidade alta ou crítica nas novas versões.
5. Commite `pyproject.toml` (se mudou) e `uv.lock` juntos, com mensagem do tipo `chore(deps): bump <pacote> to <versao>` ou `chore(deps): monthly lock refresh`.

Para um refresh periódico completo (recomendado mensalmente ou após
qualquer CVE relevante):

```bash
uv lock --upgrade && uv sync --extra test && make all && uv run --with pip-audit pip-audit
```

> [↑ Raiz do projeto](../README.md)
