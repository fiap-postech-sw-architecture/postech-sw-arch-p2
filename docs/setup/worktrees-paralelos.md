# Worktrees paralelos — guia rapido

Como rodar varios worktrees do mesmo repositorio em paralelo, cada um com sua propria stack `docker compose` no host, sem colisao de portas.

## Por que parametrizar portas

`docker-compose.yml` mapeia tres portas pro host: `app` em 8000, `postgres` em 5432, `ui` em 8080. Dois `docker compose up` simultaneos no mesmo host falham com `bind: address already in use`. Em testes (testcontainers) nao tem esse problema -- portas sao efemeras. Mas para `make up` / `make reset-db` / `make full-test` em multiplos worktrees, o host precisa de portas distintas por slot.

A partir desta versao, as tres portas leem de variaveis de ambiente com defaults retro-compativeis. Sem `.env.dev`, tudo continua em 8000/5432/8080.

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

`docker compose` deriva o nome do projeto do nome da pasta (`postech-sw-arch-p1-review.wt-83`), entao volumes (`postgres_data`) e containers (`<projeto>-app-1` etc.) ja sao isolados por worktree automaticamente. Voce so precisa garantir que as portas do host nao colidam.

## Tabela de slots sugerida

Reserve um slot por worktree ao iniciar para nao colidir entre si:

| Slot | APP_PORT | DB_PORT | UI_PORT | BACKEND_URL |
|---|---|---|---|---|
| 1 (default) | 8000 | 5432 | 8080 | http://localhost:8000 |
| 2 | 8002 | 5433 | 8081 | http://localhost:8002 |
| 3 | 8003 | 5434 | 8082 | http://localhost:8003 |
| 4 | 8004 | 5435 | 8083 | http://localhost:8004 |
| 5 | 8005 | 5436 | 8084 | http://localhost:8005 |
| 6 | 8006 | 5437 | 8085 | http://localhost:8006 |

Slot 2 pula `:8001` porque `UVICORN_PORT=8001` ja eh o default para uvicorn local fora do docker (ver `.env.dev.example`).

## O que NAO precisa parametrizar

- **testcontainers** (`make test-integ`, `make test-all`): pega porta efemera por sessao do pytest. Roda paralelo sem ajuste.
- **bandit, pip-audit, gitleaks** (issues #103, #104, #105): nao precisam de servico ativo, leem so arquivos.
- **`uv sync`, `make lint`, `make typecheck`, `make format`**: nao tocam em rede.

## Cuidados

- **Mesma branch nao pode estar em dois worktrees.** `git worktree add` exige branch propria.
- **Docker daemon e compartilhado.** `docker build` em paralelo funciona; tag a imagem do trivy com hash do commit (ex.: `pytstop:$(git rev-parse --short HEAD)`) para nao sobrescrever entre worktrees.
- **`postgres_data` por slot.** O nome do volume eh prefixado pelo project name, entao slots tem dados isolados. Se quiser zerar so o slot 2: `cd .../wt-83 && docker compose down -v`.
- **`/etc/hosts`** nao precisa de mudanca -- todos respondem em `localhost` em portas distintas.

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
