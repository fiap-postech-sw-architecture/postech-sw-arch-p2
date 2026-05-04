# Worktrees paralelos — guia rápido

> [↑ Raiz do projeto](../../README.md)

Como rodar vários worktrees do mesmo repositório em paralelo, cada um com sua própria stack `docker compose` no host, sem colisão de portas.

## Por que parametrizar portas

`docker-compose.yml` mapeia três portas pro host: `app` em 8000, `postgres` em 5432, `ui` em 8080. Dois `docker compose up` simultâneos no mesmo host falham com `bind: address already in use`. Em testes (testcontainers) não tem esse problema -- portas são efêmeras. Mas para `make up` / `make reset-db` / `make full-test` em múltiplos worktrees, o host precisa de portas distintas por slot.

A partir desta versão, as três portas leem de variáveis de ambiente com defaults retro-compatíveis. Sem `.env.dev`, tudo continua em 8000/5432/8080.

## Setup do worktree

```bash
cd ~/git/fiap/postech-sw-architecture/postech-sw-arch-p1-review

# cria worktree em pasta irma com branch propria
git worktree add ../postech-sw-arch-p1-review.wt-83 -b fix/issue-83
cd ../postech-sw-arch-p1-review.wt-83

# .env.dev (ja gera o default; ajuste se quiser portas customizadas)
cp .env.dev.example .env.dev

# se for rodar `docker compose up` neste worktree, escolha um slot
echo 'APP_PORT=8002' >> .env.dev
echo 'DB_PORT=5433'  >> .env.dev
echo 'UI_PORT=8081'  >> .env.dev
echo 'BACKEND_URL=http://localhost:8002' >> .env.dev
```

`docker compose` deriva o nome do projeto do nome da pasta (`postech-sw-arch-p1-review.wt-83`), então volumes (`postgres_data`) e containers (`<projeto>-app-1` etc.) já são isolados por worktree automaticamente. Você só precisa garantir que as portas do host não colidam.

## Tabela de slots sugerida

Reserve um slot por worktree ao iniciar para não colidir entre si:

| Slot | APP_PORT | DB_PORT | UI_PORT | BACKEND_URL |
|---|---|---|---|---|
| 1 (default) | 8000 | 5432 | 8080 | http://localhost:8000 |
| 2 | 8002 | 5433 | 8081 | http://localhost:8002 |
| 3 | 8003 | 5434 | 8082 | http://localhost:8003 |
| 4 | 8004 | 5435 | 8083 | http://localhost:8004 |
| 5 | 8005 | 5436 | 8084 | http://localhost:8005 |
| 6 | 8006 | 5437 | 8085 | http://localhost:8006 |

Slot 2 pula `:8001` porque `UVICORN_PORT=8001` já é o default para uvicorn local fora do docker (ver `.env.dev.example`).

## O que NÃO precisa parametrizar

- **testcontainers** (`make test-integ`, `make test-all`): pega porta efêmera por sessão do pytest. Roda paralelo sem ajuste.
- **bandit, pip-audit, gitleaks** (issues #103, #104, #105): não precisam de serviço ativo, leem só arquivos.
- **`uv sync`, `make lint`, `make typecheck`, `make format`**: não tocam em rede.

## Cuidados

- **Mesma branch não pode estar em dois worktrees.** `git worktree add` exige branch própria.
- **Docker daemon é compartilhado.** `docker build` em paralelo funciona; tag a imagem do trivy com hash do commit (ex.: `pytstop:$(git rev-parse --short HEAD)`) para não sobrescrever entre worktrees.
- **`postgres_data` por slot.** O nome do volume é prefixado pelo project name, então slots têm dados isolados. Se quiser zerar só o slot 2: `cd .../wt-83 && docker compose down -v`.
- **`/etc/hosts`** não precisa de mudança -- todos respondem em `localhost` em portas distintas.

## Limpeza

```bash
# remove um worktree (so apaga a pasta + ref interna; nao deleta a branch)
git worktree remove ../postech-sw-arch-p1-review.wt-83

# se a branch acabou (PR mergeada e deletada no remote)
git branch -D fix/issue-83
git worktree prune
```

## Referencias

- `docker-compose.yml` -- portas parametrizadas
- `.env.dev.example` -- vars com defaults
- `Makefile` (`reset-db`) -- usa `APP_PORT`/`UI_PORT` no health-poll e no echo final
- [git-worktree(1)](https://git-scm.com/docs/git-worktree)

> [↑ Raiz do projeto](../../README.md)
