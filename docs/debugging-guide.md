# Guia de Debugging

> [↑ Raiz do projeto](../README.md)

Referência para desenvolver localmente, rodar os testes de integração e diagnosticar os erros mais comuns quando se roda a API fora do `docker compose up` tradicional.

## Índice

- [Dois modos de rodar localmente](#dois-modos-de-rodar-localmente)
- [Socket do Docker (Colima, Docker Desktop, Linux)](#socket-do-docker-colima-docker-desktop-linux)
- [Variáveis de ambiente obrigatórias](#variaveis-de-ambiente-obrigatorias)
- [Erros 500 comuns](#erros-500-comuns)
- [Verificação end-to-end manual (curl)](#verificacao-end-to-end-manual-curl)
- [Fluxo com Claude Code (preview_start / preview_logs)](#fluxo-com-claude-code-preview_start--preview_logs)

## Dois modos de rodar localmente

### 1. Full stack via docker compose

Recomendado para smoke test antes do push. Roda exatamente como em produção -- migrations aplicadas no startup pelo `entrypoint.sh`.

```bash
docker compose up -d
# Aguardar health (~5s)
curl http://localhost:8000/api/v1/saude
```

Logs: `docker compose logs -f app`. Derrubar: `docker compose down -v` (o `-v` remove o volume do Postgres).

### 2. Postgres em container + uvicorn local com hot reload

Ideal para iteração rápida em código Python. Evita rebuild do container a cada mudança.

```bash
cp .env.dev.example .env.dev           # (opcional) override de credenciais/porta
docker compose up -d postgres          # Postgres na 5432
uv run alembic upgrade head            # migrations (ou .venv/bin/alembic)
./scripts/run-dev.sh                   # uvicorn com --reload na 8001
```

A aplicação recarrega automaticamente em cada salvamento. Os defaults do `run-dev.sh` funcionam sem `.env.dev` -- o arquivo só é necessário para sobrescrever variáveis (e.g. `UVICORN_PORT`, `JWT_SECRET` customizado). Ao terminar, `docker compose down -v` encerra o Postgres.

## Socket do Docker (Colima, Docker Desktop, Linux)

Testes de integracao usam [testcontainers](https://testcontainers.com/) que sobe um container Postgres efemero. Testcontainers precisa acessar o socket Docker para criar/destruir containers.

| Runtime | Socket padrão | Variáveis |
|---|---|---|
| Docker Desktop | `/var/run/docker.sock` | nenhuma |
| Colima (macOS) | `~/.colima/default/docker.sock` | `DOCKER_HOST`, `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` |
| Linux daemon | `/var/run/docker.sock` | nenhuma |

### Configuração permanente (Colima, macOS)

Adicione ao `~/.zshrc` ou `~/.bashrc`:

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
```

`DOCKER_HOST` diz ao cliente Docker onde achar o socket no host. `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` diz ao testcontainers qual caminho _montar dentro_ do container Ryuk (o path do socket _na VM Colima_, não no host).

### Sintomas de socket mal configurado

```
docker.errors.DockerException: Error while fetching server API version:
  ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

Ou, no Ryuk:

```
docker.errors.APIError: 500 Server Error for .../containers/.../start:
  error while creating mount source path '.../docker.sock': operation not supported
```

Solução: exportar as duas variáveis acima e reabrir o terminal (ou `source ~/.zshrc`).

## Variáveis de ambiente obrigatórias

| Variável | Obrigatória? | Default (dev) | Sintoma se ausente |
|---|---|---|---|
| `DATABASE_URL` | sim em `production`; opcional em `development`/`test` | `postgresql://pytstop:pytstop@localhost:5432/pytstop` (só quando `ENVIRONMENT` é `development`/`test`) | Em `production`: `RuntimeError: DATABASE_URL obrigatoria...` no startup. Em dev/test com URL inválida: `OperationalError: could not translate host name`. |
| `JWT_SECRET` | sim | `dev-secret-...-32-bytes...` | `RuntimeError: JWT_SECRET nao configurado` no login |
| `JWT_EXPIRATION_MINUTES` | não | `30` | -- |
| `ENVIRONMENT` | não | `development` | `/docs` e `/redoc` desabilitados em `production` |
| `CORS_ORIGINS` | não | `http://localhost:3000` | Preflight CORS falha em outros origins |
| `RUN_MIGRATIONS_ON_STARTUP` | não | `false` (compose define `true`) | Tabelas não existem; 500 no primeiro query |

JWT HS256 requer chave com pelo menos 32 bytes. O `run-dev.sh` já satisfaz esse mínimo. Em produção, gere uma chave forte (`openssl rand -hex 32`) e guarde em segredo.

Outros sintomas comuns relacionados a `DATABASE_URL`:

- `could not translate host name` -- hostname inválido (ex.: apontando para `postgres` fora da rede do compose).
- `password authentication failed for user "pytstop"` -- senha errada ou permissões do Postgres não batem com o que está no URL.
- `database "pytstop" does not exist` -- banco não foi criado (Postgres subiu mas o init script falhou, ou você apontou para um cluster diferente).
- `connection refused` -- Postgres não está rodando ou está em outra porta.

## Erros 500 comuns

### `RuntimeError: Session factory nao configurada`

Causa: o lifespan do FastAPI não chamou `configurar_session_factory()`. Isso costuma acontecer quando a aplicação é usada sem subir um servidor ASGI que inicialize o ciclo de vida (ex.: importar `src.main.app` em um script/shell sem acionar startup). `./scripts/run-dev.sh`, `uvicorn src.main:app` e rodar `python src/main.py` (que invoca `uvicorn.run(...)`) executam o lifespan normalmente.

### `sqlalchemy.exc.ProgrammingError: relation "..." does not exist`

Causa: migrations não foram aplicadas no banco apontado por `DATABASE_URL`. Solução:

```bash
uv run alembic current          # ve em que revisao esta
uv run alembic upgrade head     # aplica pendentes
```

Se `alembic current` disser `001 (head)` mas `\dt` no psql nao listar tabelas, o alembic pode ter marcado a revisao sem aplicar o DDL (bug de setup inicial). Resetar:

```bash
docker exec -it <postgres> psql -U pytstop -d pytstop -c "DROP TABLE alembic_version"
uv run alembic upgrade head
```

> Sem `uv`, os comandos acima equivalem a `.venv/bin/alembic <subcmd>` depois de `source .venv/bin/activate`.

### `sqlalchemy.orm.exc.DetachedInstanceError`

Causa: session factory sem `expire_on_commit=False` -- SQLAlchemy tenta recarregar atributos após `uow.commit()` mas a session já foi fechada.

Já corrigido em `src/compartilhado/infraestrutura/database.py`. Se voltar a aparecer, verifique que o `sessionmaker(...)` ainda contém o parâmetro `expire_on_commit=False`.

### `pydantic.errors.PydanticUserError: ... is not fully defined`

Causa: `from __future__ import annotations` em um módulo Pydantic + `UUID` (ou outro tipo) importado apenas sob `TYPE_CHECKING`. FastAPI não consegue resolver o `ForwardRef` em tempo de execução.

Solução: remover o `from __future__ import annotations` do arquivo de schemas/routers Pydantic, ou importar o tipo em tempo de execução com `# noqa: TC003`.

## Verificação end-to-end manual (curl)

Depois de subir qualquer um dos dois modos (docker compose OU uvicorn local), valide o fluxo completo:

```bash
# Assumindo app em localhost:8000 (docker) ou localhost:8001 (uvicorn).
BASE=http://localhost:8000

# 1. Criar usuario admin direto no banco (hash bcrypt).
#    gen_random_uuid() e nativo em Postgres 13+. Em versoes anteriores,
#    habilite a extensao pgcrypto antes (ver psql abaixo) ou gere o UUID em
#    Python com `python -c "import uuid; print(uuid.uuid4())"`.
HASH=$(uv run python -c "from src.autenticacao.infraestrutura.password_hasher import hash_senha; print(hash_senha('senhaforte1234'))")
PG_CONTAINER=$(docker ps --filter "name=postgres" --format "{{.Names}}" | head -1)
docker exec -i "$PG_CONTAINER" \
  psql -U pytstop -d pytstop -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
docker exec -i "$PG_CONTAINER" \
  psql -U pytstop -d pytstop -c \
  "INSERT INTO usuarios (id, email, senha_hash, papel) VALUES (gen_random_uuid(), 'admin@test.com', '$HASH', 'admin');"

# 2. Login -> token.
TOKEN=$(curl -s -X POST "$BASE/api/v1/autenticacao/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","senha":"senhaforte1234"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:30}..."

# 3. Criar servico autenticado.
curl -s -X POST "$BASE/api/v1/servicos/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nome":"Troca de oleo","descricao":"Troca completa","preco":"150.00"}' \
  | python3 -m json.tool

# 4. Listar servicos.
curl -s "$BASE/api/v1/servicos/" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Sequência esperada: 200 no login, 201 na criação, 200 na listagem com o serviço recém criado.

Se algum passo retornar 500, veja os logs: `docker compose logs app` ou o stdout do uvicorn. Cada 500 inclui um `id_requisicao` na resposta que pode ser grep-ado nos logs (structlog JSON).

## Fluxo com Claude Code (preview_start / preview_logs)

Se você usa o Claude Code, o arquivo `.claude/launch.json` deste repositório define 3 configurações de `preview_start`:

- **FastAPI (uvicorn dev server)** -- invoca `scripts/run-dev.sh`, porta 8001.
- **PostgreSQL (docker compose)** -- `docker compose up postgres`, porta 5432.
- **Full stack (docker compose)** -- `docker compose up`, porta 8000.

Uso típico durante debugging de um 500:

1. `preview_start PostgreSQL (docker compose)` -- sobe o banco.
2. `preview_start FastAPI (uvicorn dev server)` -- sobe a API com hot reload.
3. Reproduza a chamada que falha.
4. `preview_logs` com `level=error` e `search=<id_requisicao>` para extrair so o traceback relevante sem poluir o contexto.
5. Salve a correção no código -- o uvicorn recarrega sozinho. Rode o curl de novo.
6. Ao fim, `preview_stop` em cada servidor.

O `preview_logs` corta verbosidade drasticamente comparado a seguir `docker compose logs -f` manualmente, e o filtro por `search` isola o request que você está investigando.

> [↑ Raiz do projeto](../README.md)
