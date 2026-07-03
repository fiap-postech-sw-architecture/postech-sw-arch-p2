# UI de Simulação

> [↑ Raiz do projeto](../README.md)

Sandbox NiceGUI para testar manualmente a API do PytStop (sistema de oficina
mecânica: clientes, veículos, catálogo de serviços, estoque, ordens de
serviço). Dev-only — não entra no deploy do backend; coexiste com o Swagger
em `/docs`.

> **Como rodar**: o stack inteiro (postgres + backend + UI + seed) sobe com
> um único `make reset-db` -- veja
> [**Quick Start no README raiz**](../README.md#quick-start) para o caminho
> canônico, URLs e credenciais seed. Esta página cobre o que é específico da
> UI: como usar as páginas, modo híbrido para hot-reload, troubleshooting da
> UI e contribuição.

---

## Usando a UI

### Login

Na tela `/login`, clique nos atalhos **Admin**, **Atendente** ou **Mecanico**
— loga direto com a credencial seed. Ou preencha email/senha manualmente.

### Gerar dados de teste (via UI)

Logado como admin, no dashboard clique **"🎲 Gerar dados de teste"** para
popular clientes/veículos/OS. Use depois de `SKIP_DEMO=1 make reset-db` —
o fluxo padrão `make reset-db` já popula. Idempotente.

### Trocar de papel sem relogar

Dropdown **Trocar papel** no cabeçalho faz logout + login automático com
outra credencial seed. Útil pra testar RBAC.

### Páginas

| Rota | Conteúdo |
|---|---|
| `/clientes` | CRUD + veículos + ações LGPD |
| `/catalogo` | CRUD de serviços oferecidos |
| `/estoque` | CRUD + ajuste inline; itens com quantidade <= 5 em amarelo |
| `/ordens-servico` | Lista + detalhe com stepper + botões de transição (RBAC) |
| `/acompanhamento` | Público (sem auth): placa + documento -> status. Pares prontos pra testar em [`ui/seed-users.md`](seed-users.md) |

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

Se você não rodou o seed, a tela `/login` mostra um aviso em laranja.

---

## Comandos principais

| Comando | O que faz |
|---|---|
| `make up` | Sobe postgres + backend + UI em containers |
| `make down` | Derruba todos os containers |
| `make reset-db` | **Nuke + repopula** — ver [Quick start](#quick-start) |
| `make rebuild` | Força rebuild das imagens sem apagar o DB (após `git pull`) |
| `make seed-users-docker` | Popula usuários seed via container (primeira vez) |
| `make seed-demo` | Popula dados de demo via API (idempotente) |
| `make ui` | Roda só a UI localmente (sem docker) |

---

## Modo híbrido (banco docker, backend e UI locais)

Para editar código com hot-reload no backend, rode apenas o Postgres em
container e suba backend (uvicorn) e UI (`make ui`) localmente:

```bash
docker compose up -d postgres       # so o banco
uv run alembic upgrade head         # migrations (primeira vez ou pos-schema)
make seed-users                     # popula usuarios direto no DB
./scripts/run-dev.sh &              # backend em :8001 com auto-reload
make ui                             # UI em :8080
```

Nesse modo o Swagger fica em http://localhost:8001/docs. A UI usa
`BACKEND_URL=http://localhost:8001` por padrão (ver `ui/config.py`); no modo
docker o compose sobrescreve para `http://app:8000` via rede interna.

> Detalhes do dev loop completo (defaults do `run-dev.sh`, `.env.dev`,
> `JWT_SECRET`, atualizar dependencias) em
> [`docs/desenvolvimento.md`](../docs/desenvolvimento.md).

---

## Windows / sem `make`

Caminho recomendado: **Git Bash + `make`**. O setup do zero está em
[`docs/setup/windows.md`](../docs/setup/windows.md) (passo 7 instala `make`
via winget; passo 8 cobre `uv` e Git Bash). Apos esse setup, os `make`
abaixo rodam normalmente no Git Bash.

PowerShell e CMD puros **não** são suportados (os recipes dependem de bash).
WSL2 funciona identico a Linux -- veja [`docs/setup/linux.md`](../docs/setup/linux.md).

---

## Troubleshooting

### `/clientes` retorna 500 apos restart

Sintoma no log do backend: `ValueError: CPF invalido` em
`_reconstruir_documento`. Causa: `ENCRYPTION_KEY` ausente ou volátil, então
os CPFs/CNPJs cifrados não decifram após o restart.

**Fix:** `make reset-db`. Se preferir manter dados (apenas corrigir a chave),
garanta `ENCRYPTION_KEY` estável no `.env.dev` — o `.env.dev.example` já vem
com uma chave dev válida.

### Imagem docker stale apos `git pull`

Sintomas: backend 404 em endpoint novo, UI com layout antigo,
`python: can't open file '/app/scripts/<novo>.py'`. A imagem foi construída
antes dos commits atuais.

**Fix:** `make rebuild` (ou `make reset-db` se tambem quer DB limpo).

### "Usuários seed não encontrados"

Rode `make seed-users-docker`. Se persistir, confira `DATABASE_URL` no
`.env.dev`.

### Porta 8080 em uso

```bash
lsof -ti:8080 | xargs -r kill -9
# ou: UI_PORT=9090 make ui
```

### Docker nao encontra o socket

Ver [`docs/setup/troubleshooting.md`](../docs/setup/troubleshooting.md)
(Docker Desktop, Colima, `DOCKER_HOST`).

### Hot-reload da UI nao funciona

NiceGUI 2.x tem um bug com `--reload` quando rodado via `python -m ui`,
então `ui/app.py` sobe com `reload=False`. Reinicie `make ui` a cada edição.

---

## Variáveis de ambiente

| Variável | Default | Efeito |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8001` | Endereço do backend (HTTP) |
| `UI_PORT` | `8080` | Porta do NiceGUI |
| `PAINEL_MAX_ENTRADAS` | `50` | Tamanho do histórico de chamadas HTTP |
| `UI_STORAGE_SECRET` | fallback dev | Secret de cookies (só relevante fora de dev) |

`docker-compose.yml` seta `BACKEND_URL=http://app:8000` para o servico `ui`.

---

## Testes

```bash
uv run pytest tests/unitarios/ui/ -v
uv run pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=95 -m "not lento"
uv run pytest tests/unitarios/ui/ -v -m lento   # Screen via Playwright
```

Gate: 95% de cobertura em `ui/config.py`, `estado.py`, `cliente_api.py`,
`auth_guard.py`, `seed.py`. Páginas e componentes ficam em `tests/e2e_ui/`.

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

### Nova página

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

Adicione método em `ui/cliente_api.py::ClienteApi` e teste com
`httpx.MockTransport` (ver helpers existentes em
`tests/unitarios/ui/test_cliente_api.py`).

> [↑ Raiz do projeto](../README.md)
