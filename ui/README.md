# UI de Simulacao

Sandbox NiceGUI para testar manualmente a API do PytStop (sistema de oficina
mecanica: clientes, veiculos, catalogo de servicos, estoque, ordens de
servico). Dev-only — nao entra no deploy do backend; coexiste com o Swagger
em `/docs`.

---

## Quick start

Requer Docker Desktop (ou Colima) e `make`. No Windows, use Git Bash/WSL —
ver [Windows / sem make](#windows--sem-make).

```bash
make reset-db                     # sobe stack + popula DB (usuarios + demo)
open http://localhost:8080/login  # atalhos Admin / Atendente / Mecanico
```

`make reset-db` derruba qualquer stack anterior, apaga o volume do postgres,
rebuilda imagens, aguarda o backend ficar saudavel e popula usuarios + dados
de demo (7 clientes, 10 veiculos, 8 servicos, 14 itens, 8 OS em estados
variados). **Apaga todos os dados do DB local.**

Rode depois de `git pull` ou quando quiser DB limpo. Pular os dados de demo:
`SKIP_DEMO=1 make reset-db`. Derrubar tudo depois: `make down`.

### URLs

| Servico | URL |
|---|---|
| UI NiceGUI | http://localhost:8080 |
| Backend Swagger | http://localhost:8000/docs |
| Health probe | http://localhost:8000/api/v1/saude |

---

## Usando a UI

### Login

Na tela `/login`, clique nos atalhos **Admin**, **Atendente** ou **Mecanico**
— loga direto com a credencial seed. Ou preencha email/senha manualmente.

### Gerar dados de teste (via UI)

Logado como admin, no dashboard clique **"🎲 Gerar dados de teste"** para
popular clientes/veiculos/OS. Use depois de `SKIP_DEMO=1 make reset-db` —
o fluxo padrao `make reset-db` ja popula. Idempotente.

### Trocar de papel sem relogar

Dropdown **Trocar papel** no cabecalho faz logout + login automatico com
outra credencial seed. Util pra testar RBAC.

### Paginas

| Rota | Conteudo |
|---|---|
| `/clientes` | CRUD + veiculos + acoes LGPD |
| `/catalogo` | CRUD de servicos oferecidos |
| `/estoque` | CRUD + ajuste inline; itens com quantidade <= 5 em amarelo |
| `/ordens-servico` | Lista + detalhe com stepper + botoes de transicao (RBAC) |
| `/acompanhamento` | Publico (sem auth): placa + documento -> status. Pares prontos pra testar em [`ui/seed-users.md`](seed-users.md) |

---

## Credenciais seed

`make seed-users-docker` (ou qualquer comando que inclua `seed-users`)
popula os 3 usuarios abaixo. Espelhados em `ui/config.py::_USUARIOS_SEED`.

> Para a tabela completa de credenciais **e** os pares (placa, documento) das 8 OS de demo (uteis pra testar `/acompanhamento`), veja [`ui/seed-users.md`](seed-users.md).

| Papel | Email | Senha |
|---|---|---|
| admin | admin@pytstop.dev | admin-dev-pass-2026 |
| atendente | atendente@pytstop.dev | atendente-dev-pass-2026 |
| mecanico | mecanico@pytstop.dev | mecanico-dev-pass-2026 |

Se voce nao rodou o seed, a tela `/login` mostra um aviso em laranja.

---

## Comandos principais

| Comando | O que faz |
|---|---|
| `make up` | Sobe postgres + backend + UI em containers |
| `make down` | Derruba todos os containers |
| `make reset-db` | **Nuke + repopula** — ver [Quick start](#quick-start) |
| `make rebuild` | Forca rebuild das imagens sem apagar o DB (apos `git pull`) |
| `make seed-users-docker` | Popula usuarios seed via container (primeira vez) |
| `make seed-demo` | Popula dados de demo via API (idempotente) |
| `make ui` | Roda so a UI localmente (sem docker) |

---

## Modo hibrido (banco docker, backend e UI locais)

Para editar codigo com hot-reload no backend.

Requer Docker, [`uv`](https://docs.astral.sh/uv/) e Python 3.12.

```bash
docker compose up -d postgres       # so o banco
uv run alembic upgrade head         # migrations (primeira vez ou pos-schema)
make seed-users                     # popula usuarios direto no DB
./scripts/run-dev.sh &              # backend em :8001 com auto-reload
make ui                             # UI em :8080
```

Nesse modo o Swagger fica em http://localhost:8001/docs. A UI usa
`BACKEND_URL=http://localhost:8001` por padrao (ver
`ui/config.py`). No modo docker o compose sobrescreve para
`http://app:8000` via rede interna.

---

## Windows / sem `make`

**Caminho recomendado:** Git Bash + `make`.

1. [Git for Windows](https://git-scm.com/download/win) (inclui Git Bash)
2. `make` via [Scoop](https://scoop.sh) (`scoop install make`) ou
   [Chocolatey](https://chocolatey.org) (`choco install make`)
3. Docker Desktop e [`uv`](https://docs.astral.sh/uv/getting-started/installation/#windows)
4. Abra **Git Bash** (nao PowerShell/CMD) e rode os `make` normalmente

**Alternativas:**

- **WSL2** (`wsl --install` + Docker Desktop com integracao WSL) — funciona
  identico a macOS/Linux.
- **Script `./run.sh`** — bash fallback que espelha os principais targets do
  Makefile. Roda em Git Bash sem precisar instalar make:

  ```bash
  ./run.sh up              # make up
  ./run.sh reset-db        # make reset-db
  ./run.sh seed-demo       # make seed-demo
  ./run.sh help            # lista os targets suportados
  ```

PowerShell e CMD puros **nao** sao suportados (os recipes dependem de bash).

---

## Troubleshooting

### `/clientes` retorna 500 apos restart

Sintoma no log do backend: `ValueError: CPF invalido` em
`_reconstruir_documento`. Causa: `ENCRYPTION_KEY` ausente ou volatil, entao
os CPFs/CNPJs cifrados nao decifram apos o restart.

**Fix:** `make reset-db`. Se preferir manter dados (apenas corrigir a chave),
garanta `ENCRYPTION_KEY` estavel no `.env.dev` — o `.env.dev.example` ja vem
com uma chave dev valida.

### Imagem docker stale apos `git pull`

Sintomas: backend 404 em endpoint novo, UI com layout antigo,
`python: can't open file '/app/scripts/<novo>.py'`. A imagem foi construida
antes dos commits atuais.

**Fix:** `make rebuild` (ou `make reset-db` se tambem quer DB limpo).

### "Usuarios seed nao encontrados"

Rode `make seed-users-docker`. Se persistir, confira `DATABASE_URL` no
`.env.dev`.

### Porta 8080 em uso

```bash
lsof -ti:8080 | xargs -r kill -9
# ou: UI_PORT=9090 make ui
```

### Docker nao encontra o socket

Ver **Troubleshooting: Docker socket** no README raiz (Docker Desktop,
Colima, `DOCKER_HOST`).

### Hot-reload da UI nao funciona

NiceGUI 2.x tem um bug com `--reload` quando rodado via `python -m ui`,
entao `ui/app.py` sobe com `reload=False`. Reinicie `make ui` a cada edicao.

---

## Variaveis de ambiente

| Variavel | Default | Efeito |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8001` | Endereco do backend (HTTP) |
| `UI_PORT` | `8080` | Porta do NiceGUI |
| `PAINEL_MAX_ENTRADAS` | `50` | Tamanho do historico de chamadas HTTP |
| `UI_STORAGE_SECRET` | fallback dev | Secret de cookies (so relevante fora de dev) |

`docker-compose.yml` seta `BACKEND_URL=http://app:8000` para o servico `ui`.

---

## Testes

```bash
uv run pytest tests/unitarios/ui/ -v
uv run pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=95 -m "not lento"
uv run pytest tests/unitarios/ui/ -v -m lento   # Screen via Playwright
```

Gate: 95% de cobertura em `ui/config.py`, `estado.py`, `cliente_api.py`,
`auth_guard.py`, `seed.py`. Paginas e componentes ficam em `tests/e2e_ui/`.

---

## Para contribuidores

### Arquitetura

Processo Python separado do backend; fala com a API via `httpx` e serve
NiceGUI via WebSocket para o browser (zero CORS). Design completo em
[`docs/superpowers/specs/2026-04-23-ui-simulacao-design.md`](../docs/superpowers/specs/2026-04-23-ui-simulacao-design.md).

```
ui/
├── app.py              # bootstrap NiceGUI + roteamento
├── __main__.py         # entry point (python -m ui)
├── config.py           # env vars + credenciais seed
├── cliente_api.py      # httpx wrapper com captura + refresh automatico
├── estado.py           # acesso tipado a app.storage
├── auth_guard.py       # decorator @exige_autenticacao
├── seed.py             # gerador de dados de demo via API
├── paginas/            # @ui.page por rota
└── componentes/        # shell, pickers, stepper, drawer HTTP
```

### Nova pagina

```python
# ui/paginas/novo.py
from nicegui import ui
from ui.auth_guard import exige_autenticacao
from ui.componentes.cabecalho import CabecalhoApp

@ui.page("/novo")
@exige_autenticacao
def pagina_novo() -> None:
    CabecalhoApp()
    ui.label("Conteudo aqui")
```

Em `ui/app.py`: `import ui.paginas.novo as _pagina_novo  # noqa: F401`.
Em `ui/componentes/cabecalho.py::_NAV_ITEMS`: adicione a entrada da nav.

### Nova chamada ao backend

Adicione metodo em `ui/cliente_api.py::ClienteApi` e teste com
`httpx.MockTransport` (ver helpers existentes em
`tests/unitarios/ui/test_cliente_api.py`).
