# Fast Check -- Pre-requisitos: Docker/GH account no repo

Stack completa (db seedada + backend + UI) em 2 comandos, puxando do GHCR. Sem build local, sem `.env`.

## 1. Login no GHCR (uma vez)

As imagens sao **privadas** -- precisa autenticar. Forma mais simples:

```bash
docker login ghcr.io -u <SEU_GH_USER>
```

Quando pedir password, **cole um Personal Access Token (classic) com
escopo `read:packages`**, NAO sua senha do GitHub (GitHub nao aceita
password em registry desde 2021). Pra criar o token:
[github.com/settings/tokens/new](https://github.com/settings/tokens/new?scopes=read:packages&description=ghcr-pull).

## 2. Subir a stack

A partir da raiz do repo clonado:

```bash
cd db-image
docker compose up -d --wait
```

`--wait` segura o terminal ate todos os servicos passarem no healthcheck (~15-30s no x86 nativo, ate ~60s em amd64 emulando arm64 via QEMU). Quando o prompt volta, ja pode abrir o browser sem risco de `ERR_EMPTY_RESPONSE`.

Cada servico imprime a SHA do commit no startup:

```
postgres-1  | >>> pytstop seeded DB | commit 3d94aff26b7b | 2026-05-03T19:31:37-03:00
app-1       | >>> pytstop app | commit 3d94aff26b7b | 2026-05-03T19:31:37-03:00
app-1       | >>> pytstop server | commit 3d94aff26b7b | 2026-05-03T19:31:37-03:00
ui-1        | >>> pytstop ui | commit 3d94aff26b7b | 2026-05-03T19:31:37-03:00
```

## 3. Abrir as URLs

| | |
|---|---|
| **UI (NiceGUI)** | http://localhost:8080 -- login: `admin@pytstop.dev` / `admin-dev-pass-2026` (atalho `ADMIN` na tela tambem loga direto) |
| **Swagger / OpenAPI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **Health probe** | http://localhost:8000/api/v1/saude |

## 4. Exemplo de chamada API (curl)

Login -> guarda o token -> lista clientes do seed:

```bash
TOKEN=$(curl -fsS -X POST http://localhost:8000/api/v1/autenticacao/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@pytstop.dev","senha":"admin-dev-pass-2026"}' \
  | jq -r .access_token)

curl -fsSL http://localhost:8000/api/v1/clientes/ \
  -H "Authorization: Bearer $TOKEN" | jq '.total, .items[0]'
```

Saida esperada (DB seedada com 7 clientes / 10 veiculos / 8 OS em estados
variados):

```json
7
{
  "id": "18e46419-2de4-4a70-ad03-2b96dde4d7f6",
  "nome": "Rafael Costa",
  "documento_mascarado": "***.***.***-05",
  "tipo_documento": "cpf",
  ...
}
```

## 5. Validar a versao

A SHA do commit aparece em 3 lugares: nos logs de boot (acima), no rodape da pagina de login da UI (`vXXXXXXXXXXXX`), e no LABEL OCI das 3 imagens:

```bash
docker inspect ghcr.io/jbamaral/postech-sw-arch-p1-app:latest \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```

Em runtime, tambem da `docker exec <container> printenv PYTSTOP_GIT_SHA`.

## 6. Derrubar

```bash
docker compose down
```

Sem volume nomeado -- a DB e re-seedada do dump em todo `docker compose
up`. Pra persistir entre runs, use `docker compose stop` / `start` em vez
de `down`.

## Troubleshooting

| Sintoma | Causa provavel | Acao |
|---|---|---|
| `Error response from daemon: ... denied: denied` no login | Senha do GitHub em vez de PAT (GitHub depreciou password auth pra registry) | Use PAT com `read:packages`, ou `gh auth token` se tem `gh` CLI logado |
| `denied` no `docker pull` apos login OK | PAT logado mas sem `read:packages`, ou PAT fine-grained (so funciona pra org); ou usuario nao tem acesso ao package privado | Recrie o PAT como **classic** com `read:packages`. Se for fork: dono do package precisa adicionar voce |
| Porta 8000/8080 ja em uso | Outra stack rodando | `docker ps` pra ver, ou `APP_PORT=8001 UI_PORT=8081 docker compose up` (compose ja le essas vars) |
| UI carrega mas API falha 500 | `ENCRYPTION_KEY` divergente | Compose ja traz a key correta -- nao sobrescrever |
| Login API retorna 422 | Body usando `password` em vez de `senha` | API e pt-BR; use `{"email": "...", "senha": "..."}` |
| `docker compose up` puxa imagem stale | Cache local de uma corrida anterior | Compose tem `pull_policy: always` -- se ainda assim parecer stale, rode `docker compose pull` antes |
| Browser mostra `ERR_EMPTY_RESPONSE` em `localhost:8000/docs` logo apos `up` | Subiu sem `--wait` -- porta esta aberta (proxy do Docker) mas uvicorn ainda nao atende, especialmente sob emulacao QEMU | Suba com `docker compose up -d --wait`, ou cheque `docker compose ps` ate ver `app` como `(healthy)` antes de abrir o browser |
| `app` nunca fica `healthy` | App caiu no startup (DB unreachable, env var faltando) | `docker compose logs app` -- procure traceback Python ou erro de conexao no postgres |

## Setup completo (com source code)

Este QUICKSTART e um atalho. Pra fazer mudancas, rodar testes, debug do
loop de dev, etc., siga o **[README principal](../README.md)** que cobre
clone, `make reset-db`, `make test`, etc.
