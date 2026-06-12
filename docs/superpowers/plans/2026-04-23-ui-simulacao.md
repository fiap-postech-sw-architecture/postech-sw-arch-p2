# UI de Simulacao NiceGUI — Implementation Plan

> **Status: Concluido — referencia historica.** PR #81 entregou a UI; este
> plano captura o roadmap original e snippets de design intermediario.
> Para o codigo final entregue, ver `ui/` no repo. Algumas tasks foram
> reordenadas, escopos ajustados via reviews (coverage 95% em vez de 60%,
> seed maior, mascaramento de token substituido por nao-logar headers).
> A description do PR #81 + ui/README.md sao as fontes da verdade atuais.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma UI de simulacao em Python puro (NiceGUI) para testes manuais integrados das APIs do PytStop, rodando tanto local quanto em docker, com troca rapida de papel, pickers de recursos, seed de dados, painel de request/response e visualizacao da maquina de estados da OS.

**Architecture:** Processo Python separado do backend, consumindo a API via `httpx` server-to-server (zero CORS). Estrutura em `ui/` alongside `src/`, dev-only (nao entra no Dockerfile do backend). 5 PRs incrementais, cada um ponta-a-ponta testavel.

**Tech Stack:** Python 3.12, NiceGUI >=2.0, httpx >=0.27, pytest (com `httpx.MockTransport` + `nicegui.testing.Screen`), ruff/mypy/bandit strict, Docker, docker-compose.

**Spec:** `docs/superpowers/specs/2026-04-23-ui-simulacao-design.md`

---

## File Structure

**New files to create:**

```
ui/
├── __init__.py
├── __main__.py                      # entrypoint: python -m ui
├── app.py                           # NiceGUI setup + roteamento
├── config.py                        # BACKEND_URL, UI_PORT, USUARIOS_SEED
├── cliente_api.py                   # ClienteApi (httpx wrapper + captura + refresh)
├── estado.py                        # session state tipado
├── seed.py                          # gerar_dados_teste()
├── Dockerfile                       # imagem dev-only
├── README.md                        # docs tecnicas internas
├── paginas/
│   ├── __init__.py
│   ├── login.py
│   ├── dashboard.py
│   ├── clientes.py
│   ├── catalogo.py
│   ├── estoque.py
│   ├── ordens_servico.py
│   └── acompanhamento.py
└── componentes/
    ├── __init__.py
    ├── cabecalho.py                 # nav + role switcher + logout
    ├── painel_http.py               # drawer req/res
    ├── maquina_estados.py           # Transicao + TRANSICOES_POR_STATUS + helper
    ├── stepper_os.py                # visualizacao horizontal dos estados
    ├── botoes_transicao.py          # grid de botoes condicionais
    ├── picker_recurso.py            # dropdown generico com cache
    └── dialogo_confirmacao.py

scripts/
└── seed_usuarios.py                 # cria admin + atendente + mecanico

tests/unitarios/ui/
├── __init__.py
├── conftest.py                      # fixtures compartilhadas (backend mockado)
├── test_cliente_api.py
├── test_estado.py
├── test_maquina_estados.py
├── test_seed.py
├── test_drift_check.py
└── componentes/
    ├── __init__.py
    ├── test_login.py
    └── test_botoes_transicao.py
```

**Files to modify:**

- `pyproject.toml` — adicionar extra `ui`, estender mypy/ruff/bandit scopes
- `docker-compose.yml` — novo servico `ui`
- `Makefile` — targets `ui`, `seed-users`, `seed-users-docker`, `up-backend`
- `README.md` — nova secao `## UI de Simulacao` + env vars
- `.github/workflows/ci.yml` — incluir `ui/` nos jobs lint/type-check/security/test

---

## Phase 1 — Infraestrutura

Objetivo: criar a estrutura de pastas, configurar dependencias, docker, Makefile, CI, com um "hello world" NiceGUI rodando. Ponta-a-ponta testavel: `make ui` mostra uma pagina.

**Estrategia de branch**: todo o trabalho das Phases 1-5 acontece em **uma unica branch** (`feat/ui-simulacao-nicegui`). O PR e aberto so no final, apos revisao com `/code-review` sobre o diff total. Dentro da branch, cada task faz commit individual para preservar historico granular (squash merge resolve isso na hora do merge).

### Task 1.0: Criar branch de feature

**Files:**
- (nenhum — so operacao git)

- [ ] **Step 1: Confirmar que esta em main e atualizado**

```bash
git checkout main
git pull --ff-only
git status
```

Expected: working tree clean, branch atualizada com origin/main.

- [ ] **Step 2: Criar branch de feature**

```bash
git checkout -b feat/ui-simulacao-nicegui
git status
```

Expected: `On branch feat/ui-simulacao-nicegui`.

- [ ] **Step 3: (opcional) Criar worktree isolada**

Se preferir usar worktree separada para nao misturar com outros trabalhos:

```bash
git worktree add ../postech-sw-arch-p1-ui-worktree feat/ui-simulacao-nicegui
cd ../postech-sw-arch-p1-ui-worktree
```

Caso contrario, continuar no diretorio atual.

### Task 1.1: Adicionar extra `ui` ao pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Adicionar dependencia opcional `ui`**

Em `pyproject.toml`, logo apos o bloco `[project.optional-dependencies].test`, adicionar:

```toml
[project.optional-dependencies.ui]
# Extra opcional para a UI de simulacao (dev-only, nao entra em producao).
# Instale com: uv sync --extra test --extra ui
ui = [
    "nicegui>=2.0,<3",
]
```

(Observacao: `httpx>=0.27` ja esta listado em `test`. A UI reusa o mesmo `httpx`, nao duplica.)

- [ ] **Step 2: Rodar uv lock + sync**

```bash
uv lock
uv sync --extra test --extra ui
```

Expected: `uv.lock` atualizado, `nicegui` instalado no `.venv`.

- [ ] **Step 3: Verificar import funciona**

```bash
uv run python -c "import nicegui; print(nicegui.__version__)"
```

Expected: versao `2.x.x` impressa sem erro.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(ui): add nicegui as optional 'ui' extra"
```

### Task 1.2: Estender ruff/mypy/bandit para `ui/`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Atualizar scope de ferramentas**

Em `pyproject.toml`:

```toml
# (no bloco [tool.ruff.lint.isort])
known-first-party = ["src", "ui"]

# (adicionar em [tool.mypy.overrides])
[[tool.mypy.overrides]]
module = "nicegui.*"
ignore_missing_imports = true

# (bloco novo)
[tool.coverage.run]
source = ["src", "ui"]
omit = ["tests/*", "*/migrations/*", "*/__init__.py"]

[tool.coverage.paths]
src = ["src/"]
ui = ["ui/"]
```

Nota: a meta de cobertura `fail_under = 95` permanece no bloco `[tool.coverage.report]`. A meta separada por path (95% src, 60% ui) sera feita via `.coveragerc` em task posterior.

- [ ] **Step 2: Criar `ui/` com `__init__.py` vazio para validar o lint**

```bash
mkdir -p ui
touch ui/__init__.py
```

- [ ] **Step 3: Rodar lint/mypy pra confirmar que nao quebra**

```bash
uv run ruff check src/ ui/ tests/
uv run mypy src/ ui/
```

Expected: ambos passam sem erros.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml ui/__init__.py
git commit -m "chore(ui): extend ruff/mypy/coverage scope to ui/"
```

### Task 1.3: Criar estrutura de diretorios `ui/`

**Files:**
- Create: `ui/paginas/__init__.py`
- Create: `ui/componentes/__init__.py`
- Create: `tests/unitarios/ui/__init__.py`
- Create: `tests/unitarios/ui/componentes/__init__.py`

- [ ] **Step 1: Criar diretorios e `__init__.py` vazios**

```bash
mkdir -p ui/paginas ui/componentes
mkdir -p tests/unitarios/ui/componentes
touch ui/paginas/__init__.py
touch ui/componentes/__init__.py
touch tests/unitarios/ui/__init__.py
touch tests/unitarios/ui/componentes/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add ui/ tests/unitarios/ui/
git commit -m "chore(ui): create directory scaffolding for ui package and tests"
```

### Task 1.4: Criar `ui/config.py` com defaults e validacao

**Files:**
- Create: `ui/config.py`
- Create: `tests/unitarios/ui/test_config.py`

- [ ] **Step 1: Escrever teste que falha**

Criar `tests/unitarios/ui/test_config.py`:

```python
from __future__ import annotations

from ui.config import Config, UsuarioSeed


def test_config_usa_defaults_quando_env_vazio() -> None:
    cfg = Config.from_env(env={})
    assert cfg.backend_url == "http://localhost:8001"
    assert cfg.ui_port == 8080
    assert cfg.painel_max_entradas == 50


def test_config_respeita_env_vars() -> None:
    cfg = Config.from_env(
        env={
            "BACKEND_URL": "http://app:8000",
            "UI_PORT": "9000",
            "PAINEL_MAX_ENTRADAS": "100",
        }
    )
    assert cfg.backend_url == "http://app:8000"
    assert cfg.ui_port == 9000
    assert cfg.painel_max_entradas == 100


def test_config_expoe_usuarios_seed_dos_3_papeis() -> None:
    cfg = Config.from_env(env={})
    assert set(cfg.usuarios_seed.keys()) == {"admin", "atendente", "mecanico"}
    for papel, usuario in cfg.usuarios_seed.items():
        assert isinstance(usuario, UsuarioSeed)
        assert usuario.papel == papel
        assert len(usuario.senha) >= 12
        assert "@" in usuario.email
```

- [ ] **Step 2: Rodar o teste (deve falhar)**

```bash
uv run pytest tests/unitarios/ui/test_config.py -v --no-lint
```

Expected: `ImportError: cannot import name 'Config' from 'ui.config'`.

- [ ] **Step 3: Implementar `ui/config.py`**

```python
"""Configuracao da UI de simulacao (dev-only).

Le env vars com defaults razoaveis para dev local. Credenciais dos usuarios
seed sao FIXAS por design: esta UI e ferramenta de dev e espelha o que
``scripts/seed_usuarios.py`` popula no banco.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

Papel = Literal["admin", "atendente", "mecanico"]


@dataclass(frozen=True)
class UsuarioSeed:
    """Credenciais fixas de um usuario dev usado pelo role switcher."""

    email: str
    senha: str
    papel: Papel


# Credenciais fixas dev-only. NUNCA promover pra producao. Elas sao
# usadas ao mesmo tempo pelo ``scripts/seed_usuarios.py`` (pra popular
# o banco) e pelo switcher de papel na UI (pra relogar). A senha tem
# >=12 chars pra passar na validacao do backend.
_USUARIOS_SEED: dict[Papel, UsuarioSeed] = {
    "admin": UsuarioSeed(
        email="admin@pytstop.local",
        senha="admin-dev-pass-2026",
        papel="admin",
    ),
    "atendente": UsuarioSeed(
        email="atendente@pytstop.local",
        senha="atendente-dev-pass-2026",
        papel="atendente",
    ),
    "mecanico": UsuarioSeed(
        email="mecanico@pytstop.local",
        senha="mecanico-dev-pass-2026",
        papel="mecanico",
    ),
}


@dataclass(frozen=True)
class Config:
    backend_url: str
    ui_port: int
    painel_max_entradas: int
    usuarios_seed: dict[Papel, UsuarioSeed] = field(
        default_factory=lambda: dict(_USUARIOS_SEED)
    )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        source = env if env is not None else dict(os.environ)
        return cls(
            backend_url=source.get("BACKEND_URL", "http://localhost:8001"),
            ui_port=int(source.get("UI_PORT", "8080")),
            painel_max_entradas=int(source.get("PAINEL_MAX_ENTRADAS", "50")),
            usuarios_seed=dict(_USUARIOS_SEED),
        )


CONFIG = Config.from_env()
```

- [ ] **Step 4: Rodar o teste (deve passar)**

```bash
uv run pytest tests/unitarios/ui/test_config.py -v --no-lint
```

Expected: 3 testes verdes.

- [ ] **Step 5: Commit**

```bash
git add ui/config.py tests/unitarios/ui/test_config.py
git commit -m "feat(ui): add Config and UsuarioSeed with env-driven defaults"
```

### Task 1.5: Criar `ui/app.py` e `ui/__main__.py` com hello world

**Files:**
- Create: `ui/app.py`
- Create: `ui/__main__.py`

- [ ] **Step 1: Implementar `ui/app.py`**

```python
"""Ponto de entrada da UI NiceGUI.

Define o servidor NiceGUI, roteamento basico e montagem do shell.
Por enquanto mostra apenas uma pagina root; paginas reais vem nas
proximas tasks.
"""

from __future__ import annotations

from nicegui import ui

from ui.config import CONFIG


@ui.page("/")
def pagina_root() -> None:
    """Hello world placeholder, substituido pelo dashboard na Phase 2."""
    ui.label("PytStop — UI de Simulacao").classes("text-2xl font-bold")
    ui.label(f"Backend: {CONFIG.backend_url}")


def executar() -> None:
    """Inicia o servidor NiceGUI na porta configurada."""
    ui.run(
        title="PytStop UI",
        port=CONFIG.ui_port,
        reload=True,
        show=False,
        favicon="🔧",
    )
```

- [ ] **Step 2: Implementar `ui/__main__.py`**

```python
"""Permite rodar ``python -m ui`` a partir do workspace root."""

from __future__ import annotations

from ui.app import executar

if __name__ in {"__main__", "__mp_main__"}:
    executar()
```

Observacao: NiceGUI com `reload=True` importa o modulo de entrada no subprocesso de reload com nome `__mp_main__`; o check duplo e idiomatico.

- [ ] **Step 3: Verificar inicializacao local**

```bash
uv run python -m ui &
SERVER_PID=$!
sleep 3
curl -sf http://localhost:8080/ > /dev/null && echo OK || echo FAIL
kill $SERVER_PID
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add ui/app.py ui/__main__.py
git commit -m "feat(ui): add nicegui app entrypoint with placeholder root page"
```

### Task 1.6: Criar `ui/Dockerfile` dev-only

**Files:**
- Create: `ui/Dockerfile`

- [ ] **Step 1: Escrever Dockerfile**

```dockerfile
# NOT FOR PRODUCTION DEPLOY — dev/testing tool only.
# Esta imagem serve a UI de simulacao NiceGUI consumindo o backend
# PytStop via HTTP. Nao deve ser promovida para publicos externos.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Instala uv via bin estatico (mesma abordagem do Dockerfile do backend).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Aproveita cache em duas camadas: lock primeiro, fonte depois.
COPY pyproject.toml uv.lock ./
RUN uv sync --extra ui --frozen --no-dev

# Copia apenas o que a UI precisa.
COPY ui /app/ui

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["python", "-m", "ui"]
```

- [ ] **Step 2: Build local pra sanity check**

```bash
docker build -f ui/Dockerfile -t pytstop-ui:local .
```

Expected: build ok (pode levar ~60s na primeira vez).

- [ ] **Step 3: Commit**

```bash
git add ui/Dockerfile
git commit -m "feat(ui): add dev-only Dockerfile for the simulation UI"
```

### Task 1.7: Adicionar servico `ui` ao docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Adicionar servico**

No final de `docker-compose.yml`, antes do bloco `volumes`:

```yaml
  ui:
    build:
      context: .
      dockerfile: ui/Dockerfile
    ports:
      - "8080:8080"
    depends_on:
      app:
        condition: service_started
    environment:
      - BACKEND_URL=http://app:8000
      - UI_PORT=8080
```

- [ ] **Step 2: Subir tudo e verificar**

```bash
docker compose up -d
sleep 10
curl -sf http://localhost:8080/ > /dev/null && echo UI_OK
curl -sf http://localhost:8000/api/v1/saude > /dev/null && echo BACKEND_OK
curl -sf http://localhost:8000/docs > /dev/null && echo SWAGGER_OK
docker compose down
```

Expected: `UI_OK`, `BACKEND_OK`, `SWAGGER_OK`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(ui): add ui service to docker-compose"
```

### Task 1.8: Adicionar Makefile targets

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Adicionar targets e atualizar `.PHONY`**

Na linha `.PHONY:`, adicionar `ui seed-users seed-users-docker up-backend`:

```make
.PHONY: lint format typecheck security test test-integ test-all check all up down seed ui seed-users seed-users-docker up-backend
```

Ao final do arquivo, adicionar:

```make
ui:
	$(PY)python -m ui

seed-users:
	@bash -c 'set -a; [ -f .env ] && . ./.env; [ -f .env.dev ] && . ./.env.dev; set +a; $(PY)python scripts/seed_usuarios.py'

seed-users-docker:
	docker compose exec app python scripts/seed_usuarios.py

up-backend:
	@bash -c 'source scripts/docker-check.sh && docker compose up -d postgres app'
```

- [ ] **Step 2: Verificar targets existem**

```bash
make -n ui seed-users seed-users-docker up-backend
```

Expected: cada target imprime o comando que executaria, sem erros.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "feat(ui): add ui/seed-users/up-backend makefile targets"
```

### Task 1.9: Atualizar CI para incluir `ui/`

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Estender scopes nos jobs existentes**

No job `lint`, substituir:

```yaml
      - name: Ruff check
        run: uv run ruff check src/ tests/
      - name: Ruff format check
        run: uv run ruff format --check src/ tests/
```

por:

```yaml
      - name: Install UI extra
        run: uv sync --extra test --extra ui --frozen
      - name: Ruff check
        run: uv run ruff check src/ ui/ tests/
      - name: Ruff format check
        run: uv run ruff format --check src/ ui/ tests/
```

No job `type-check`, substituir a instalacao e o mypy:

```yaml
      - name: Install dependencies from lockfile
        run: uv sync --extra test --extra ui --frozen
      - name: Mypy
        run: uv run mypy src/ ui/
```

No job `security`, substituir:

```yaml
      - name: Bandit security scan
        run: uv run bandit -r src/ ui/ -c pyproject.toml --severity-level high
```

No job `test`, estender o `uv sync` para incluir `--extra ui` e os pytests rodarao automaticamente os testes em `tests/unitarios/ui/` ja que `testpaths = ["tests"]`.

- [ ] **Step 2: Atualizar `[tool.bandit]` em `pyproject.toml`**

```toml
[tool.bandit]
targets = ["src", "ui"]
```

- [ ] **Step 3: Validar localmente que o pipeline completo passa**

```bash
uv sync --extra test --extra ui --frozen
uv run ruff check src/ ui/ tests/
uv run ruff format --check src/ ui/ tests/
uv run mypy src/ ui/
uv run bandit -r src/ ui/ -c pyproject.toml --severity-level high
uv run pytest tests/unitarios/ -x -q --no-lint
```

Expected: todos passam.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml
git commit -m "ci(ui): include ui/ in lint, type-check, security, and test jobs"
```

### Task 1.10: Atualizar README e criar `ui/README.md`

**Files:**
- Modify: `README.md`
- Create: `ui/README.md`

- [ ] **Step 1: Adicionar secao ao README raiz**

Apos a secao `## API`, inserir:

```markdown
## UI de Simulacao

Sandbox em Python puro (NiceGUI) para testes manuais integrados da API.
**Nao e artefato de producao** — nao entra no Dockerfile do backend, nao e
promovida a entregavel. Coexiste com o Swagger UI (`/docs`): Swagger e
referencia crua da API, a UI de simulacao e sandbox integrado.

### Pre-requisito

Usuarios dos 3 papeis precisam existir no banco:

```bash
make seed-users            # local (envs vem de .env/.env.dev)
make seed-users-docker     # via docker compose
```

### Rodar local

```bash
docker compose up -d postgres            # so o banco
uv run alembic upgrade head              # primeira vez
make seed-users                          # primeira vez
./scripts/run-dev.sh &                   # backend em :8001
make ui                                  # UI em :8080
```

### Rodar via docker

```bash
make up                                  # postgres + app + ui
make seed-users-docker                   # primeira vez
```

### URLs

| Servico | Local | Docker |
|---|---|---|
| UI NiceGUI | http://localhost:8080 | http://localhost:8080 |
| Backend Swagger | http://localhost:8001/docs | http://localhost:8000/docs |
| Health probe | http://localhost:8001/api/v1/saude | http://localhost:8000/api/v1/saude |

Detalhes tecnicos da UI em [`ui/README.md`](ui/README.md).
```

E estender a tabela de env vars com:

```markdown
| BACKEND_URL | URL do backend consumida pela UI | http://localhost:8001 local / http://app:8000 docker |
| UI_PORT | Porta da UI NiceGUI | 8080 |
```

- [ ] **Step 2: Criar `ui/README.md`**

```markdown
# UI de Simulacao — Docs Tecnicas

Sandbox NiceGUI para testes manuais integrados da API PytStop. Dev-only.

## Arquitetura

Ver [`docs/superpowers/specs/2026-04-23-ui-simulacao-design.md`](../docs/superpowers/specs/2026-04-23-ui-simulacao-design.md) para o design completo.

Resumo: processo Python separado do backend, consome API via `httpx`
server-to-server (zero CORS). Browser fala com NiceGUI via WebSocket.

## Estrutura

```
ui/
├── app.py              # setup NiceGUI + roteamento
├── config.py           # env vars + credenciais seed fixas
├── cliente_api.py      # httpx wrapper com captura + refresh auto
├── estado.py           # acesso tipado a app.storage (sessao, historico)
├── seed.py             # gerador de dados de teste via API
├── paginas/            # paginas NiceGUI (@ui.page)
└── componentes/        # componentes reutilizaveis (shell, pickers, etc)
```

## Como adicionar uma pagina nova

1. Criar arquivo em `ui/paginas/<nome>.py` com funcao decorada:
   ```python
   from nicegui import ui
   from ui.componentes.cabecalho import CabecalhoApp

   @ui.page("/novo")
   def pagina_novo() -> None:
       CabecalhoApp()
       ui.label("Conteudo aqui")
   ```
2. Importar em `ui/app.py` (o decorator auto-registra ao importar).
3. Adicionar entrada na nav em `ui/componentes/cabecalho.py`.

## Como adicionar chamada a um endpoint novo

1. Adicionar metodo em `ui/cliente_api.py`:
   ```python
   def listar_algo(self) -> list[AlgoResponse]:
       return self._get("/api/v1/algo")
   ```
2. Tipar a resposta com um dataclass/pydantic se util.
3. Test com `httpx.MockTransport` em `tests/unitarios/ui/test_cliente_api.py`.

## Tests

```bash
uv run pytest tests/unitarios/ui/ -v
```

Coverage alvo: 60% total, 80% nos modulos criticos (cliente_api, estado,
maquina_estados, seed). Gerenciado via `.coveragerc`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md ui/README.md
git commit -m "docs(ui): add README sections for simulation UI"
```

---

## Phase 2 — Fundacao: seed de usuarios, auth, shell, login (PR 2)

Objetivo: ter auth end-to-end — seed dos 3 papeis no banco, ClienteApi robusto com captura + refresh, estado da sessao, shell com role switcher, pagina de login funcional.

### Task 2.1: Implementar `scripts/seed_usuarios.py`

**Files:**
- Create: `scripts/seed_usuarios.py`
- Create: `tests/unitarios/scripts/test_seed_usuarios.py`

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/unitarios/scripts/test_seed_usuarios.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts import seed_usuarios


def test_cria_os_3_papeis_quando_banco_vazio() -> None:
    sessions: list[MagicMock] = []

    def session_factory() -> MagicMock:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        sessions.append(session)
        return session

    with patch.object(seed_usuarios, "UsuarioSQLAlchemyRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.email_existe.return_value = False
        mock_repo_cls.return_value = mock_repo

        relatorio = seed_usuarios.criar_usuarios_seed(
            session_factory=session_factory,
            hasher=lambda s: f"hashed-{s}",
        )

    assert relatorio.criados == 3
    assert relatorio.existentes == 0
    assert mock_repo.salvar.call_count == 3


def test_skipa_papeis_que_ja_existem() -> None:
    def session_factory() -> MagicMock:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        return session

    with patch.object(seed_usuarios, "UsuarioSQLAlchemyRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.email_existe.return_value = True
        mock_repo_cls.return_value = mock_repo

        relatorio = seed_usuarios.criar_usuarios_seed(
            session_factory=session_factory,
            hasher=lambda s: f"hashed-{s}",
        )

    assert relatorio.criados == 0
    assert relatorio.existentes == 3
    assert mock_repo.salvar.call_count == 0
```

- [ ] **Step 2: Rodar (deve falhar)**

```bash
uv run pytest tests/unitarios/scripts/test_seed_usuarios.py -v --no-lint
```

Expected: `ModuleNotFoundError: No module named 'scripts.seed_usuarios'`.

- [ ] **Step 3: Implementar `scripts/seed_usuarios.py`**

```python
"""Script de seed: cria admin + atendente + mecanico se ausentes.

Complementa ``scripts/seed_admin.py``: enquanto aquele cria o admin inicial
via env vars para bootstrap de producao, este popula os 3 papeis com
credenciais FIXAS em ``ui/config.py`` para uso exclusivo da UI de simulacao
em dev. Escreve direto no banco porque o endpoint ``/registrar`` do backend
nao aceita ``papel`` como parametro (cria sempre com papel default).

Uso:
    make seed-users                            # local (envs vem de .env)
    make seed-users-docker                     # via docker compose
    python scripts/seed_usuarios.py            # manual

Idempotencia: reruns sao no-op por UNIQUE constraint em usuarios.email.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RelatorioSeed:
    criados: int
    existentes: int

    def resumo(self) -> str:
        return f"{self.criados} criados, {self.existentes} ja existiam"


from src.autenticacao.dominio.papel import Papel  # noqa: E402
from src.autenticacao.dominio.usuario import Usuario  # noqa: E402
from src.autenticacao.infraestrutura.repository import (  # noqa: E402
    UsuarioSQLAlchemyRepository,
)

# Mapeamento de papel -> (email, senha). Espelho de ``ui/config.py``;
# manter sincronizado. Senhas dev-only com >=12 chars.
_USUARIOS_FIXOS: list[tuple[Papel, str, str]] = [
    (Papel.ADMIN, "admin@pytstop.local", "admin-dev-pass-2026"),
    (Papel.ATENDENTE, "atendente@pytstop.local", "atendente-dev-pass-2026"),
    (Papel.MECANICO, "mecanico@pytstop.local", "mecanico-dev-pass-2026"),
]


def criar_usuarios_seed(
    session_factory: Callable[[], Session],
    hasher: Callable[[str], str],
) -> RelatorioSeed:
    """Cria os 3 papeis se ausentes. Retorna contagem de criados/existentes."""
    from sqlalchemy.exc import IntegrityError

    criados = 0
    existentes = 0
    for papel, email, senha in _USUARIOS_FIXOS:
        with session_factory() as session:
            repo = UsuarioSQLAlchemyRepository(session=session)
            if repo.email_existe(email):
                existentes += 1
                continue
            usuario = Usuario.criar(
                email=email,
                senha_hash=hasher(senha),
                papel=papel,
            )
            try:
                repo.salvar(usuario)
                session.commit()
                criados += 1
            except IntegrityError:
                session.rollback()
                existentes += 1
    return RelatorioSeed(criados=criados, existentes=existentes)


def main() -> None:
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        if environment in {"development", "test"}:
            database_url = "postgresql://pytstop:pytstop@localhost:5432/pytstop"
        else:
            print("ERRO: DATABASE_URL obrigatoria fora de dev/test.")
            sys.exit(1)

    from src.autenticacao.infraestrutura.password_hasher import hash_senha
    from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
    from src.compartilhado.infraestrutura.database import (
        criar_engine,
        criar_session_factory,
    )

    iniciar_todos_mapeamentos()
    engine = criar_engine(database_url)
    try:
        relatorio = criar_usuarios_seed(
            session_factory=criar_session_factory(engine),
            hasher=hash_senha,
        )
    finally:
        engine.dispose()

    print(f"Seed de usuarios: {relatorio.resumo()}.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar teste (deve passar)**

```bash
uv run pytest tests/unitarios/scripts/test_seed_usuarios.py -v --no-lint
```

Expected: 2 testes verdes.

- [ ] **Step 5: Verificar execucao end-to-end**

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/seed_usuarios.py
uv run python scripts/seed_usuarios.py   # segundo run deve ser no-op
```

Expected: primeira execucao `3 criados, 0 ja existiam`; segunda `0 criados, 3 ja existiam`.

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_usuarios.py tests/unitarios/scripts/test_seed_usuarios.py
git commit -m "feat(seed): add seed_usuarios.py for admin+atendente+mecanico"
```

### Task 2.2: Implementar `ui/estado.py` (state management)

**Files:**
- Create: `ui/estado.py`
- Create: `tests/unitarios/ui/test_estado.py`

- [ ] **Step 1: Escrever teste que falha**

```python
# tests/unitarios/ui/test_estado.py
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ui.estado import RegistroHttp, Sessao, StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore(max_entradas_historico=3)


def test_sessao_inicial_e_vazia(store: StateStore) -> None:
    assert store.token_atual() is None
    assert store.papel_atual() is None
    assert store.email_atual() is None
    assert store.historico_http() == []


def test_salvar_sessao_persiste_campos(store: StateStore) -> None:
    store.salvar_sessao(
        Sessao(
            access_token="abc",
            refresh_token="xyz",
            email="admin@pytstop.local",
            papel="admin",
        )
    )
    assert store.token_atual() == "abc"
    assert store.refresh_token_atual() == "xyz"
    assert store.email_atual() == "admin@pytstop.local"
    assert store.papel_atual() == "admin"


def test_limpar_sessao_reseta_tudo(store: StateStore) -> None:
    store.salvar_sessao(
        Sessao(access_token="abc", refresh_token="xyz", email="a@b", papel="admin")
    )
    store.limpar_sessao()
    assert store.token_atual() is None
    assert store.papel_atual() is None


def test_registro_http_entra_no_inicio_do_historico(store: StateStore) -> None:
    r1 = _reg("GET", "/api/v1/clientes", 200)
    r2 = _reg("POST", "/api/v1/clientes", 201)
    store.registrar_chamada_http(r1)
    store.registrar_chamada_http(r2)
    hist = store.historico_http()
    assert hist[0] == r2
    assert hist[1] == r1


def test_historico_respeita_max_entradas(store: StateStore) -> None:
    for i in range(5):
        store.registrar_chamada_http(_reg("GET", f"/{i}", 200))
    assert len(store.historico_http()) == 3


def test_limpar_historico_esvazia(store: StateStore) -> None:
    store.registrar_chamada_http(_reg("GET", "/x", 200))
    store.limpar_historico_http()
    assert store.historico_http() == []


def _reg(metodo: str, caminho: str, status: int) -> RegistroHttp:
    return RegistroHttp(
        timestamp=datetime.now(UTC),
        metodo=metodo,
        caminho=caminho,
        status=status,
        duracao_ms=10,
        request_body=None,
        response_body="{}",
        papel_no_momento="admin",
    )
```

- [ ] **Step 2: Rodar teste (falha com ImportError)**

- [ ] **Step 3: Implementar `ui/estado.py`**

```python
"""State management da UI.

Abstrai o storage subjacente (em producao, ``nicegui.app.storage.user`` e
``storage.tab``; em testes, um dict in-memory). Fornece acesso tipado
para evitar que paginas toquem storage cru.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

Papel = Literal["admin", "atendente", "mecanico"]


@dataclass(frozen=True)
class Sessao:
    access_token: str
    refresh_token: str
    email: str
    papel: Papel


@dataclass(frozen=True)
class RegistroHttp:
    timestamp: datetime
    metodo: str
    caminho: str
    status: int
    duracao_ms: int
    request_body: str | None
    response_body: str
    papel_no_momento: str


class _StorageProtocol(Protocol):
    def get(self, key: str, default: object = None) -> object: ...
    def __setitem__(self, key: str, value: object) -> None: ...
    def clear(self) -> None: ...


class _DictStorage:
    """Backing store in-memory, usado em testes e como fallback."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: object) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()


_KEY_SESSAO = "sessao"


class StateStore:
    """Acesso tipado ao storage. Uma instancia por processo UI; thread-safe
    para o modelo single-user de uma sandbox de dev.
    """

    def __init__(
        self,
        user_storage: _StorageProtocol | None = None,
        tab_storage: _StorageProtocol | None = None,
        max_entradas_historico: int = 50,
    ) -> None:
        self._user = user_storage or _DictStorage()
        self._tab = tab_storage or _DictStorage()
        self._max = max_entradas_historico
        self._historico: deque[RegistroHttp] = deque(maxlen=max_entradas_historico)

    # ----- sessao -----

    def salvar_sessao(self, sessao: Sessao) -> None:
        self._user[_KEY_SESSAO] = {
            "access_token": sessao.access_token,
            "refresh_token": sessao.refresh_token,
            "email": sessao.email,
            "papel": sessao.papel,
        }

    def limpar_sessao(self) -> None:
        self._user[_KEY_SESSAO] = None

    def _sessao(self) -> dict[str, str] | None:
        valor = self._user.get(_KEY_SESSAO)
        if isinstance(valor, dict):
            return valor  # type: ignore[return-value]
        return None

    def token_atual(self) -> str | None:
        s = self._sessao()
        return s["access_token"] if s else None

    def refresh_token_atual(self) -> str | None:
        s = self._sessao()
        return s["refresh_token"] if s else None

    def email_atual(self) -> str | None:
        s = self._sessao()
        return s["email"] if s else None

    def papel_atual(self) -> Papel | None:
        s = self._sessao()
        if not s:
            return None
        papel = s["papel"]
        if papel in {"admin", "atendente", "mecanico"}:
            return papel  # type: ignore[return-value]
        return None

    def esta_autenticado(self) -> bool:
        return self.token_atual() is not None

    # ----- historico http -----

    def registrar_chamada_http(self, registro: RegistroHttp) -> None:
        self._historico.appendleft(registro)

    def historico_http(self) -> list[RegistroHttp]:
        return list(self._historico)

    def limpar_historico_http(self) -> None:
        self._historico.clear()


# Singleton lazy — inicializado com NiceGUI storage quando a app sobe.
_store: StateStore | None = None


def obter_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store


def configurar_store(store: StateStore) -> None:
    """Permite injetar um store customizado (usado em testes e no bootstrap)."""
    global _store
    _store = store
```

- [ ] **Step 4: Rodar teste (deve passar)**

- [ ] **Step 5: Commit**

```bash
git add ui/estado.py tests/unitarios/ui/test_estado.py
git commit -m "feat(ui): add StateStore with typed session and HTTP history"
```

### Task 2.3: Implementar `ui/cliente_api.py` — base + captura

**Files:**
- Create: `ui/cliente_api.py`
- Create: `tests/unitarios/ui/test_cliente_api.py`

- [ ] **Step 1: Escrever teste que falha (base + captura)**

```python
# tests/unitarios/ui/test_cliente_api.py
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from ui.cliente_api import (
    AcessoNegadoError,
    BackendInacessivelError,
    ClienteApi,
    NaoAutenticadoError,
    RateLimitExcedidoError,
    ValidacaoError,
)
from ui.estado import Sessao, StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore()


def _transport(handler):  # noqa: ANN001
    return httpx.MockTransport(handler)


def test_adiciona_bearer_token_quando_autenticado(store: StateStore) -> None:
    store.salvar_sessao(Sessao("tok", "ref", "a@b", "admin"))
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    api = ClienteApi(
        base_url="http://x",
        store=store,
        transport=_transport(handler),
    )
    api.get("/api/v1/saude")
    assert capturado["authorization"] == "Bearer tok"


def test_nao_adiciona_auth_quando_sem_sessao(store: StateStore) -> None:
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.get("/api/v1/saude")
    assert "authorization" not in capturado


def test_registra_chamada_no_historico_com_mascaramento(store: StateStore) -> None:
    store.salvar_sessao(Sessao("secret-token", "ref", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "xyz"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.post("/api/v1/clientes", json_body={"nome": "Joao"})

    hist = store.historico_http()
    assert len(hist) == 1
    r = hist[0]
    assert r.metodo == "POST"
    assert r.caminho == "/api/v1/clientes"
    assert r.status == 201
    assert r.papel_no_momento == "admin"
    assert r.request_body is not None
    assert "Joao" in r.request_body
    # Token NAO vaza
    assert "secret-token" not in r.request_body
    assert "secret-token" not in r.response_body


def test_mapeia_422_para_validacao_error(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"detail": [{"loc": ["body", "email"], "msg": "invalid"}]}
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ValidacaoError) as exc:
        api.post("/api/v1/clientes", json_body={})
    assert exc.value.detalhes[0]["msg"] == "invalid"


def test_mapeia_403_para_acesso_negado(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "atendente"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "admin required"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(AcessoNegadoError):
        api.post("/api/v1/servicos", json_body={"nome": "x"})


def test_mapeia_429_para_rate_limit(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(RateLimitExcedidoError) as exc:
        api.get("/api/v1/acompanhamento")
    assert exc.value.retry_after == 30


def test_conexao_falha_levanta_backend_inacessivel(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    api = ClienteApi(
        base_url="http://nonexistent",
        store=store,
        transport=_transport(handler),
    )
    with pytest.raises(BackendInacessivelError):
        api.get("/api/v1/saude")
```

- [ ] **Step 2: Rodar teste (falha com ImportError)**

- [ ] **Step 3: Implementar `ui/cliente_api.py`**

```python
"""Cliente HTTP centralizado da UI.

Toda chamada ao backend passa por aqui. Responsabilidades:
- injecao automatica de ``Authorization: Bearer <token>``
- captura de request/response para o painel HTTP (com mascaramento)
- mapeamento de erros HTTP para excecoes tipadas
- refresh automatico em 401 (implementado em task 2.4)
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from ui.estado import RegistroHttp, StateStore, obter_store

if TYPE_CHECKING:
    from collections.abc import Mapping


# ----- excecoes tipadas -----


class ApiError(Exception):
    """Base para erros do cliente."""


class NaoAutenticadoError(ApiError):
    """401 persistente (apos refresh falhar)."""


class AcessoNegadoError(ApiError):
    """403 — papel insuficiente."""

    def __init__(self, papel_necessario: str | None = None) -> None:
        super().__init__(f"Acesso negado. Papel necessario: {papel_necessario}")
        self.papel_necessario = papel_necessario


class ValidacaoError(ApiError):
    """422 — preserva ``detail`` do FastAPI."""

    def __init__(self, detalhes: list[dict[str, Any]]) -> None:
        super().__init__("Validacao falhou")
        self.detalhes = detalhes


class RateLimitExcedidoError(ApiError):
    """429 — retry depois do cooldown."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Rate limit. Retry em {retry_after}s")
        self.retry_after = retry_after


class BackendIndisponivelError(ApiError):
    """5xx."""


class BackendInacessivelError(ApiError):
    """Connection refused / timeout."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Backend inacessivel em {url}")
        self.url = url


# ----- cliente -----

_TOKEN_MASKED = "Bearer ****"  # noqa: S105


class ClienteApi:
    def __init__(
        self,
        base_url: str,
        store: StateStore | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._store = store or obter_store()
        self._client = httpx.Client(
            base_url=self._base_url,
            transport=transport,
            timeout=timeout,
        )

    # ----- metodos publicos por verbo -----

    def get(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("GET", path, params=params)

    def post(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("POST", path, json_body=json_body)

    def put(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("PUT", path, json_body=json_body)

    def patch(
        self, path: str, *, json_body: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("PATCH", path, json_body=json_body)

    def delete(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        return self._request("DELETE", path, params=params)

    # ----- interno -----

    def _request(
        self,
        metodo: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        headers: dict[str, str] = {}
        token = self._store.token_atual()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        inicio = time.perf_counter()
        try:
            resposta = self._client.request(
                metodo,
                path,
                headers=headers,
                params=params,
                json=json_body,
            )
        except httpx.ConnectError as exc:
            self._registrar_conexao_falhou(metodo, path, json_body, exc)
            raise BackendInacessivelError(self._base_url) from exc
        except httpx.TimeoutException as exc:
            self._registrar_conexao_falhou(metodo, path, json_body, exc)
            raise BackendInacessivelError(self._base_url) from exc

        duracao_ms = int((time.perf_counter() - inicio) * 1000)
        self._registrar(metodo, path, json_body, resposta, duracao_ms)
        return self._interpretar_resposta(resposta)

    def _interpretar_resposta(
        self, resposta: httpx.Response
    ) -> dict[str, Any] | list[Any]:
        status = resposta.status_code
        if 200 <= status < 300:
            if status == 204 or not resposta.content:
                return {}
            return resposta.json()  # type: ignore[no-any-return]
        if status == 401:
            raise NaoAutenticadoError("Nao autenticado")
        if status == 403:
            detail = _extrair_detail(resposta)
            raise AcessoNegadoError(detail)
        if status == 422:
            body = resposta.json()
            detail = body.get("detail", []) if isinstance(body, dict) else []
            raise ValidacaoError(detail if isinstance(detail, list) else [])
        if status == 429:
            retry = int(resposta.headers.get("Retry-After", "60"))
            raise RateLimitExcedidoError(retry_after=retry)
        if 500 <= status < 600:
            raise BackendIndisponivelError(f"Erro {status}")
        raise ApiError(f"Status inesperado {status}")

    def _registrar(
        self,
        metodo: str,
        path: str,
        body: Mapping[str, Any] | None,
        resposta: httpx.Response,
        duracao_ms: int,
    ) -> None:
        self._store.registrar_chamada_http(
            RegistroHttp(
                timestamp=datetime.now(UTC),
                metodo=metodo,
                caminho=path,
                status=resposta.status_code,
                duracao_ms=duracao_ms,
                request_body=_formatar_json(body) if body else None,
                response_body=_formatar_response(resposta),
                papel_no_momento=self._store.papel_atual() or "sem-sessao",
            )
        )

    def _registrar_conexao_falhou(
        self,
        metodo: str,
        path: str,
        body: Mapping[str, Any] | None,
        exc: Exception,
    ) -> None:
        self._store.registrar_chamada_http(
            RegistroHttp(
                timestamp=datetime.now(UTC),
                metodo=metodo,
                caminho=path,
                status=0,
                duracao_ms=0,
                request_body=_formatar_json(body) if body else None,
                response_body=f"CONNECTION ERROR: {exc}",
                papel_no_momento=self._store.papel_atual() or "sem-sessao",
            )
        )


def _extrair_detail(resposta: httpx.Response) -> str | None:
    try:
        body = resposta.json()
        if isinstance(body, dict):
            detail = body.get("detail")
            if isinstance(detail, str):
                return detail
    except Exception:  # noqa: BLE001
        pass
    return None


def _formatar_json(obj: object) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return str(obj)


_MAX_RESPONSE_BYTES = 10_000


def _formatar_response(resposta: httpx.Response) -> str:
    content_type = resposta.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return _formatar_json(resposta.json())[:_MAX_RESPONSE_BYTES]
        except Exception:  # noqa: BLE001
            return resposta.text[:_MAX_RESPONSE_BYTES]
    return resposta.text[:_MAX_RESPONSE_BYTES]
```

- [ ] **Step 4: Rodar teste (deve passar)**

- [ ] **Step 5: Commit**

```bash
git add ui/cliente_api.py tests/unitarios/ui/test_cliente_api.py
git commit -m "feat(ui): add ClienteApi with typed errors and HTTP capture"
```

### Task 2.4: Adicionar refresh automatico em 401

**Files:**
- Modify: `ui/cliente_api.py`
- Modify: `tests/unitarios/ui/test_cliente_api.py`

- [ ] **Step 1: Adicionar teste para refresh automatico**

Adicionar em `tests/unitarios/ui/test_cliente_api.py`:

```python
def test_401_dispara_refresh_e_retenta_uma_vez(store: StateStore) -> None:
    store.salvar_sessao(Sessao("expired", "valid-refresh", "a@b", "admin"))
    chamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "novo-token",
                    "refresh_token": "novo-refresh",
                    "token_type": "bearer",
                },
            )
        if request.headers.get("authorization") == "Bearer expired":
            return httpx.Response(401, json={"detail": "token expired"})
        if request.headers.get("authorization") == "Bearer novo-token":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(500)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    resultado = api.get("/api/v1/clientes")
    assert resultado == {"ok": True}
    assert "GET /api/v1/clientes" in chamadas[0]
    assert "POST /api/v1/autenticacao/refresh" in chamadas[1]
    assert "GET /api/v1/clientes" in chamadas[2]
    assert store.token_atual() == "novo-token"


def test_refresh_falhar_limpa_sessao_e_levanta_nao_autenticado(
    store: StateStore,
) -> None:
    store.salvar_sessao(Sessao("expired", "also-expired", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(401)
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")
    assert store.token_atual() is None


def test_401_no_proprio_refresh_nao_entra_em_loop(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "admin"))
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.post("/api/v1/autenticacao/refresh", json_body={"refresh_token": "r"})
    assert chamadas == 1
```

- [ ] **Step 2: Rodar (novos testes falham)**

- [ ] **Step 3: Implementar refresh em `_request`**

Em `ui/cliente_api.py`, substituir `_request` e adicionar metodo privado:

```python
_ROTAS_SEM_REFRESH = frozenset(
    {"/api/v1/autenticacao/refresh", "/api/v1/autenticacao/login"}
)


def _request(
    self,
    metodo: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    json_body: Mapping[str, Any] | None = None,
    _ja_tentou_refresh: bool = False,
) -> dict[str, Any] | list[Any]:
    headers: dict[str, str] = {}
    token = self._store.token_atual()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    inicio = time.perf_counter()
    try:
        resposta = self._client.request(
            metodo, path, headers=headers, params=params, json=json_body
        )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        self._registrar_conexao_falhou(metodo, path, json_body, exc)
        raise BackendInacessivelError(self._base_url) from exc

    duracao_ms = int((time.perf_counter() - inicio) * 1000)
    self._registrar(metodo, path, json_body, resposta, duracao_ms)

    if (
        resposta.status_code == 401
        and not _ja_tentou_refresh
        and path not in _ROTAS_SEM_REFRESH
        and self._store.refresh_token_atual()
    ):
        if self._tentar_refresh():
            return self._request(
                metodo,
                path,
                params=params,
                json_body=json_body,
                _ja_tentou_refresh=True,
            )
        # refresh falhou: limpa sessao e propaga
        self._store.limpar_sessao()
        raise NaoAutenticadoError("Sessao expirada")

    return self._interpretar_resposta(resposta)


def _tentar_refresh(self) -> bool:
    """Executa POST /refresh uma vez. Retorna True se atualizou tokens."""
    refresh_token = self._store.refresh_token_atual()
    if not refresh_token:
        return False
    try:
        resposta = self._client.post(
            "/api/v1/autenticacao/refresh",
            json={"refresh_token": refresh_token},
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
    if resposta.status_code != 200:
        return False
    body = resposta.json()
    # Preserva email e papel atuais; so troca os tokens.
    from ui.estado import Sessao

    email = self._store.email_atual() or ""
    papel = self._store.papel_atual() or "admin"
    self._store.salvar_sessao(
        Sessao(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            email=email,
            papel=papel,
        )
    )
    return True
```

- [ ] **Step 4: Rodar todos os testes do cliente_api**

```bash
uv run pytest tests/unitarios/ui/test_cliente_api.py -v --no-lint
```

Expected: todos verdes.

- [ ] **Step 5: Commit**

```bash
git add ui/cliente_api.py tests/unitarios/ui/test_cliente_api.py
git commit -m "feat(ui): auto-refresh access token on 401 with single retry"
```

### Task 2.5: Wrappers de auth em ClienteApi

**Files:**
- Modify: `ui/cliente_api.py`
- Modify: `tests/unitarios/ui/test_cliente_api.py`

- [ ] **Step 1: Adicionar teste**

```python
def test_login_salva_sessao_e_decodifica_papel(store: StateStore) -> None:
    # JWT payload base64 com papel=admin e email=a@b
    # {"email":"a@b","papel":"admin"} base64 sem padding:
    payload_b64 = "eyJlbWFpbCI6ImFAYiIsInBhcGVsIjoiYWRtaW4ifQ"
    fake_jwt = f"xxx.{payload_b64}.yyy"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": fake_jwt,
                "refresh_token": "r",
                "token_type": "bearer",
            },
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.login(email="a@b", senha="secret123456")
    assert store.token_atual() == fake_jwt
    assert store.email_atual() == "a@b"
    assert store.papel_atual() == "admin"


def test_logout_limpa_sessao_mesmo_se_backend_falhar(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.logout()  # nao deve levantar
    assert store.token_atual() is None
```

- [ ] **Step 2: Rodar (deve falhar — login/logout nao existem)**

- [ ] **Step 3: Implementar login/logout em `ClienteApi`**

Adicionar em `ui/cliente_api.py`:

```python
import base64
from ui.estado import Sessao


def login(self, *, email: str, senha: str) -> None:
    """Faz login e salva sessao decodificando papel do JWT."""
    resposta = self._client.post(
        "/api/v1/autenticacao/login",
        json={"email": email, "senha": senha},
    )
    if resposta.status_code != 200:
        raise NaoAutenticadoError(f"Login falhou: {resposta.status_code}")
    body = resposta.json()
    access = body["access_token"]
    papel = _extrair_papel_do_jwt(access) or "admin"
    self._store.salvar_sessao(
        Sessao(
            access_token=access,
            refresh_token=body["refresh_token"],
            email=email,
            papel=papel,
        )
    )


def logout(self) -> None:
    """Logout best-effort. Limpa sessao local mesmo se backend falhar."""
    token = self._store.token_atual()
    if token:
        try:
            self._client.post(
                "/api/v1/autenticacao/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:  # noqa: BLE001
            pass
    self._store.limpar_sessao()


def _extrair_papel_do_jwt(token: str) -> str | None:
    """Decodifica payload do JWT sem verificar assinatura."""
    try:
        partes = token.split(".")
        if len(partes) != 3:
            return None
        padded = partes[1] + "=" * (-len(partes[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        papel = payload.get("papel")
        if isinstance(papel, str) and papel in {"admin", "atendente", "mecanico"}:
            return papel
    except Exception:  # noqa: BLE001
        return None
    return None
```

Ajuste de import: adicionar `import base64` no topo.

- [ ] **Step 4: Rodar todos os testes**

- [ ] **Step 5: Commit**

```bash
git add ui/cliente_api.py tests/unitarios/ui/test_cliente_api.py
git commit -m "feat(ui): add login/logout wrappers with JWT papel extraction"
```

### Task 2.6: Wiring NiceGUI storage em `ui/app.py`

**Files:**
- Modify: `ui/app.py`

- [ ] **Step 1: Configurar store com storage real do NiceGUI**

Substituir `ui/app.py`:

```python
"""Ponto de entrada da UI NiceGUI."""

from __future__ import annotations

from nicegui import app, ui

from ui.cliente_api import ClienteApi
from ui.config import CONFIG
from ui.estado import StateStore, configurar_store


class _NiceguiStorageAdapter:
    """Adapta ``nicegui.app.storage`` ao ``_StorageProtocol`` do StateStore."""

    def __init__(self, scope: str) -> None:
        self._scope = scope

    def _backend(self) -> dict[str, object]:
        if self._scope == "user":
            return app.storage.user  # type: ignore[no-any-return]
        if self._scope == "tab":
            return app.storage.tab  # type: ignore[no-any-return]
        raise ValueError(self._scope)

    def get(self, key: str, default: object = None) -> object:
        return self._backend().get(key, default)

    def __setitem__(self, key: str, value: object) -> None:
        self._backend()[key] = value

    def clear(self) -> None:
        self._backend().clear()


def _configurar_estado() -> None:
    configurar_store(
        StateStore(
            user_storage=_NiceguiStorageAdapter("user"),
            tab_storage=_NiceguiStorageAdapter("tab"),
            max_entradas_historico=CONFIG.painel_max_entradas,
        )
    )


def obter_api() -> ClienteApi:
    """Factory do cliente HTTP — ha um por processo UI."""
    return ClienteApi(base_url=CONFIG.backend_url)


@ui.page("/")
def pagina_root() -> None:
    ui.label("PytStop — UI de Simulacao").classes("text-2xl font-bold")
    ui.label(f"Backend: {CONFIG.backend_url}")


def executar() -> None:
    _configurar_estado()
    ui.run(
        title="PytStop UI",
        port=CONFIG.ui_port,
        storage_secret="pytstop-ui-dev-only-secret-change-for-public-deploy",  # noqa: S106
        reload=True,
        show=False,
        favicon="🔧",
    )
```

- [ ] **Step 2: Confirmar que inicializa sem erro**

```bash
uv run python -m ui &
SERVER_PID=$!
sleep 3
curl -sf http://localhost:8080/ > /dev/null && echo OK
kill $SERVER_PID
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add ui/app.py
git commit -m "feat(ui): wire StateStore to nicegui app.storage scopes"
```

### Task 2.7: Componente `CabecalhoApp` (nav + role switcher + logout)

**Files:**
- Create: `ui/componentes/cabecalho.py`

- [ ] **Step 1: Implementar cabecalho**

```python
"""Cabecalho fixo da UI: nav, role switcher, identidade e logout."""

from __future__ import annotations

from nicegui import ui

from ui.config import CONFIG, Papel
from ui.estado import obter_store


_CORES_PAPEL: dict[Papel, str] = {
    "admin": "bg-red-600",
    "atendente": "bg-blue-600",
    "mecanico": "bg-green-600",
}

_NAV_ITEMS: list[tuple[str, str]] = [
    ("Dashboard", "/"),
    ("Clientes", "/clientes"),
    ("Catalogo", "/catalogo"),
    ("Estoque", "/estoque"),
    ("OS", "/ordens-servico"),
    ("Acompanhamento", "/acompanhamento"),
]


class CabecalhoApp:
    """Renderiza o cabecalho fixo. Chame no topo de cada @ui.page."""

    def __init__(self) -> None:
        store = obter_store()
        papel = store.papel_atual()
        with ui.header().classes("bg-gray-800 text-white shadow"):
            with ui.row().classes("items-center w-full gap-4 px-4"):
                ui.label("PytStop").classes("text-xl font-bold")
                with ui.row().classes("gap-2"):
                    for label, path in _NAV_ITEMS:
                        ui.link(label, path).classes("text-white no-underline px-2")

                ui.space()

                if papel:
                    self._renderizar_switcher(papel, store.email_atual() or "")
                else:
                    ui.link("Login", "/login").classes("text-white")

    def _renderizar_switcher(self, papel_atual: Papel, email: str) -> None:
        ui.badge(papel_atual, color=None).classes(
            f"{_CORES_PAPEL[papel_atual]} text-white px-3 py-1"
        )
        ui.label(email).classes("text-sm text-gray-300")
        papeis = list(CONFIG.usuarios_seed.keys())
        select = ui.select(
            papeis,
            value=papel_atual,
            label="Trocar papel",
        ).classes("w-40 bg-gray-700 text-white")
        select.on_value_change(lambda e: self._trocar_papel(e.value))
        ui.button("Logout", on_click=self._logout).classes("bg-gray-600")

    def _trocar_papel(self, novo_papel: Papel) -> None:
        from ui.app import obter_api

        api = obter_api()
        api.logout()
        usuario = CONFIG.usuarios_seed[novo_papel]
        try:
            api.login(email=usuario.email, senha=usuario.senha)
            ui.navigate.reload()
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"Falha ao trocar papel: {exc}", type="negative")

    def _logout(self) -> None:
        from ui.app import obter_api

        obter_api().logout()
        ui.navigate.to("/login")
```

- [ ] **Step 2: Commit**

```bash
git add ui/componentes/cabecalho.py
git commit -m "feat(ui): add header with nav, role switcher, and logout"
```

### Task 2.8: Pagina `/login`

**Files:**
- Create: `ui/paginas/login.py`
- Modify: `ui/app.py`
- Create: `tests/unitarios/ui/componentes/test_login.py`

- [ ] **Step 1: Escrever teste com NiceGUI Screen**

```python
# tests/unitarios/ui/componentes/test_login.py
from __future__ import annotations

import pytest
from nicegui.testing import Screen

# Marca como lento — Screen levanta browser headless.
pytestmark = pytest.mark.lento


def test_login_mostra_campos_email_e_senha(screen: Screen) -> None:
    import ui.paginas.login  # noqa: F401 — registra a pagina

    screen.open("/login")
    screen.should_contain("Entrar")
    screen.should_contain("E-mail")
    screen.should_contain("Senha")


def test_login_mostra_atalhos_dos_3_papeis(screen: Screen) -> None:
    import ui.paginas.login  # noqa: F401

    screen.open("/login")
    screen.should_contain("Admin")
    screen.should_contain("Atendente")
    screen.should_contain("Mecanico")
```

Nota: `screen` fixture vem de `nicegui.testing`; sera configurada na task 2.10.

- [ ] **Step 2: Implementar `ui/paginas/login.py`**

```python
"""Pagina de login com atalhos para os 3 papeis seed."""

from __future__ import annotations

from nicegui import ui

from ui.cliente_api import ApiError, BackendInacessivelError
from ui.config import CONFIG, Papel
from ui.estado import obter_store


@ui.page("/login")
def pagina_login() -> None:
    store = obter_store()
    if store.esta_autenticado():
        ui.navigate.to("/")
        return

    with ui.column().classes("absolute-center items-center gap-4 w-96"):
        ui.label("PytStop").classes("text-3xl font-bold")
        ui.label("UI de Simulacao").classes("text-gray-500")

        email_input = ui.input("E-mail").classes("w-full")
        senha_input = ui.input("Senha", password=True).classes("w-full")

        status_backend = ui.label("").classes("text-sm")
        _checar_backend(status_backend)

        ui.button(
            "Entrar",
            on_click=lambda: _entrar(email_input.value, senha_input.value),
        ).classes("w-full")

        ui.separator()
        ui.label("Atalhos (dev)").classes("text-sm text-gray-500")
        with ui.row().classes("gap-2 w-full justify-center"):
            for papel in ("admin", "atendente", "mecanico"):
                ui.button(
                    papel.capitalize(),
                    on_click=lambda p=papel: _entrar_como_seed(p),
                ).classes("flex-1")


def _checar_backend(label: ui.label) -> None:
    from ui.app import obter_api

    try:
        obter_api().get("/api/v1/saude")
        label.set_text("Backend online")
        label.classes(replace="text-sm text-green-600")
    except BackendInacessivelError:
        label.set_text(f"Backend offline em {CONFIG.backend_url}")
        label.classes(replace="text-sm text-red-600")
    except Exception:  # noqa: BLE001
        label.set_text("Backend indisponivel")
        label.classes(replace="text-sm text-orange-600")


def _entrar(email: str, senha: str) -> None:
    from ui.app import obter_api

    try:
        obter_api().login(email=email, senha=senha)
        ui.navigate.to("/")
    except ApiError as exc:
        ui.notify(f"Falha no login: {exc}", type="negative")


def _entrar_como_seed(papel: Papel) -> None:
    usuario = CONFIG.usuarios_seed[papel]
    _entrar(usuario.email, usuario.senha)
```

- [ ] **Step 3: Importar pagina em `ui/app.py`**

Em `ui/app.py`, adicionar apos o import de `ClienteApi`:

```python
# Registro de paginas: o decorator @ui.page executa ao importar.
import ui.paginas.login  # noqa: F401
```

- [ ] **Step 4: Smoke test manual**

```bash
uv run python -m ui &
PID=$!
sleep 3
curl -sf http://localhost:8080/login > /dev/null && echo LOGIN_OK
kill $PID
```

- [ ] **Step 5: Commit**

```bash
git add ui/paginas/login.py ui/app.py tests/unitarios/ui/componentes/test_login.py
git commit -m "feat(ui): add login page with role shortcuts and backend health check"
```

### Task 2.9: Proteger rotas autenticadas

**Files:**
- Create: `ui/auth_guard.py`
- Modify: `ui/paginas/login.py`

- [ ] **Step 1: Implementar guard**

```python
# ui/auth_guard.py
"""Redireciona para /login quando o usuario nao esta autenticado."""

from __future__ import annotations

from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from nicegui import ui

from ui.estado import obter_store

P = ParamSpec("P")
R = TypeVar("R")


def exige_autenticacao(func: Callable[P, R]) -> Callable[P, R | None]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
        if not obter_store().esta_autenticado():
            ui.navigate.to("/login")
            return None
        return func(*args, **kwargs)

    return wrapper
```

- [ ] **Step 2: Atualizar `pagina_root` para usar o guard**

Em `ui/app.py`, adicionar import e aplicar:

```python
from ui.auth_guard import exige_autenticacao


@ui.page("/")
@exige_autenticacao
def pagina_root() -> None:
    from ui.componentes.cabecalho import CabecalhoApp

    CabecalhoApp()
    with ui.column().classes("p-8 gap-4"):
        ui.label("Dashboard").classes("text-2xl font-bold")
        ui.label("Em construcao — seed data, metricas, atalhos virao nas proximas tasks.")
```

- [ ] **Step 3: Commit**

```bash
git add ui/auth_guard.py ui/app.py
git commit -m "feat(ui): add auth guard decorator and protect root page"
```

### Task 2.10: Fixture pytest pra NiceGUI Screen + marker `lento`

**Files:**
- Modify: `tests/unitarios/ui/conftest.py` (criar)
- Modify: `pyproject.toml`

- [ ] **Step 1: Criar `conftest.py` para UI**

```python
# tests/unitarios/ui/conftest.py
"""Fixtures compartilhadas dos testes da UI."""

from __future__ import annotations

import pytest

pytest_plugins = ["nicegui.testing.plugin"]


@pytest.fixture(autouse=True)
def _reset_ui_storage():  # noqa: ANN202
    """Isola o storage entre testes."""
    from ui.estado import StateStore, configurar_store

    configurar_store(StateStore())
    yield
```

- [ ] **Step 2: Registrar marker `lento` (ja esta em `pyproject.toml` via `markers`)**

Ja existe `lento: testes que demoram mais de 1s`. Nenhuma mudanca necessaria.

- [ ] **Step 3: Rodar testes da UI excluindo `lento`**

```bash
uv run pytest tests/unitarios/ui/ -v --no-lint -m "not lento"
```

Expected: passa todos os testes unitarios; testes de Screen sao ignorados.

- [ ] **Step 4: Commit**

```bash
git add tests/unitarios/ui/conftest.py
git commit -m "test(ui): add conftest with nicegui plugin and storage isolation"
```

---

## Phase 3 — CRUD simples: clientes, catalogo, estoque (PR 3)

Objetivo: paginas CRUD dos contextos de suporte, reusando um `PickerRecurso` generico. Cada pagina expoe listagem paginada, criar/editar em dialog, desativar.

### Task 3.1: `PickerRecurso[T]` generico

**Files:**
- Create: `ui/componentes/picker_recurso.py`
- Create: `tests/unitarios/ui/componentes/test_picker_recurso.py`

- [ ] **Step 1: Escrever teste**

```python
# tests/unitarios/ui/componentes/test_picker_recurso.py
from __future__ import annotations

from ui.componentes.picker_recurso import CacheRecursos


def test_cache_retorna_itens_frescos_na_primeira_chamada() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [{"id": "1", "nome": "Alfa"}]

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    items = cache.obter()
    assert items == [{"id": "1", "nome": "Alfa"}]
    assert calls == 1


def test_cache_reutiliza_antes_de_expirar() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return []

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    cache.obter()
    cache.obter()
    cache.obter()
    assert calls == 1


def test_cache_invalidar_forca_refetch() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return []

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    cache.obter()
    cache.invalidar()
    cache.obter()
    assert calls == 2
```

- [ ] **Step 2: Rodar (falha com ImportError)**

- [ ] **Step 3: Implementar**

```python
# ui/componentes/picker_recurso.py
"""Dropdown generico populado via endpoint de listagem com cache TTL."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui


@dataclass
class CacheRecursos:
    ttl_seg: int
    fetcher: Callable[[], list[dict[str, Any]]]
    _cache: list[dict[str, Any]] | None = None
    _expira_em: float = 0.0

    def obter(self) -> list[dict[str, Any]]:
        if self._cache is not None and time.monotonic() < self._expira_em:
            return self._cache
        self._cache = self.fetcher()
        self._expira_em = time.monotonic() + self.ttl_seg
        return self._cache

    def invalidar(self) -> None:
        self._cache = None
        self._expira_em = 0.0


class PickerRecurso:
    """Dropdown pra escolher um recurso por id.

    Uso:
        picker = PickerRecurso(
            rotulo="Cliente",
            fetcher=lambda: api.get("/api/v1/clientes", params={"limit": 100})["items"],
            campo_label="nome",
        )
        # picker.valor() retorna o id selecionado (UUID str) ou None
    """

    def __init__(
        self,
        *,
        rotulo: str,
        fetcher: Callable[[], list[dict[str, Any]]],
        campo_label: str = "nome",
        campo_id: str = "id",
        ttl_seg: int = 30,
    ) -> None:
        self._campo_id = campo_id
        self._campo_label = campo_label
        self._cache = CacheRecursos(ttl_seg=ttl_seg, fetcher=fetcher)
        options = self._obter_opcoes()
        with ui.row().classes("items-end gap-2"):
            self._select = ui.select(
                options=options,
                label=rotulo,
                with_input=True,
                clearable=True,
            ).classes("min-w-60")
            ui.button(icon="refresh", on_click=self._refresh).props("flat dense")

    def _obter_opcoes(self) -> dict[str, str]:
        itens = self._cache.obter()
        return {str(i[self._campo_id]): str(i[self._campo_label]) for i in itens}

    def _refresh(self) -> None:
        self._cache.invalidar()
        self._select.options = self._obter_opcoes()
        self._select.update()

    def valor(self) -> str | None:
        return self._select.value

    def set_disabled(self, disabled: bool) -> None:
        self._select.props(f'disable={str(disabled).lower()}')
```

- [ ] **Step 4: Rodar testes**

- [ ] **Step 5: Commit**

```bash
git add ui/componentes/picker_recurso.py tests/unitarios/ui/componentes/test_picker_recurso.py
git commit -m "feat(ui): add PickerRecurso component with TTL cache"
```

### Task 3.2: `DialogoConfirmacao` generico

**Files:**
- Create: `ui/componentes/dialogo_confirmacao.py`

- [ ] **Step 1: Implementar**

```python
"""Dialog generico de confirmacao pra deletes e cancelamentos."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui


def confirmar(
    *,
    titulo: str,
    mensagem: str,
    confirmar_label: str = "Confirmar",
    cancelar_label: str = "Cancelar",
    perigoso: bool = False,
    on_confirmar: Callable[[], None],
) -> None:
    """Abre um dialog modal pedindo confirmacao."""
    with ui.dialog() as dialog, ui.card():
        ui.label(titulo).classes("text-lg font-bold")
        ui.label(mensagem)
        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button(cancelar_label, on_click=dialog.close).props("flat")
            btn = ui.button(
                confirmar_label,
                on_click=lambda: _confirmar(dialog, on_confirmar),
            )
            if perigoso:
                btn.classes("bg-red-600 text-white")
    dialog.open()


def _confirmar(dialog: ui.dialog, callback: Callable[[], None]) -> None:
    dialog.close()
    callback()
```

- [ ] **Step 2: Commit**

```bash
git add ui/componentes/dialogo_confirmacao.py
git commit -m "feat(ui): add generic confirmation dialog"
```

### Task 3.3: Metodos de cliente_api para o contexto clientes

**Files:**
- Modify: `ui/cliente_api.py`
- Modify: `tests/unitarios/ui/test_cliente_api.py`

- [ ] **Step 1: Adicionar teste**

```python
def test_cliente_api_helpers_de_clientes(store):
    chamadas: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/api/v1/clientes":
            return httpx.Response(200, json={"items": [], "total": 0, "offset": 0, "limit": 20})
        if request.method == "POST":
            return httpx.Response(201, json={"id": "x"})
        return httpx.Response(200, json={})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.listar_clientes(offset=0, limit=20)
    api.criar_cliente({"nome": "Joao", "documento": "11144477735", "tipo_documento": "cpf"})
    assert ("GET", "/api/v1/clientes") in chamadas
    assert ("POST", "/api/v1/clientes") in chamadas
```

- [ ] **Step 2: Implementar helpers em `ClienteApi`**

Adicionar ao final de `ui/cliente_api.py`:

```python
# ----- helpers por contexto -----

# clientes

def listar_clientes(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    return self.get("/api/v1/clientes", params={"offset": offset, "limit": limit})  # type: ignore[return-value]

def obter_cliente(self, cliente_id: str) -> dict[str, Any]:
    return self.get(f"/api/v1/clientes/{cliente_id}")  # type: ignore[return-value]

def criar_cliente(self, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.post("/api/v1/clientes", json_body=body)  # type: ignore[return-value]

def atualizar_cliente(self, cliente_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.put(f"/api/v1/clientes/{cliente_id}", json_body=body)  # type: ignore[return-value]

def desativar_cliente(self, cliente_id: str) -> None:
    self.delete(f"/api/v1/clientes/{cliente_id}")

def listar_veiculos(self, cliente_id: str) -> list[dict[str, Any]]:
    return self.get(f"/api/v1/clientes/{cliente_id}/veiculos")  # type: ignore[return-value]

def adicionar_veiculo(self, cliente_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.post(f"/api/v1/clientes/{cliente_id}/veiculos", json_body=body)  # type: ignore[return-value]

def remover_veiculo(self, cliente_id: str, veiculo_id: str) -> None:
    self.delete(f"/api/v1/clientes/{cliente_id}/veiculos/{veiculo_id}")
```

- [ ] **Step 3: Rodar testes**

- [ ] **Step 4: Commit**

```bash
git add ui/cliente_api.py tests/unitarios/ui/test_cliente_api.py
git commit -m "feat(ui): add cliente_api helpers for clientes and veiculos"
```

### Task 3.4: Pagina `/clientes` com listagem + criar

**Files:**
- Create: `ui/paginas/clientes.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Implementar pagina**

```python
"""Pagina de listagem e gestao de clientes."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError, ValidacaoError
from ui.componentes.cabecalho import CabecalhoApp


@ui.page("/clientes")
@exige_autenticacao
def pagina_clientes() -> None:
    CabecalhoApp()
    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Clientes").classes("text-2xl font-bold")
        with ui.row().classes("gap-2"):
            ui.button(
                "Novo cliente",
                icon="add",
                on_click=lambda: _dialog_criar(refresh),
            ).classes("bg-blue-600 text-white")

        tabela_container = ui.column().classes("w-full")

        def refresh() -> None:
            tabela_container.clear()
            with tabela_container:
                _renderizar_tabela()

        refresh()


def _renderizar_tabela() -> None:
    from ui.app import obter_api

    api = obter_api()
    try:
        dados = api.listar_clientes()
    except ApiError as exc:
        ui.label(f"Erro ao listar: {exc}").classes("text-red-600")
        return

    columns = [
        {"name": "nome", "label": "Nome", "field": "nome"},
        {"name": "documento", "label": "Documento", "field": "documento"},
        {"name": "tipo_documento", "label": "Tipo", "field": "tipo_documento"},
        {"name": "contato", "label": "Contato", "field": "contato"},
    ]
    rows = dados.get("items", [])
    ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
    ui.label(f"Total: {dados.get('total', 0)}").classes("text-sm text-gray-500")


def _dialog_criar(on_sucesso) -> None:  # noqa: ANN001
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Novo cliente").classes("text-lg font-bold")
        nome = ui.input("Nome").classes("w-full")
        documento = ui.input("Documento (CPF/CNPJ)").classes("w-full")
        tipo = ui.select(["cpf", "cnpj"], label="Tipo", value="cpf").classes("w-full")
        contato = ui.input("Contato").classes("w-full")

        erros = ui.column().classes("text-red-600 text-sm")

        def salvar() -> None:
            from ui.app import obter_api

            erros.clear()
            try:
                obter_api().criar_cliente(
                    {
                        "nome": nome.value,
                        "documento": documento.value,
                        "tipo_documento": tipo.value,
                        "contato": contato.value,
                    }
                )
                dialog.close()
                ui.notify("Cliente criado", type="positive")
                on_sucesso()
            except ValidacaoError as exc:
                with erros:
                    for d in exc.detalhes:
                        ui.label(f"- {d.get('loc', [])}: {d.get('msg', '')}")
            except ApiError as exc:
                with erros:
                    ui.label(f"Erro: {exc}")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")

    dialog.open()
```

- [ ] **Step 2: Registrar em `ui/app.py`**

Adicionar:

```python
import ui.paginas.clientes  # noqa: F401
```

- [ ] **Step 3: Smoke test**

```bash
uv run python -m ui &
PID=$!
sleep 3
curl -sf http://localhost:8080/clientes > /dev/null && echo OK
kill $PID
```

- [ ] **Step 4: Commit**

```bash
git add ui/paginas/clientes.py ui/app.py
git commit -m "feat(ui): add clientes listing page and create dialog"
```

### Task 3.5: Edicao, exclusao e expansao de veiculos em `/clientes`

**Files:**
- Modify: `ui/paginas/clientes.py`

- [ ] **Step 1: Ampliar a pagina**

Substituir `_renderizar_tabela` e adicionar helpers:

```python
def _renderizar_tabela() -> None:
    from ui.app import obter_api
    from ui.componentes.dialogo_confirmacao import confirmar

    api = obter_api()
    try:
        dados = api.listar_clientes()
    except ApiError as exc:
        ui.label(f"Erro ao listar: {exc}").classes("text-red-600")
        return

    for cliente in dados.get("items", []):
        with ui.expansion(cliente["nome"], icon="person").classes("w-full"):
            with ui.row().classes("gap-4 items-start"):
                with ui.column().classes("gap-1"):
                    ui.label(f"Documento: {cliente['documento']}")
                    ui.label(f"Tipo: {cliente['tipo_documento']}")
                    ui.label(f"Contato: {cliente.get('contato', '-')}")
                ui.space()
                ui.button(
                    icon="edit",
                    on_click=lambda c=cliente: _dialog_editar(c, _refresh_global),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda c=cliente: confirmar(
                        titulo="Desativar cliente",
                        mensagem=f"Desativar {c['nome']}?",
                        perigoso=True,
                        on_confirmar=lambda cid=c["id"]: _desativar(cid),
                    ),
                ).props("flat dense")
            _renderizar_veiculos(cliente["id"])


def _dialog_editar(cliente: dict[str, Any], on_sucesso) -> None:  # noqa: ANN001
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"Editar {cliente['nome']}").classes("text-lg font-bold")
        nome = ui.input("Nome", value=cliente.get("nome", "")).classes("w-full")
        contato = ui.input("Contato", value=cliente.get("contato", "")).classes("w-full")

        def salvar() -> None:
            from ui.app import obter_api

            try:
                obter_api().atualizar_cliente(
                    cliente["id"], {"nome": nome.value, "contato": contato.value}
                )
                dialog.close()
                ui.notify("Cliente atualizado", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _desativar(cliente_id: str) -> None:
    from ui.app import obter_api

    try:
        obter_api().desativar_cliente(cliente_id)
        ui.notify("Cliente desativado", type="positive")
        _refresh_global()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _renderizar_veiculos(cliente_id: str) -> None:
    from ui.app import obter_api

    api = obter_api()
    try:
        veiculos = api.listar_veiculos(cliente_id)
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600 text-sm")
        return
    ui.label("Veiculos").classes("font-bold mt-2")
    for v in veiculos:
        with ui.row().classes("gap-2 items-center"):
            ui.label(f"{v['marca']} {v['modelo']} {v['ano']} — {v['placa']}")
            ui.button(
                icon="delete",
                on_click=lambda cid=cliente_id, vid=v["id"]: _remover_veiculo(cid, vid),
            ).props("flat dense")
    ui.button(
        "Adicionar veiculo",
        icon="add",
        on_click=lambda cid=cliente_id: _dialog_adicionar_veiculo(cid, _refresh_global),
    ).props("flat dense")


def _remover_veiculo(cliente_id: str, veiculo_id: str) -> None:
    from ui.app import obter_api

    try:
        obter_api().remover_veiculo(cliente_id, veiculo_id)
        ui.notify("Veiculo removido", type="positive")
        _refresh_global()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _dialog_adicionar_veiculo(cliente_id: str, on_sucesso) -> None:  # noqa: ANN001
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Novo veiculo").classes("text-lg font-bold")
        placa = ui.input("Placa").classes("w-full")
        marca = ui.input("Marca").classes("w-full")
        modelo = ui.input("Modelo").classes("w-full")
        ano = ui.number("Ano", value=2020, min=1950, max=2030).classes("w-full")

        def salvar() -> None:
            from ui.app import obter_api

            try:
                obter_api().adicionar_veiculo(
                    cliente_id,
                    {
                        "placa": placa.value,
                        "marca": marca.value,
                        "modelo": modelo.value,
                        "ano": int(ano.value),
                    },
                )
                dialog.close()
                ui.notify("Veiculo adicionado", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


# variavel modular para o refresh — preenchido em pagina_clientes
_refresh_global = lambda: None  # type: ignore[assignment]  # noqa: E731
```

Em `pagina_clientes`, ajustar:

```python
def refresh() -> None:
    global _refresh_global
    _refresh_global = refresh
    tabela_container.clear()
    with tabela_container:
        _renderizar_tabela()
```

- [ ] **Step 2: Commit**

```bash
git add ui/paginas/clientes.py
git commit -m "feat(ui): add cliente edit, delete, and vehicle management"
```

### Task 3.6: Helpers de cliente_api e pagina `/catalogo`

**Files:**
- Modify: `ui/cliente_api.py`
- Create: `ui/paginas/catalogo.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Adicionar helpers em `ClienteApi`**

```python
# servicos

def listar_servicos(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    return self.get("/api/v1/servicos", params={"offset": offset, "limit": limit})  # type: ignore[return-value]

def criar_servico(self, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.post("/api/v1/servicos", json_body=body)  # type: ignore[return-value]

def atualizar_servico(self, servico_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.put(f"/api/v1/servicos/{servico_id}", json_body=body)  # type: ignore[return-value]

def desativar_servico(self, servico_id: str) -> None:
    self.delete(f"/api/v1/servicos/{servico_id}")
```

- [ ] **Step 2: Implementar `ui/paginas/catalogo.py`**

```python
"""Pagina de catalogo de servicos."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.dialogo_confirmacao import confirmar


@ui.page("/catalogo")
@exige_autenticacao
def pagina_catalogo() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Catalogo de Servicos").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar(refresh)

        ui.button(
            "Novo servico",
            icon="add",
            on_click=lambda: _dialog_servico(None, refresh),
        ).classes("bg-blue-600 text-white")
        refresh()


def _renderizar(on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        dados = obter_api().listar_servicos()
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for servico in dados.get("items", []):
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label(servico["nome"]).classes("font-bold flex-1")
                ui.label(f"R$ {servico.get('preco', 0):.2f}")
                ui.button(
                    icon="edit",
                    on_click=lambda s=servico: _dialog_servico(s, on_refresh),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda s=servico: confirmar(
                        titulo="Desativar servico",
                        mensagem=f"Desativar {s['nome']}?",
                        perigoso=True,
                        on_confirmar=lambda sid=s["id"]: _desativar(sid, on_refresh),
                    ),
                ).props("flat dense")
            if servico.get("descricao"):
                ui.label(servico["descricao"]).classes("text-sm text-gray-600")


def _dialog_servico(servico: dict[str, Any] | None, on_sucesso) -> None:  # noqa: ANN001
    from ui.app import obter_api

    titulo = "Editar servico" if servico else "Novo servico"
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(titulo).classes("text-lg font-bold")
        nome = ui.input("Nome", value=(servico or {}).get("nome", "")).classes("w-full")
        descricao = ui.textarea(
            "Descricao", value=(servico or {}).get("descricao", "")
        ).classes("w-full")
        preco = ui.number(
            "Preco", value=float((servico or {}).get("preco", 0)), min=0, step=0.01
        ).classes("w-full")

        def salvar() -> None:
            body = {"nome": nome.value, "descricao": descricao.value, "preco": preco.value}
            try:
                if servico:
                    obter_api().atualizar_servico(servico["id"], body)
                else:
                    obter_api().criar_servico(body)
                dialog.close()
                ui.notify("Salvo", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _desativar(servico_id: str, on_sucesso) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        obter_api().desativar_servico(servico_id)
        ui.notify("Servico desativado", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
```

- [ ] **Step 3: Registrar em `ui/app.py`**

```python
import ui.paginas.catalogo  # noqa: F401
```

- [ ] **Step 4: Commit**

```bash
git add ui/cliente_api.py ui/paginas/catalogo.py ui/app.py
git commit -m "feat(ui): add catalogo page with CRUD of services"
```

### Task 3.7: Helpers de cliente_api e pagina `/estoque`

**Files:**
- Modify: `ui/cliente_api.py`
- Create: `ui/paginas/estoque.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Adicionar helpers em `ClienteApi`**

```python
# estoque

def listar_estoque(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    return self.get("/api/v1/estoque", params={"offset": offset, "limit": limit})  # type: ignore[return-value]

def criar_item_estoque(self, body: Mapping[str, Any]) -> dict[str, Any]:
    return self.post("/api/v1/estoque", json_body=body)  # type: ignore[return-value]

def atualizar_item_estoque(
    self, item_id: str, body: Mapping[str, Any]
) -> dict[str, Any]:
    return self.put(f"/api/v1/estoque/{item_id}", json_body=body)  # type: ignore[return-value]

def ajustar_quantidade(self, item_id: str, nova_quantidade: int) -> dict[str, Any]:
    return self.patch(  # type: ignore[return-value]
        f"/api/v1/estoque/{item_id}/quantidade",
        json_body={"nova_quantidade": nova_quantidade},
    )

def desativar_item_estoque(self, item_id: str) -> None:
    self.delete(f"/api/v1/estoque/{item_id}")
```

- [ ] **Step 2: Implementar `ui/paginas/estoque.py`**

```python
"""Pagina de gestao de estoque."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.dialogo_confirmacao import confirmar

_LIMITE_BAIXO = 5


@ui.page("/estoque")
@exige_autenticacao
def pagina_estoque() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Estoque").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar(refresh)

        ui.button(
            "Novo item",
            icon="add",
            on_click=lambda: _dialog_item(None, refresh),
        ).classes("bg-blue-600 text-white")
        refresh()


def _renderizar(on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        dados = obter_api().listar_estoque()
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for item in dados.get("items", []):
        qty = int(item.get("quantidade", 0))
        row_classes = "w-full"
        if qty < _LIMITE_BAIXO:
            row_classes += " bg-yellow-100"
        with ui.card().classes(row_classes):
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label(item["nome"]).classes("font-bold flex-1")
                ui.label(f"R$ {float(item.get('preco_unitario', 0)):.2f}")
                _controle_quantidade(item, on_refresh)
                ui.button(
                    icon="edit",
                    on_click=lambda i=item: _dialog_item(i, on_refresh),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda i=item: confirmar(
                        titulo="Desativar item",
                        mensagem=f"Desativar {i['nome']}?",
                        perigoso=True,
                        on_confirmar=lambda iid=i["id"]: _desativar(iid, on_refresh),
                    ),
                ).props("flat dense")


def _controle_quantidade(item: dict[str, Any], on_refresh) -> None:  # noqa: ANN001
    qty_input = ui.number(
        value=int(item.get("quantidade", 0)), min=0, step=1, label="Qty"
    ).classes("w-24")

    def aplicar() -> None:
        from ui.app import obter_api

        try:
            obter_api().ajustar_quantidade(item["id"], int(qty_input.value))
            ui.notify("Quantidade atualizada", type="positive")
            on_refresh()
        except ApiError as exc:
            ui.notify(f"Erro: {exc}", type="negative")

    ui.button(icon="save", on_click=aplicar).props("flat dense")


def _dialog_item(item: dict[str, Any] | None, on_sucesso) -> None:  # noqa: ANN001
    from ui.app import obter_api

    titulo = "Editar item" if item else "Novo item"
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(titulo).classes("text-lg font-bold")
        nome = ui.input("Nome", value=(item or {}).get("nome", "")).classes("w-full")
        descricao = ui.textarea(
            "Descricao", value=(item or {}).get("descricao", "")
        ).classes("w-full")
        preco = ui.number(
            "Preco unitario",
            value=float((item or {}).get("preco_unitario", 0)),
            min=0,
            step=0.01,
        ).classes("w-full")
        qty_field = None
        if item is None:
            qty_field = ui.number("Quantidade inicial", value=0, min=0, step=1).classes(
                "w-full"
            )

        def salvar() -> None:
            body: dict[str, Any] = {
                "nome": nome.value,
                "descricao": descricao.value,
                "preco_unitario": preco.value,
            }
            try:
                if item:
                    obter_api().atualizar_item_estoque(item["id"], body)
                else:
                    body["quantidade"] = int(qty_field.value) if qty_field else 0
                    obter_api().criar_item_estoque(body)
                dialog.close()
                ui.notify("Salvo", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _desativar(item_id: str, on_sucesso) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        obter_api().desativar_item_estoque(item_id)
        ui.notify("Item desativado", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
```

- [ ] **Step 3: Registrar em `ui/app.py`**

```python
import ui.paginas.estoque  # noqa: F401
```

- [ ] **Step 4: Rodar testes e smoke test**

```bash
uv run pytest tests/unitarios/ -v --no-lint -m "not lento"
uv run python -m ui &
PID=$!
sleep 3
curl -sf http://localhost:8080/estoque > /dev/null && echo OK
kill $PID
```

- [ ] **Step 5: Commit**

```bash
git add ui/cliente_api.py ui/paginas/estoque.py ui/app.py
git commit -m "feat(ui): add estoque page with CRUD and inline qty control"
```

---

## Phase 4 — Ordens de Servico e maquina de estados (PR 4)

Objetivo: pagina de OS com listagem, detalhe, stepper visual e botoes de transicao condicionais por papel e estado.

### Task 4.1: `maquina_estados.py` — Transicao + TRANSICOES_POR_STATUS

**Files:**
- Create: `ui/componentes/maquina_estados.py`
- Create: `tests/unitarios/ui/test_maquina_estados.py`

- [ ] **Step 1: Escrever testes (matriz estados × papeis)**

```python
# tests/unitarios/ui/test_maquina_estados.py
from __future__ import annotations

import pytest

from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import (
    TRANSICOES_POR_STATUS,
    obter_transicoes_validas,
)


def test_estado_recebida_admin_ve_diagnostico_e_cancelar() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "admin")
    acoes = {b.acao for b in botoes}
    assert acoes == {"diagnostico", "cancelar"}
    for b in botoes:
        assert b.habilitado is True


def test_estado_recebida_mecanico_nao_pode_cancelar() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "mecanico")
    por_acao = {b.acao: b for b in botoes}
    assert por_acao["diagnostico"].habilitado is True
    assert por_acao["cancelar"].habilitado is False


def test_estado_recebida_atendente_so_ve_tudo_desabilitado() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.RECEBIDA, "atendente")
    assert all(b.habilitado is False for b in botoes)


def test_estado_entregue_nao_tem_transicoes() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.ENTREGUE, "admin")
    assert botoes == []


def test_estado_cancelada_nao_tem_transicoes() -> None:
    botoes = obter_transicoes_validas(StatusOrdem.CANCELADA, "admin")
    assert botoes == []


def test_todos_os_estados_do_status_ordem_estao_mapeados() -> None:
    assert set(TRANSICOES_POR_STATUS.keys()) == set(StatusOrdem)


@pytest.mark.parametrize("papel", ["admin", "atendente", "mecanico"])
@pytest.mark.parametrize("status", list(StatusOrdem))
def test_matriz_completa_nao_lanca_excecao(
    status: StatusOrdem, papel: str
) -> None:
    obter_transicoes_validas(status, papel)
```

- [ ] **Step 2: Rodar (falha)**

- [ ] **Step 3: Implementar `ui/componentes/maquina_estados.py`**

```python
"""Maquina de estados da OrdemDeServico na UI.

Fonte unica de verdade das transicoes visiveis. Deve espelhar o backend —
o teste em ``tests/unitarios/ui/test_drift_check.py`` quebra o build se
um novo estado for introduzido no backend sem ser adicionado aqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.ordem_servico.dominio.status import StatusOrdem


@dataclass(frozen=True)
class Transicao:
    acao: str
    rotulo: str
    endpoint: str
    papeis_autorizados: frozenset[str]
    confirma: bool = False
    pede_motivo: bool = False
    perigoso: bool = False


@dataclass(frozen=True)
class BotaoTransicao:
    transicao: Transicao
    habilitado: bool
    motivo_bloqueio: str | None = None

    @property
    def acao(self) -> str:
        return self.transicao.acao

    @property
    def rotulo(self) -> str:
        return self.transicao.rotulo


_CANCELAR = Transicao(
    acao="cancelar",
    rotulo="Cancelar",
    endpoint="/cancelamento",
    papeis_autorizados=frozenset({"admin"}),
    confirma=True,
    pede_motivo=True,
    perigoso=True,
)

TRANSICOES_POR_STATUS: dict[StatusOrdem, list[Transicao]] = {
    StatusOrdem.RECEBIDA: [
        Transicao(
            acao="diagnostico",
            rotulo="Iniciar diagnostico",
            endpoint="/diagnostico",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ],
    StatusOrdem.EM_DIAGNOSTICO: [
        Transicao(
            acao="gerar_orcamento",
            rotulo="Gerar orcamento",
            endpoint="/orcamento",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ],
    StatusOrdem.AGUARDANDO_APROVACAO: [
        Transicao(
            acao="aprovar",
            rotulo="Aprovar orcamento",
            endpoint="/aprovacao",
            papeis_autorizados=frozenset({"admin"}),
        ),
        _CANCELAR,
    ],
    StatusOrdem.EM_EXECUCAO: [
        Transicao(
            acao="finalizar",
            rotulo="Finalizar servico",
            endpoint="/finalizacao",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        Transicao(
            acao="gerar_complementar",
            rotulo="Gerar orcamento complementar",
            endpoint="/orcamento-complementar",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        _CANCELAR,
    ],
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: [
        Transicao(
            acao="aprovar_complementar",
            rotulo="Aprovar complementar",
            endpoint="/aprovacao-complementar",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
        Transicao(
            acao="rejeitar_complementar",
            rotulo="Rejeitar complementar",
            endpoint="/rejeicao-complementar",
            papeis_autorizados=frozenset({"admin"}),
            confirma=True,
            perigoso=True,
        ),
        _CANCELAR,
    ],
    StatusOrdem.FINALIZADA: [
        Transicao(
            acao="entregar",
            rotulo="Registrar entrega",
            endpoint="/entrega",
            papeis_autorizados=frozenset({"admin", "mecanico"}),
        ),
    ],
    StatusOrdem.ENTREGUE: [],
    StatusOrdem.CANCELADA: [],
}


def obter_transicoes_validas(
    status: StatusOrdem,
    papel_atual: str,
) -> list[BotaoTransicao]:
    """Retorna botoes com enable/disable ja calculado por papel."""
    botoes: list[BotaoTransicao] = []
    for transicao in TRANSICOES_POR_STATUS.get(status, []):
        if papel_atual in transicao.papeis_autorizados:
            botoes.append(BotaoTransicao(transicao=transicao, habilitado=True))
        else:
            papeis = " ou ".join(sorted(transicao.papeis_autorizados))
            botoes.append(
                BotaoTransicao(
                    transicao=transicao,
                    habilitado=False,
                    motivo_bloqueio=f"Exige papel: {papeis}",
                )
            )
    return botoes
```

- [ ] **Step 4: Rodar testes**

- [ ] **Step 5: Commit**

```bash
git add ui/componentes/maquina_estados.py tests/unitarios/ui/test_maquina_estados.py
git commit -m "feat(ui): add OS state machine map with role-aware transitions"
```

### Task 4.2: Drift-check entre UI e backend

**Files:**
- Create: `tests/unitarios/ui/test_drift_check.py`

- [ ] **Step 1: Escrever teste**

```python
# tests/unitarios/ui/test_drift_check.py
"""Sanity check contra drift entre TRANSICOES_POR_STATUS (UI) e StatusOrdem (backend)."""

from __future__ import annotations

from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import TRANSICOES_POR_STATUS


def test_todos_estados_do_backend_tem_mapeamento_no_ui() -> None:
    estados_backend = set(StatusOrdem)
    estados_ui = set(TRANSICOES_POR_STATUS.keys())
    faltando_no_ui = estados_backend - estados_ui
    assert not faltando_no_ui, (
        f"Estados adicionados ao backend sem mapeamento no UI: {faltando_no_ui}. "
        f"Adicione entradas em ui/componentes/maquina_estados.py::TRANSICOES_POR_STATUS."
    )


def test_ui_nao_tem_estados_que_o_backend_nao_conhece() -> None:
    estados_backend = set(StatusOrdem)
    estados_ui = set(TRANSICOES_POR_STATUS.keys())
    fantasma_no_ui = estados_ui - estados_backend
    assert not fantasma_no_ui, (
        f"UI referencia estados inexistentes no backend: {fantasma_no_ui}"
    )
```

- [ ] **Step 2: Rodar**

```bash
uv run pytest tests/unitarios/ui/test_drift_check.py -v --no-lint
```

Expected: 2 testes verdes.

- [ ] **Step 3: Commit**

```bash
git add tests/unitarios/ui/test_drift_check.py
git commit -m "test(ui): add drift-check between UI state machine and backend"
```

### Task 4.3: Helpers de cliente_api para ordem_servico

**Files:**
- Modify: `ui/cliente_api.py`

- [ ] **Step 1: Adicionar helpers em `ClienteApi`**

```python
# ordens de servico

def listar_ordens(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
    return self.get("/api/v1/ordens-de-servico", params={"offset": offset, "limit": limit})  # type: ignore[return-value]

def obter_ordem(self, ordem_id: str) -> dict[str, Any]:
    return self.get(f"/api/v1/ordens-de-servico/{ordem_id}")  # type: ignore[return-value]

def criar_ordem(self, cliente_id: str, veiculo_id: str) -> dict[str, Any]:
    return self.post(  # type: ignore[return-value]
        "/api/v1/ordens-de-servico",
        json_body={"cliente_id": cliente_id, "veiculo_id": veiculo_id},
    )

def adicionar_item_ordem(
    self, ordem_id: str, body: Mapping[str, Any]
) -> dict[str, Any]:
    return self.post(f"/api/v1/ordens-de-servico/{ordem_id}/itens", json_body=body)  # type: ignore[return-value]

def remover_item_ordem(self, ordem_id: str, item_id: str) -> dict[str, Any]:
    return self.delete(f"/api/v1/ordens-de-servico/{ordem_id}/itens/{item_id}")  # type: ignore[return-value]

def executar_transicao(
    self,
    ordem_id: str,
    endpoint: str,
    body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa uma transicao de estado (ex endpoint='/diagnostico')."""
    return self.post(  # type: ignore[return-value]
        f"/api/v1/ordens-de-servico/{ordem_id}{endpoint}",
        json_body=body,
    )

def metricas_ordens(self) -> dict[str, Any]:
    return self.get("/api/v1/ordens-de-servico/metricas")  # type: ignore[return-value]
```

- [ ] **Step 2: Commit**

```bash
git add ui/cliente_api.py
git commit -m "feat(ui): add ordem_servico helpers to cliente_api"
```

### Task 4.4: Componente `StepperOs`

**Files:**
- Create: `ui/componentes/stepper_os.py`

- [ ] **Step 1: Implementar**

```python
"""Visualizacao horizontal do ciclo de vida da OS."""

from __future__ import annotations

from nicegui import ui

from src.ordem_servico.dominio.status import StatusOrdem

# Ordem visual do happy path.
_HAPPY_PATH: list[StatusOrdem] = [
    StatusOrdem.RECEBIDA,
    StatusOrdem.EM_DIAGNOSTICO,
    StatusOrdem.AGUARDANDO_APROVACAO,
    StatusOrdem.EM_EXECUCAO,
    StatusOrdem.FINALIZADA,
    StatusOrdem.ENTREGUE,
]

_ROTULOS: dict[StatusOrdem, str] = {
    StatusOrdem.RECEBIDA: "Recebida",
    StatusOrdem.EM_DIAGNOSTICO: "Em Diag.",
    StatusOrdem.AGUARDANDO_APROVACAO: "Ag. Aprov.",
    StatusOrdem.EM_EXECUCAO: "Em Execucao",
    StatusOrdem.FINALIZADA: "Finalizada",
    StatusOrdem.ENTREGUE: "Entregue",
    StatusOrdem.CANCELADA: "Cancelada",
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: "Ag. Aprov. Comp.",
}


class StepperOs:
    """Renderiza o stepper horizontal do ciclo de vida.

    status_atual: o estado corrente da OS.
    """

    def __init__(self, status_atual: StatusOrdem) -> None:
        with ui.row().classes("items-center gap-2 w-full"):
            for i, estado in enumerate(_HAPPY_PATH):
                self._render_etapa(estado, status_atual)
                if i < len(_HAPPY_PATH) - 1:
                    ui.label("→").classes("text-gray-400")

            if status_atual == StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR:
                ui.label("↕").classes("text-blue-500 mx-2")
                self._render_etapa(status_atual, status_atual)

            if status_atual == StatusOrdem.CANCELADA:
                ui.label("⇢").classes("text-red-500 mx-2")
                self._render_etapa(status_atual, status_atual)

    def _render_etapa(
        self, estado: StatusOrdem, status_atual: StatusOrdem
    ) -> None:
        rotulo = _ROTULOS.get(estado, estado.value)
        atual = estado == status_atual
        passado = _eh_passado(estado, status_atual)
        if estado == StatusOrdem.CANCELADA and status_atual == StatusOrdem.CANCELADA:
            classes = "bg-red-500 text-white"
        elif estado == StatusOrdem.ENTREGUE and status_atual == StatusOrdem.ENTREGUE:
            classes = "bg-green-600 text-white"
        elif atual:
            classes = "bg-blue-600 text-white font-bold"
        elif passado:
            classes = "bg-gray-300 text-gray-700"
        else:
            classes = "border border-gray-300 text-gray-400"
        ui.label(rotulo).classes(f"px-3 py-1 rounded {classes}")


def _eh_passado(estado: StatusOrdem, atual: StatusOrdem) -> bool:
    try:
        return _HAPPY_PATH.index(estado) < _HAPPY_PATH.index(atual)
    except ValueError:
        return False
```

- [ ] **Step 2: Commit**

```bash
git add ui/componentes/stepper_os.py
git commit -m "feat(ui): add StepperOs horizontal state visualization"
```

### Task 4.5: Componente `BotoesTransicao`

**Files:**
- Create: `ui/componentes/botoes_transicao.py`

- [ ] **Step 1: Implementar**

```python
"""Grid de botoes para transicoes validas do estado atual da OS."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from src.ordem_servico.dominio.status import StatusOrdem
from ui.componentes.maquina_estados import (
    BotaoTransicao,
    Transicao,
    obter_transicoes_validas,
)
from ui.estado import obter_store


class BotoesTransicao:
    """Renderiza botoes para transicoes validas do estado atual.

    on_executar: callback(transicao, body) -> None, chamado quando o
    usuario confirma a transicao.
    """

    def __init__(
        self,
        status_atual: StatusOrdem,
        on_executar: Callable[[Transicao, dict[str, str] | None], None],
    ) -> None:
        self._on_executar = on_executar
        papel = obter_store().papel_atual() or "sem-papel"
        botoes = obter_transicoes_validas(status_atual, papel)
        if not botoes:
            ui.label(
                "Estado final — nenhuma transicao disponivel."
            ).classes("text-gray-500 italic")
            return

        with ui.row().classes("gap-2 flex-wrap"):
            for botao in botoes:
                self._render_botao(botao)

    def _render_botao(self, botao: BotaoTransicao) -> None:
        t = botao.transicao
        btn = ui.button(
            botao.rotulo,
            on_click=lambda b=botao: self._clicar(b),
        )
        if not botao.habilitado:
            btn.props("disable")
            btn.classes("opacity-50")
            btn.tooltip(botao.motivo_bloqueio or "Nao permitido")
        elif t.perigoso:
            btn.classes("bg-red-600 text-white")
        else:
            btn.classes("bg-blue-600 text-white")

    def _clicar(self, botao: BotaoTransicao) -> None:
        if not botao.habilitado:
            return
        t = botao.transicao
        if t.pede_motivo:
            self._abrir_dialog_motivo(t)
        elif t.confirma:
            self._abrir_dialog_confirmacao(t)
        else:
            self._on_executar(t, None)

    def _abrir_dialog_motivo(self, transicao: Transicao) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"{transicao.rotulo}").classes("text-lg font-bold")
            ui.label("Informe o motivo (minimo 10 caracteres):")
            motivo = ui.textarea().classes("w-full")

            def submeter() -> None:
                if len(motivo.value.strip()) < 10:
                    ui.notify("Motivo deve ter ao menos 10 caracteres", type="warning")
                    return
                dialog.close()
                self._on_executar(transicao, {"motivo": motivo.value.strip()})

            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("Cancelar", on_click=dialog.close).props("flat")
                ui.button("Confirmar", on_click=submeter).classes(
                    "bg-red-600 text-white"
                )
        dialog.open()

    def _abrir_dialog_confirmacao(self, transicao: Transicao) -> None:
        from ui.componentes.dialogo_confirmacao import confirmar

        confirmar(
            titulo=transicao.rotulo,
            mensagem=f"Confirma a acao '{transicao.rotulo}'?",
            perigoso=transicao.perigoso,
            on_confirmar=lambda: self._on_executar(transicao, None),
        )
```

- [ ] **Step 2: Commit**

```bash
git add ui/componentes/botoes_transicao.py
git commit -m "feat(ui): add BotoesTransicao with role-aware enable/disable"
```

### Task 4.6: Pagina `/ordens-servico` lista + criar

**Files:**
- Create: `ui/paginas/ordens_servico.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Implementar pagina de lista**

```python
"""Paginas de listagem e detalhe de ordens de servico."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.picker_recurso import PickerRecurso

_CORES_STATUS: dict[str, str] = {
    "recebida": "bg-gray-400",
    "em_diagnostico": "bg-yellow-500",
    "aguardando_aprovacao": "bg-orange-500",
    "em_execucao": "bg-blue-500",
    "aguardando_aprovacao_complementar": "bg-orange-600",
    "finalizada": "bg-green-500",
    "entregue": "bg-green-700",
    "cancelada": "bg-red-600",
}


@ui.page("/ordens-servico")
@exige_autenticacao
def pagina_ordens() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Ordens de Servico").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar_lista()

        ui.button(
            "Nova OS",
            icon="add",
            on_click=lambda: _dialog_nova_ordem(refresh),
        ).classes("bg-blue-600 text-white")
        refresh()


def _renderizar_lista() -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().listar_ordens()
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for ordem in dados.get("items", []):
        status = ordem.get("status", "?")
        cor = _CORES_STATUS.get(status, "bg-gray-300")
        with ui.card().classes("w-full cursor-pointer").on(
            "click", lambda o=ordem: ui.navigate.to(f"/ordens-servico/{o['id']}")
        ):
            with ui.row().classes("items-center gap-4"):
                ui.label(str(ordem["id"])[:8]).classes("font-mono text-xs")
                ui.badge(status, color=None).classes(f"{cor} text-white")
                ui.label(ordem.get("cliente_nome", "")).classes("flex-1")
                ui.label(ordem.get("veiculo_placa", "")).classes("font-mono")


def _dialog_nova_ordem(on_sucesso) -> None:  # noqa: ANN001
    from ui.app import obter_api

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Nova OS").classes("text-lg font-bold")

        cliente_picker = PickerRecurso(
            rotulo="Cliente",
            fetcher=lambda: obter_api().listar_clientes(limit=100).get("items", []),
            campo_label="nome",
        )
        veiculo_picker_container = ui.column().classes("w-full")
        veiculo_picker_holder: dict[str, PickerRecurso] = {}

        def refresh_veiculos() -> None:
            veiculo_picker_container.clear()
            cid = cliente_picker.valor()
            if not cid:
                return
            with veiculo_picker_container:
                veiculo_picker_holder["v"] = PickerRecurso(
                    rotulo="Veiculo",
                    fetcher=lambda: obter_api().listar_veiculos(cid),
                    campo_label="placa",
                )

        cliente_picker._select.on_value_change(lambda e: refresh_veiculos())

        def salvar() -> None:
            cid = cliente_picker.valor()
            vp = veiculo_picker_holder.get("v")
            vid = vp.valor() if vp else None
            if not cid or not vid:
                ui.notify("Escolha cliente e veiculo", type="warning")
                return
            try:
                resposta = obter_api().criar_ordem(cid, vid)
                dialog.close()
                ui.notify("OS criada", type="positive")
                ui.navigate.to(f"/ordens-servico/{resposta['id']}")
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Criar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()
```

- [ ] **Step 2: Registrar em `ui/app.py`**

```python
import ui.paginas.ordens_servico  # noqa: F401
```

- [ ] **Step 3: Commit**

```bash
git add ui/paginas/ordens_servico.py ui/app.py
git commit -m "feat(ui): add ordens-servico list page and create dialog"
```

### Task 4.7: Pagina detalhe `/ordens-servico/{id}` + transicoes

**Files:**
- Modify: `ui/paginas/ordens_servico.py`

- [ ] **Step 1: Adicionar rota de detalhe**

No final de `ui/paginas/ordens_servico.py`:

```python
from src.ordem_servico.dominio.status import StatusOrdem
from ui.cliente_api import ValidacaoError
from ui.componentes.botoes_transicao import BotoesTransicao
from ui.componentes.maquina_estados import Transicao
from ui.componentes.stepper_os import StepperOs


@ui.page("/ordens-servico/{ordem_id}")
@exige_autenticacao
def pagina_detalhe_ordem(ordem_id: str) -> None:
    CabecalhoApp()

    container = ui.column().classes("p-8 gap-4 w-full")

    def render() -> None:
        container.clear()
        with container:
            _renderizar_detalhe(ordem_id, render)

    render()


def _renderizar_detalhe(ordem_id: str, on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        ordem = obter_api().obter_ordem(ordem_id)
    except ApiError as exc:
        ui.label(f"Erro ao carregar OS: {exc}").classes("text-red-600")
        return

    ui.label(f"OS {ordem['id']}").classes("text-2xl font-bold font-mono")
    status_str = ordem["status"]
    try:
        status_enum = StatusOrdem(status_str)
    except ValueError:
        ui.label(f"Status invalido: {status_str}").classes("text-red-600")
        return

    cor = _CORES_STATUS.get(status_str, "bg-gray-300")
    ui.badge(status_str, color=None).classes(f"{cor} text-white text-lg px-3 py-1")

    with ui.card().classes("w-full"):
        ui.label("Dados").classes("font-bold")
        ui.label(f"Cliente: {ordem.get('cliente_nome', '-')}")
        ui.label(f"Veiculo: {ordem.get('veiculo_placa', '-')}")
        ui.label(f"Criada em: {ordem.get('criado_em', '-')}")

    with ui.card().classes("w-full"):
        ui.label("Ciclo de vida").classes("font-bold")
        StepperOs(status_enum)

    with ui.card().classes("w-full"):
        ui.label("Acoes").classes("font-bold")

        def executar(transicao: Transicao, body: dict[str, str] | None) -> None:
            try:
                obter_api().executar_transicao(ordem_id, transicao.endpoint, body)
                ui.notify(f"Transicao {transicao.rotulo} executada", type="positive")
                on_refresh()
            except ValidacaoError as exc:
                msgs = "; ".join(str(d.get("msg", "")) for d in exc.detalhes)
                ui.notify(f"Invalido: {msgs}", type="negative")
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        BotoesTransicao(status_enum, on_executar=executar)

    _renderizar_itens(ordem_id, ordem, on_refresh)

    orcamento = ordem.get("orcamento")
    if orcamento:
        with ui.card().classes("w-full"):
            ui.label("Orcamento").classes("font-bold")
            ui.label(f"Total: R$ {float(orcamento.get('total', 0)):.2f}")


def _renderizar_itens(ordem_id: str, ordem: dict[str, Any], on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center w-full"):
            ui.label("Itens").classes("font-bold flex-1")
            ui.button(
                "Adicionar item",
                icon="add",
                on_click=lambda: _dialog_adicionar_item(ordem_id, on_refresh),
            ).props("flat dense")
        itens = ordem.get("itens", [])
        if not itens:
            ui.label("Nenhum item ainda.").classes("text-gray-500 italic")
            return
        for item in itens:
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label(item.get("descricao", "")).classes("flex-1")
                ui.label(f"Qty: {item.get('quantidade', 1)}")
                ui.button(
                    icon="delete",
                    on_click=lambda i=item: _remover_item(
                        ordem_id, i["id"], on_refresh
                    ),
                ).props("flat dense")


def _remover_item(ordem_id: str, item_id: str, on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    try:
        obter_api().remover_item_ordem(ordem_id, item_id)
        ui.notify("Item removido", type="positive")
        on_refresh()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _dialog_adicionar_item(ordem_id: str, on_refresh) -> None:  # noqa: ANN001
    from ui.app import obter_api

    with ui.dialog() as dialog, ui.card().classes("w-[32rem]"):
        ui.label("Adicionar item").classes("text-lg font-bold")
        ui.label("Escolha um servico do catalogo OU um item de estoque.").classes(
            "text-sm text-gray-500"
        )

        servico_picker = PickerRecurso(
            rotulo="Servico",
            fetcher=lambda: obter_api().listar_servicos(limit=100).get("items", []),
            campo_label="nome",
        )
        item_picker = PickerRecurso(
            rotulo="Item estoque",
            fetcher=lambda: obter_api().listar_estoque(limit=100).get("items", []),
            campo_label="nome",
        )
        descricao = ui.input("Descricao (opcional)").classes("w-full")
        quantidade = ui.number("Quantidade", value=1, min=1, step=1).classes("w-full")

        def salvar() -> None:
            body: dict[str, Any] = {
                "descricao": descricao.value or None,
                "quantidade": int(quantidade.value),
            }
            if servico_picker.valor():
                body["servico_catalogo_id"] = servico_picker.valor()
            if item_picker.valor():
                body["item_estoque_id"] = item_picker.valor()
            try:
                obter_api().adicionar_item_ordem(ordem_id, body)
                dialog.close()
                ui.notify("Item adicionado", type="positive")
                on_refresh()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()
```

- [ ] **Step 2: Rodar testes e smoke test**

```bash
uv run pytest tests/unitarios/ -v --no-lint -m "not lento"
uv run python -m ui &
PID=$!
sleep 3
curl -sf http://localhost:8080/ordens-servico > /dev/null && echo OK
kill $PID
```

- [ ] **Step 3: Commit**

```bash
git add ui/paginas/ordens_servico.py
git commit -m "feat(ui): add OS detail page with stepper, transitions, and items"
```

---

## Phase 5 — Polimento: seed, painel HTTP, LGPD, acompanhamento, dashboard, cobertura (PR 5)

Objetivo: fechar o escopo completo da UI com seed de dados, painel HTTP, LGPD em clientes, pagina de acompanhamento publico e cards de metricas no dashboard.

### Task 5.1: `ui/seed.py` — gerador de dados

**Files:**
- Create: `ui/seed.py`
- Create: `tests/unitarios/ui/test_seed.py`

- [ ] **Step 1: Escrever teste**

```python
# tests/unitarios/ui/test_seed.py
from __future__ import annotations

from unittest.mock import MagicMock

from ui.seed import RelatorioSeed, gerar_dados_teste


def test_gerar_dados_cria_conjunto_completo() -> None:
    api = MagicMock()
    api.listar_clientes.return_value = {"items": []}
    api.listar_servicos.return_value = {"items": []}
    api.listar_estoque.return_value = {"items": []}
    api.criar_cliente.return_value = {"id": "c"}
    api.adicionar_veiculo.return_value = {"id": "v"}
    api.criar_servico.return_value = {"id": "s"}
    api.criar_item_estoque.return_value = {"id": "e"}
    api.criar_ordem.return_value = {"id": "o"}
    api.adicionar_item_ordem.return_value = {}
    api.executar_transicao.return_value = {}

    progresso: list[tuple[int, str]] = []
    rel = gerar_dados_teste(
        api,
        on_progresso=lambda pct, msg: progresso.append((pct, msg)),
    )

    assert isinstance(rel, RelatorioSeed)
    assert rel.clientes_criados == 3
    assert rel.veiculos_criados == 5
    assert rel.servicos_criados == 5
    assert rel.itens_criados == 10
    assert rel.ordens_criadas == 4
    assert len(progresso) > 0


def test_gerar_dados_skipa_duplicatas() -> None:
    api = MagicMock()
    api.listar_clientes.return_value = {
        "items": [
            {"id": "c1", "documento": "11144477735"},
            {"id": "c2", "documento": "98765432100"},
            {"id": "c3", "documento": "12345678000190"},
        ]
    }
    api.listar_servicos.return_value = {
        "items": [
            {"id": "s1", "nome": "Troca de oleo"},
            {"id": "s2", "nome": "Alinhamento"},
            {"id": "s3", "nome": "Troca de pastilha"},
            {"id": "s4", "nome": "Diagnostico eletronico"},
            {"id": "s5", "nome": "Revisao completa"},
        ]
    }
    api.listar_estoque.return_value = {
        "items": [
            {"id": f"e{i}", "nome": n}
            for i, n in enumerate(
                [
                    "Filtro de oleo",
                    "Pastilha de freio dianteiro",
                    "Oleo 5W30",
                    "Filtro de ar",
                    "Vela de ignicao",
                    "Correia dentada",
                    "Amortecedor",
                    "Lampada farol H7",
                    "Junta de motor",
                    "Fluido de freio",
                ]
            )
        ]
    }
    api.listar_veiculos.return_value = []
    api.adicionar_veiculo.return_value = {"id": "v"}
    api.criar_ordem.return_value = {"id": "o"}
    api.adicionar_item_ordem.return_value = {}
    api.executar_transicao.return_value = {}

    rel = gerar_dados_teste(api, on_progresso=lambda *a: None)

    assert rel.clientes_existentes == 3
    assert rel.servicos_existentes == 5
    assert rel.itens_existentes == 10
    api.criar_cliente.assert_not_called()
    api.criar_servico.assert_not_called()
    api.criar_item_estoque.assert_not_called()
```

- [ ] **Step 2: Rodar (falha)**

- [ ] **Step 3: Implementar `ui/seed.py`**

```python
"""Gerador de dados de teste via API do backend.

Cria 3 clientes (2 PF + 1 PJ), 5 veiculos, 5 servicos, 10 itens de estoque
e 4 OS em estados variados. Idempotente por chave natural (documento, nome).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ui.cliente_api import ApiError, ClienteApi


@dataclass
class RelatorioSeed:
    clientes_criados: int = 0
    clientes_existentes: int = 0
    veiculos_criados: int = 0
    servicos_criados: int = 0
    servicos_existentes: int = 0
    itens_criados: int = 0
    itens_existentes: int = 0
    ordens_criadas: int = 0
    avisos: list[str] = field(default_factory=list)


_CLIENTES: list[dict[str, Any]] = [
    {
        "nome": "Joao Silva",
        "documento": "11144477735",
        "tipo_documento": "cpf",
        "contato": "joao@example.com",
    },
    {
        "nome": "Maria Santos",
        "documento": "98765432100",
        "tipo_documento": "cpf",
        "contato": "maria@example.com",
    },
    {
        "nome": "Oficina Boa Vida LTDA",
        "documento": "12345678000190",
        "tipo_documento": "cnpj",
        "contato": "contato@boavida.com",
    },
]

_VEICULOS: list[tuple[int, dict[str, Any]]] = [
    (0, {"placa": "ABC1D23", "marca": "Volkswagen", "modelo": "Gol", "ano": 2015}),
    (0, {"placa": "DEF2E34", "marca": "Honda", "modelo": "Civic", "ano": 2020}),
    (1, {"placa": "GHI3F45", "marca": "Toyota", "modelo": "Corolla", "ano": 2018}),
    (2, {"placa": "JKL4G56", "marca": "Fiat", "modelo": "Strada", "ano": 2019}),
    (2, {"placa": "MNO5H67", "marca": "Hyundai", "modelo": "HR", "ano": 2022}),
]

_SERVICOS: list[dict[str, Any]] = [
    {"nome": "Troca de oleo", "descricao": "Troca de oleo e filtro", "preco": 150.0},
    {"nome": "Alinhamento", "descricao": "Alinhamento 4 rodas", "preco": 120.0},
    {"nome": "Troca de pastilha", "descricao": "Pastilha dianteira", "preco": 280.0},
    {"nome": "Diagnostico eletronico", "descricao": "Scanner OBD-II", "preco": 200.0},
    {"nome": "Revisao completa", "descricao": "Revisao 10k km", "preco": 600.0},
]

_ITENS: list[dict[str, Any]] = [
    {"nome": "Filtro de oleo", "descricao": "Universal", "quantidade": 20, "preco_unitario": 35.0},
    {"nome": "Pastilha de freio dianteiro", "descricao": "", "quantidade": 15, "preco_unitario": 180.0},
    {"nome": "Oleo 5W30", "descricao": "Litro", "quantidade": 50, "preco_unitario": 45.0},
    {"nome": "Filtro de ar", "descricao": "", "quantidade": 12, "preco_unitario": 28.0},
    {"nome": "Vela de ignicao", "descricao": "", "quantidade": 30, "preco_unitario": 18.0},
    {"nome": "Correia dentada", "descricao": "", "quantidade": 5, "preco_unitario": 220.0},
    {"nome": "Amortecedor", "descricao": "Par", "quantidade": 8, "preco_unitario": 350.0},
    {"nome": "Lampada farol H7", "descricao": "", "quantidade": 25, "preco_unitario": 22.0},
    # Item com qty baixa pra testar destaque amarelo:
    {"nome": "Junta de motor", "descricao": "", "quantidade": 3, "preco_unitario": 140.0},
    {"nome": "Fluido de freio", "descricao": "500ml", "quantidade": 18, "preco_unitario": 32.0},
]


def gerar_dados_teste(
    api: ClienteApi,
    *,
    on_progresso: Callable[[int, str], None],
) -> RelatorioSeed:
    """Gera dados via API. Admin required. Idempotente por chave natural."""
    rel = RelatorioSeed()

    # 1. Clientes
    on_progresso(0, "Carregando clientes existentes...")
    existentes_clientes = {
        c["documento"]: c for c in api.listar_clientes(limit=100).get("items", [])
    }
    ids_clientes: list[str] = []
    for i, cliente in enumerate(_CLIENTES):
        on_progresso(5 + i * 3, f"Cliente {cliente['nome']}")
        if cliente["documento"] in existentes_clientes:
            ids_clientes.append(existentes_clientes[cliente["documento"]]["id"])
            rel.clientes_existentes += 1
            continue
        try:
            resp = api.criar_cliente(cliente)
            ids_clientes.append(resp["id"])
            rel.clientes_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Cliente {cliente['nome']}: {exc}")

    # 2. Veiculos (so se o cliente foi criado agora; existentes mantem veiculos atuais)
    on_progresso(15, "Adicionando veiculos...")
    for idx_cliente, veiculo in _VEICULOS:
        if idx_cliente >= len(ids_clientes):
            continue
        cid = ids_clientes[idx_cliente]
        try:
            veiculos_existentes = api.listar_veiculos(cid)
            if any(v.get("placa") == veiculo["placa"] for v in veiculos_existentes):
                continue
            api.adicionar_veiculo(cid, veiculo)
            rel.veiculos_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Veiculo {veiculo['placa']}: {exc}")

    # 3. Servicos
    on_progresso(30, "Catalogo de servicos...")
    existentes_servicos = {
        s["nome"]: s for s in api.listar_servicos(limit=100).get("items", [])
    }
    ids_servicos: list[str] = []
    for i, servico in enumerate(_SERVICOS):
        on_progresso(35 + i * 2, f"Servico {servico['nome']}")
        if servico["nome"] in existentes_servicos:
            ids_servicos.append(existentes_servicos[servico["nome"]]["id"])
            rel.servicos_existentes += 1
            continue
        try:
            resp = api.criar_servico(servico)
            ids_servicos.append(resp["id"])
            rel.servicos_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Servico {servico['nome']}: {exc}")

    # 4. Itens de estoque
    on_progresso(50, "Itens de estoque...")
    existentes_itens = {
        i["nome"]: i for i in api.listar_estoque(limit=100).get("items", [])
    }
    ids_itens: list[str] = []
    for i, item in enumerate(_ITENS):
        on_progresso(55 + i, f"Item {item['nome']}")
        if item["nome"] in existentes_itens:
            ids_itens.append(existentes_itens[item["nome"]]["id"])
            rel.itens_existentes += 1
            continue
        try:
            resp = api.criar_item_estoque(item)
            ids_itens.append(resp["id"])
            rel.itens_criados += 1
        except ApiError as exc:
            rel.avisos.append(f"Item {item['nome']}: {exc}")

    # 5. Ordens em estados variados
    on_progresso(70, "Criando OS em estados variados...")
    if ids_clientes and ids_servicos:
        rel.ordens_criadas += _criar_os_recebida(api, ids_clientes[0], rel)
        on_progresso(75, "OS #2 — EM_DIAGNOSTICO")
        rel.ordens_criadas += _criar_os_em_diagnostico(
            api, ids_clientes[1 % len(ids_clientes)], ids_servicos[0], rel
        )
        on_progresso(85, "OS #3 — AGUARDANDO_APROVACAO")
        rel.ordens_criadas += _criar_os_aguardando_aprovacao(
            api, ids_clientes[2 % len(ids_clientes)], ids_servicos[0], ids_servicos[1], rel
        )
        on_progresso(95, "OS #4 — EM_EXECUCAO")
        rel.ordens_criadas += _criar_os_em_execucao(
            api, ids_clientes[0], ids_servicos, ids_itens, rel
        )

    on_progresso(100, "Concluido")
    return rel


def _veiculo_id_do_cliente(api: ClienteApi, cliente_id: str) -> str | None:
    veiculos = api.listar_veiculos(cliente_id)
    return veiculos[0]["id"] if veiculos else None


def _criar_os_recebida(
    api: ClienteApi, cliente_id: str, rel: RelatorioSeed
) -> int:
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        rel.avisos.append("OS #1: cliente sem veiculo")
        return 0
    try:
        api.criar_ordem(cliente_id, vid)
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #1: {exc}")
        return 0


def _criar_os_em_diagnostico(
    api: ClienteApi, cliente_id: str, servico_id: str, rel: RelatorioSeed
) -> int:
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        os = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            os["id"],
            {"servico_catalogo_id": servico_id, "quantidade": 1},
        )
        api.executar_transicao(os["id"], "/diagnostico")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #2: {exc}")
        return 0


def _criar_os_aguardando_aprovacao(
    api: ClienteApi,
    cliente_id: str,
    servico1_id: str,
    servico2_id: str,
    rel: RelatorioSeed,
) -> int:
    vid = _veiculo_id_do_cliente(api, cliente_id)
    if not vid:
        return 0
    try:
        os = api.criar_ordem(cliente_id, vid)
        api.adicionar_item_ordem(
            os["id"], {"servico_catalogo_id": servico1_id, "quantidade": 1}
        )
        api.adicionar_item_ordem(
            os["id"], {"servico_catalogo_id": servico2_id, "quantidade": 1}
        )
        api.executar_transicao(os["id"], "/diagnostico")
        api.executar_transicao(os["id"], "/orcamento")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #3: {exc}")
        return 0


def _criar_os_em_execucao(
    api: ClienteApi,
    cliente_id: str,
    servicos: list[str],
    itens: list[str],
    rel: RelatorioSeed,
) -> int:
    veiculos = api.listar_veiculos(cliente_id)
    if len(veiculos) < 2:
        return 0
    vid = veiculos[1]["id"]
    try:
        os = api.criar_ordem(cliente_id, vid)
        for sid in servicos[:2]:
            api.adicionar_item_ordem(
                os["id"], {"servico_catalogo_id": sid, "quantidade": 1}
            )
        if itens:
            api.adicionar_item_ordem(
                os["id"], {"item_estoque_id": itens[0], "quantidade": 1}
            )
        api.executar_transicao(os["id"], "/diagnostico")
        api.executar_transicao(os["id"], "/orcamento")
        api.executar_transicao(os["id"], "/aprovacao")
        return 1
    except ApiError as exc:
        rel.avisos.append(f"OS #4: {exc}")
        return 0
```

- [ ] **Step 4: Rodar testes**

- [ ] **Step 5: Commit**

```bash
git add ui/seed.py tests/unitarios/ui/test_seed.py
git commit -m "feat(ui): add seed.py with idempotent test data generator"
```

### Task 5.2: Dashboard com botao de seed e metricas

**Files:**
- Create: `ui/paginas/dashboard.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Implementar dashboard real**

```python
"""Dashboard — pagina root apos login."""

from __future__ import annotations

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import AcessoNegadoError, ApiError
from ui.componentes.cabecalho import CabecalhoApp
from ui.estado import obter_store


@ui.page("/")
@exige_autenticacao
def pagina_dashboard() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Dashboard").classes("text-2xl font-bold")

        _renderizar_metricas()

        with ui.row().classes("gap-4"):
            papel = obter_store().papel_atual()
            botao_seed = ui.button(
                "🎲 Gerar dados de teste",
                on_click=_dialog_seed,
            ).classes("bg-purple-600 text-white")
            if papel != "admin":
                botao_seed.props("disable")
                botao_seed.tooltip("Seed requer papel admin")
            ui.button(
                "Nova OS",
                icon="add",
                on_click=lambda: ui.navigate.to("/ordens-servico"),
            ).classes("bg-blue-600 text-white")


def _renderizar_metricas() -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().metricas_ordens()
    except AcessoNegadoError:
        ui.label("Metricas disponiveis apenas para admin.").classes("text-gray-500")
        return
    except ApiError as exc:
        ui.label(f"Erro ao carregar metricas: {exc}").classes("text-red-600")
        return

    with ui.row().classes("gap-4 w-full flex-wrap"):
        _card_metrica("Total de OS", str(dados.get("total", 0)), "bg-blue-500")
        _card_metrica(
            "Tempo medio (min)",
            str(dados.get("tempo_medio_execucao_minutos", 0)),
            "bg-green-500",
        )
        por_status = dados.get("por_status", {})
        for status, qtd in por_status.items():
            _card_metrica(status, str(qtd), "bg-gray-500")


def _card_metrica(titulo: str, valor: str, cor: str) -> None:
    with ui.card().classes(f"{cor} text-white min-w-40"):
        ui.label(titulo).classes("text-sm")
        ui.label(valor).classes("text-3xl font-bold")


def _dialog_seed() -> None:
    from ui.app import obter_api
    from ui.seed import gerar_dados_teste

    with ui.dialog() as dialog, ui.card().classes("w-[36rem]"):
        ui.label("Gerando dados de teste").classes("text-lg font-bold")
        progress = ui.linear_progress(value=0).classes("w-full")
        status_label = ui.label("Iniciando...").classes("text-sm")
        relatorio_container = ui.column().classes("w-full")
        fechar_btn = ui.button("Fechar", on_click=dialog.close).props("flat")
        fechar_btn.set_visibility(False)

        def atualizar_progresso(pct: int, msg: str) -> None:
            progress.value = pct / 100
            status_label.set_text(msg)

        try:
            rel = gerar_dados_teste(obter_api(), on_progresso=atualizar_progresso)
            with relatorio_container:
                ui.label(f"✓ {rel.clientes_criados} clientes criados ({rel.clientes_existentes} existiam)")
                ui.label(f"✓ {rel.veiculos_criados} veiculos adicionados")
                ui.label(f"✓ {rel.servicos_criados} servicos criados ({rel.servicos_existentes} existiam)")
                ui.label(f"✓ {rel.itens_criados} itens de estoque criados ({rel.itens_existentes} existiam)")
                ui.label(f"✓ {rel.ordens_criadas} OS criadas")
                for aviso in rel.avisos:
                    ui.label(f"⚠ {aviso}").classes("text-orange-600")
        except ApiError as exc:
            with relatorio_container:
                ui.label(f"Erro fatal: {exc}").classes("text-red-600")
        fechar_btn.set_visibility(True)
    dialog.open()
```

- [ ] **Step 2: Substituir `pagina_root` em `ui/app.py`**

Remover a `pagina_root` placeholder e importar o dashboard:

```python
# Em ui/app.py, remover:
#   @ui.page("/")
#   @exige_autenticacao
#   def pagina_root() -> None: ...
#
# Adicionar import:
import ui.paginas.dashboard  # noqa: F401
```

- [ ] **Step 3: Commit**

```bash
git add ui/paginas/dashboard.py ui/app.py
git commit -m "feat(ui): add dashboard with metrics cards and seed button"
```

### Task 5.3: Painel HTTP (drawer req/res)

**Files:**
- Create: `ui/componentes/painel_http.py`
- Modify: `ui/componentes/cabecalho.py`

- [ ] **Step 1: Implementar drawer**

```python
"""Drawer com historico de request/response do ClienteApi."""

from __future__ import annotations

from typing import Literal

from nicegui import ui

from ui.estado import RegistroHttp, obter_store

FiltroStatus = Literal["tudo", "2xx", "4xx", "5xx"]


class PainelHttp:
    """Drawer lateral direito que lista os RegistroHttp."""

    def __init__(self) -> None:
        self._filtro: FiltroStatus = "tudo"
        self._busca: str = ""
        self._drawer = ui.right_drawer(value=False, bordered=True).classes(
            "bg-gray-900 text-white p-4 w-96"
        )
        with self._drawer:
            with ui.row().classes("items-center w-full"):
                ui.label("Painel HTTP").classes("text-lg font-bold")
                ui.space()
                ui.button(
                    icon="delete",
                    on_click=self._limpar,
                ).props("flat dense").tooltip("Limpar historico")

            self._busca_input = ui.input(
                placeholder="Buscar por caminho",
                on_change=lambda e: self._atualizar_busca(e.value),
            ).classes("w-full")
            ui.select(
                ["tudo", "2xx", "4xx", "5xx"],
                value="tudo",
                on_change=lambda e: self._atualizar_filtro(e.value),
            ).classes("w-full")
            self._lista = ui.column().classes("w-full gap-2")
        self.renderizar()
        ui.timer(1.0, self.renderizar)  # refresh periodico

    def toggle(self) -> None:
        self._drawer.toggle()

    def renderizar(self) -> None:
        self._lista.clear()
        with self._lista:
            for registro in obter_store().historico_http():
                if not self._passa_filtro(registro):
                    continue
                self._render_entrada(registro)

    def _passa_filtro(self, r: RegistroHttp) -> bool:
        if self._busca and self._busca not in r.caminho:
            return False
        if self._filtro == "tudo":
            return True
        status = r.status
        if self._filtro == "2xx":
            return 200 <= status < 300
        if self._filtro == "4xx":
            return 400 <= status < 500
        if self._filtro == "5xx":
            return 500 <= status < 600 or status == 0
        return True

    def _render_entrada(self, r: RegistroHttp) -> None:
        cor = _cor_status(r.status)
        with ui.expansion(
            f"[{r.metodo}] {r.caminho}  ({r.status} · {r.duracao_ms}ms · {r.papel_no_momento})"
        ).classes(f"w-full {cor}"):
            if r.request_body:
                ui.label("Request").classes("font-bold text-sm")
                ui.code(r.request_body, language="json").classes("text-xs")
            ui.label("Response").classes("font-bold text-sm")
            ui.code(r.response_body, language="json").classes("text-xs")

    def _atualizar_filtro(self, valor: str) -> None:
        if valor in ("tudo", "2xx", "4xx", "5xx"):
            self._filtro = valor  # type: ignore[assignment]
            self.renderizar()

    def _atualizar_busca(self, valor: str) -> None:
        self._busca = valor or ""
        self.renderizar()

    def _limpar(self) -> None:
        obter_store().limpar_historico_http()
        self.renderizar()


def _cor_status(status: int) -> str:
    if status == 0:
        return "bg-red-900"
    if 200 <= status < 300:
        return "bg-green-900"
    if 400 <= status < 500:
        return "bg-orange-900"
    if 500 <= status < 600:
        return "bg-red-900"
    return "bg-gray-700"
```

- [ ] **Step 2: Adicionar botao no cabecalho pra abrir o drawer**

Em `ui/componentes/cabecalho.py`, antes de `ui.space()` na row:

```python
ui.button(
    icon="history",
    on_click=self._toggle_painel_http,
).props("flat dense").tooltip("Painel HTTP").classes("text-white")
```

E adicionar metodo:

```python
def _toggle_painel_http(self) -> None:
    from ui.componentes.painel_http import PainelHttp

    # NiceGUI drawer e persistente — toggle via app.storage.client guarda instancia
    from nicegui import app

    painel = app.storage.client.get("painel_http")
    if painel is None:
        painel = PainelHttp()
        app.storage.client["painel_http"] = painel
    painel.toggle()
```

- [ ] **Step 3: Commit**

```bash
git add ui/componentes/painel_http.py ui/componentes/cabecalho.py
git commit -m "feat(ui): add HTTP request/response drawer panel"
```

### Task 5.4: LGPD em pagina de clientes

**Files:**
- Modify: `ui/cliente_api.py`
- Modify: `ui/paginas/clientes.py`

- [ ] **Step 1: Adicionar helpers LGPD em `ClienteApi`**

```python
# LGPD

def exportar_dados_cliente(self, cliente_id: str) -> dict[str, Any]:
    return self.get(f"/api/v1/clientes/{cliente_id}/dados-pessoais/exportar")  # type: ignore[return-value]

def excluir_dados_cliente(self, cliente_id: str) -> None:
    self.delete(f"/api/v1/clientes/{cliente_id}/dados-pessoais")

def registrar_consentimento(self, cliente_id: str, tipo: str) -> dict[str, Any]:
    return self.post(  # type: ignore[return-value]
        f"/api/v1/clientes/{cliente_id}/consentimento",
        json_body={"tipo": tipo},
    )

def revogar_consentimento(self, cliente_id: str, tipo: str) -> None:
    self.delete(
        f"/api/v1/clientes/{cliente_id}/consentimento",
        params={"tipo": tipo},
    )
```

- [ ] **Step 2: Adicionar menu LGPD em cada card de cliente em `clientes.py`**

Dentro de `_renderizar_tabela`, apos os botoes edit/delete, adicionar:

```python
with ui.button(icon="more_vert").props("flat dense"):
    with ui.menu() as menu:
        ui.menu_item(
            "Registrar consentimento",
            on_click=lambda c=cliente: _dialog_consentimento(c, registrar=True),
        )
        ui.menu_item(
            "Revogar consentimento",
            on_click=lambda c=cliente: _dialog_consentimento(c, registrar=False),
        )
        ui.menu_item(
            "Exportar dados pessoais",
            on_click=lambda c=cliente: _exportar_dados(c),
        )
        ui.menu_item(
            "Excluir dados pessoais",
            on_click=lambda c=cliente: confirmar(
                titulo="Excluir dados pessoais",
                mensagem=f"ATENCAO: remove dados de {c['nome']} (LGPD).",
                perigoso=True,
                on_confirmar=lambda cid=c["id"]: _excluir_dados(cid),
            ),
        )
```

E adicionar as funcoes auxiliares:

```python
def _dialog_consentimento(cliente: dict[str, Any], *, registrar: bool) -> None:
    from ui.app import obter_api

    acao = "Registrar" if registrar else "Revogar"
    with ui.dialog() as dialog, ui.card().classes("w-80"):
        ui.label(f"{acao} consentimento").classes("text-lg font-bold")
        tipo = ui.select(
            ["marketing", "comunicacao", "compartilhamento"],
            label="Tipo",
            value="marketing",
        ).classes("w-full")

        def salvar() -> None:
            try:
                if registrar:
                    obter_api().registrar_consentimento(cliente["id"], tipo.value)
                else:
                    obter_api().revogar_consentimento(cliente["id"], tipo.value)
                dialog.close()
                ui.notify(f"{acao} com sucesso", type="positive")
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Confirmar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _exportar_dados(cliente: dict[str, Any]) -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().exportar_dados_cliente(cliente["id"])
        with ui.dialog() as dialog, ui.card().classes("w-[36rem]"):
            ui.label(f"Dados pessoais de {cliente['nome']}").classes(
                "text-lg font-bold"
            )
            import json

            ui.code(
                json.dumps(dados, indent=2, ensure_ascii=False), language="json"
            ).classes("text-xs")
            ui.button("Fechar", on_click=dialog.close)
        dialog.open()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _excluir_dados(cliente_id: str) -> None:
    from ui.app import obter_api

    try:
        obter_api().excluir_dados_cliente(cliente_id)
        ui.notify("Dados excluidos", type="positive")
        _refresh_global()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
```

- [ ] **Step 3: Commit**

```bash
git add ui/cliente_api.py ui/paginas/clientes.py
git commit -m "feat(ui): add LGPD actions to cliente page (consent, export, delete)"
```

### Task 5.5: Pagina de acompanhamento publico

**Files:**
- Modify: `ui/cliente_api.py`
- Create: `ui/paginas/acompanhamento.py`
- Modify: `ui/app.py`

- [ ] **Step 1: Adicionar helper publico**

```python
# acompanhamento publico (sem auth)

def acompanhamento_publico(self, *, placa: str, documento: str) -> dict[str, Any]:
    return self.get(  # type: ignore[return-value]
        "/api/v1/acompanhamento",
        params={"placa": placa, "documento": documento},
    )
```

- [ ] **Step 2: Implementar pagina**

```python
# ui/paginas/acompanhamento.py
"""Pagina publica de acompanhamento de OS (simula visao do cliente final)."""

from __future__ import annotations

from nicegui import ui

from ui.cliente_api import (
    ApiError,
    BackendInacessivelError,
    RateLimitExcedidoError,
    ValidacaoError,
)


@ui.page("/acompanhamento")
def pagina_acompanhamento() -> None:
    """Pagina sem auth (simula endpoint publico do backend)."""
    with ui.column().classes("absolute-center items-center gap-4 w-[32rem]"):
        ui.label("Acompanhamento de OS").classes("text-3xl font-bold")
        ui.label("Consulte o andamento do seu servico").classes("text-gray-500")

        placa = ui.input(
            "Placa", placeholder="ABC1D23"
        ).classes("w-full")
        documento = ui.input(
            "CPF ou CNPJ", placeholder="apenas numeros"
        ).classes("w-full")

        resultado = ui.column().classes("w-full")

        def consultar() -> None:
            from ui.app import obter_api

            resultado.clear()
            try:
                dados = obter_api().acompanhamento_publico(
                    placa=placa.value, documento=documento.value
                )
                with resultado:
                    with ui.card().classes("w-full bg-green-50"):
                        ui.label(f"Status: {dados.get('status', '?')}").classes(
                            "text-lg font-bold"
                        )
                        ui.label(
                            f"Atualizado em: {dados.get('atualizado_em', '-')}"
                        )
                        ui.label(f"Ordem: {dados.get('id', '?')}")
            except ValidacaoError:
                with resultado:
                    ui.label("Placa ou documento em formato invalido.").classes(
                        "text-red-600"
                    )
            except RateLimitExcedidoError as exc:
                with resultado:
                    ui.label(
                        f"Muitas consultas. Aguarde {exc.retry_after}s."
                    ).classes("text-orange-600")
            except BackendInacessivelError as exc:
                with resultado:
                    ui.label(f"Backend inacessivel: {exc}").classes("text-red-600")
            except ApiError as exc:
                with resultado:
                    ui.label(f"Nenhuma OS encontrada ({exc}).").classes(
                        "text-gray-600"
                    )

        ui.button("Consultar", on_click=consultar).classes(
            "bg-blue-600 text-white w-full"
        )
```

- [ ] **Step 3: Registrar em `ui/app.py`**

```python
import ui.paginas.acompanhamento  # noqa: F401
```

- [ ] **Step 4: Commit**

```bash
git add ui/cliente_api.py ui/paginas/acompanhamento.py ui/app.py
git commit -m "feat(ui): add public acompanhamento page without auth"
```

### Task 5.6: Detectar usuarios seed ausentes na pagina de login

**Files:**
- Modify: `ui/paginas/login.py`

- [ ] **Step 1: Adicionar detecao**

Em `ui/paginas/login.py`, apos `_checar_backend`, adicionar:

```python
def _checar_usuarios_seed(alerta: ui.column) -> None:
    from ui.app import obter_api
    from ui.cliente_api import NaoAutenticadoError

    api = obter_api()
    usuario_admin = CONFIG.usuarios_seed["admin"]
    try:
        api._client.post(
            "/api/v1/autenticacao/login",
            json={"email": usuario_admin.email, "senha": usuario_admin.senha},
        )
        # Se o login teria dado certo, assumimos que o seed rodou.
    except Exception:  # noqa: BLE001
        return

    # Checa de verdade: pede login e ve se retorna 200.
    try:
        resposta = api._client.post(
            "/api/v1/autenticacao/login",
            json={"email": usuario_admin.email, "senha": usuario_admin.senha},
        )
    except Exception:  # noqa: BLE001
        return
    if resposta.status_code == 401:
        alerta.clear()
        with alerta:
            ui.label(
                "Usuarios seed nao encontrados no banco. "
                "Rode 'make seed-users' (ou 'make seed-users-docker') "
                "antes de continuar."
            ).classes("text-orange-600 text-sm")
```

E chamar no `pagina_login` antes do botao `Entrar`:

```python
alerta_seed = ui.column().classes("w-full")
_checar_usuarios_seed(alerta_seed)
```

- [ ] **Step 2: Commit**

```bash
git add ui/paginas/login.py
git commit -m "feat(ui): detect missing seed users and show inline instructions"
```

### Task 5.7: `.coveragerc` com thresholds separados

**Files:**
- Create: `.coveragerc`

- [ ] **Step 1: Criar arquivo**

```ini
# .coveragerc
# Thresholds por path. `src/` mantem 95% (meta oficial do backend);
# `ui/` fica em 60% por ser ferramenta de dev.

[run]
source = src, ui
omit =
    tests/*
    */migrations/*
    */__init__.py

[paths]
src = src/
ui = ui/

[report]
# Meta global: 95% no backend. UI tem meta separada via workflow CI.
fail_under = 95
show_missing = True
```

**Nota sobre thresholds por path**: coverage.py nao suporta `fail_under` por path nativamente. Na pratica, rodamos dois comandos distintos de `pytest --cov`:
- `pytest tests/unitarios/ --cov=src --cov-fail-under=95` (backend)
- `pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=60` (UI)

Documentar isso em `ui/README.md`.

- [ ] **Step 2: Atualizar CI para rodar coverage de UI separadamente**

No job `test` de `.github/workflows/ci.yml`, adicionar apos o pytest normal:

```yaml
      - name: Run UI unit tests with separate coverage gate
        run: |
          uv run pytest tests/unitarios/ui/ \
            --no-lint \
            --cov=ui \
            --cov-report=term-missing \
            --cov-fail-under=60 \
            -m "not lento" \
            -x \
            --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add .coveragerc .github/workflows/ci.yml
git commit -m "ci(ui): add separate 60% coverage gate for ui package"
```

### Task 5.8: Smoke test end-to-end + entrega

**Files:**
- (nenhum novo)

- [ ] **Step 1: Rodar pipeline local completo**

```bash
uv sync --extra test --extra ui --frozen
uv run ruff check src/ ui/ tests/
uv run ruff format --check src/ ui/ tests/
uv run mypy src/ ui/
uv run bandit -r src/ ui/ -c pyproject.toml --severity-level high
uv run pytest tests/unitarios/ -v --no-lint -m "not lento"
uv run pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=60 --no-lint -m "not lento"
```

Expected: tudo verde.

- [ ] **Step 2: Smoke test via docker**

```bash
docker compose up -d
sleep 15
make seed-users-docker
curl -sf http://localhost:8080/ > /dev/null && echo UI_OK
curl -sf http://localhost:8080/login > /dev/null && echo LOGIN_OK
curl -sf http://localhost:8080/acompanhamento > /dev/null && echo ACOMPANHAMENTO_OK
curl -sf http://localhost:8000/docs > /dev/null && echo SWAGGER_OK
docker compose down
```

Expected: 4 OKs.

- [ ] **Step 3: Smoke test local**

```bash
docker compose up -d postgres
uv run alembic upgrade head
make seed-users
./scripts/run-dev.sh &
BACKEND_PID=$!
sleep 5
make ui &
UI_PID=$!
sleep 3
curl -sf http://localhost:8080/ > /dev/null && echo LOCAL_OK
kill $UI_PID $BACKEND_PID
docker compose down -v
```

Expected: `LOCAL_OK`.

- [ ] **Step 4: Commit final**

Nao ha mudancas de codigo, so verificacao. Pular commit.

### Task 5.8a: Teste visual E2E com Playwright + screenshots

**Files:**
- Create: `tests/e2e_ui/jornadas.md` (relatorio final)
- Create: `tests/e2e_ui/screenshots/` (artefatos visuais, gitignored exceto thumbnails)

Jornada automatizada via Playwright MCP cobrindo o fluxo principal. Gera screenshots em cada etapa, le console/network, e reporta bugs encontrados.

- [ ] **Step 1: Subir stack completa via docker**

```bash
docker compose up -d
sleep 20
docker compose exec -T app python scripts/seed_usuarios.py
curl -sf http://localhost:8080/ > /dev/null && echo UI_OK
curl -sf http://localhost:8000/api/v1/saude > /dev/null && echo BACKEND_OK
```

Expected: `UI_OK` + `BACKEND_OK`.

- [ ] **Step 2: Criar diretorio pra artefatos e .gitkeep**

```bash
mkdir -p tests/e2e_ui/screenshots
touch tests/e2e_ui/screenshots/.gitkeep
```

- [ ] **Step 3: Jornada 1 — login e dashboard como admin**

Via Playwright MCP (mcp__plugin_playwright_playwright__*):
1. `browser_navigate` → `http://localhost:8080/login`
2. `browser_take_screenshot` → `01-login.png`
3. `browser_click` no botao "Admin" (atalho)
4. `browser_wait_for` texto "Dashboard"
5. `browser_take_screenshot` → `02-dashboard-admin.png`
6. `browser_console_messages` — verificar zero erros de console
7. `browser_network_requests` — confirmar GET /api/v1/ordens-de-servico/metricas com 200

Registrar qualquer erro em `tests/e2e_ui/jornadas.md`.

- [ ] **Step 4: Jornada 2 — seed de dados**

1. Na dashboard, `browser_click` em "🎲 Gerar dados de teste"
2. `browser_wait_for` texto "Concluido" (pode levar 10-15s)
3. `browser_take_screenshot` → `03-seed-relatorio.png`
4. Verificar no relatorio: 3 clientes, 5 veiculos, 5 servicos, 10 itens, 4 OS
5. `browser_console_messages` e `browser_network_requests` — zero 500s

- [ ] **Step 5: Jornada 3 — CRUD pages**

1. Navegar para `/clientes` → screenshot `04-clientes-lista.png`
2. Expandir um cliente → screenshot `05-cliente-veiculos.png`
3. Navegar para `/catalogo` → screenshot `06-catalogo.png`
4. Navegar para `/estoque` → screenshot `07-estoque.png` (verificar destaque amarelo em "Junta de motor")

- [ ] **Step 6: Jornada 4 — OS e maquina de estados**

1. Navegar para `/ordens-servico` → screenshot `08-os-lista.png`
2. Clicar numa OS em RECEBIDA → screenshot `09-os-detalhe-recebida.png`
3. Verificar stepper mostra "Recebida" destacado em azul
4. Verificar botoes: "Iniciar diagnostico" (azul) e "Cancelar" (vermelho)
5. Clicar "Iniciar diagnostico" → screenshot `10-apos-diagnostico.png`
6. Verificar stepper avancou pra "Em Diag." em azul; "Recebida" em cinza

- [ ] **Step 7: Jornada 5 — RBAC via switcher**

1. No switcher do cabecalho, trocar pra "mecanico"
2. Pagina recarrega → screenshot `11-papel-mecanico.png`
3. Navegar de volta pra OS detalhe
4. Verificar botao "Cancelar" agora DISABLED com cadeado e tooltip "Exige papel: admin"
5. Screenshot `12-rbac-cancel-bloqueado.png`

- [ ] **Step 8: Jornada 6 — painel HTTP e token masking**

1. Clicar no icone "history" no cabecalho pra abrir o drawer
2. Screenshot `13-painel-http.png`
3. Expandir uma entrada → screenshot `14-painel-http-expandido.png`
4. Verificar que o request body NAO contem nenhum token cru (buscar por prefixo JWT comum `eyJ`)
5. Verificar que exibe `Bearer ****` onde aparece authorization

- [ ] **Step 9: Jornada 7 — acompanhamento publico**

1. Logout → screenshot `15-apos-logout.png`
2. Navegar para `/acompanhamento` → screenshot `16-acompanhamento-form.png`
3. Preencher placa `ABC1D23` + documento `11144477735` (cliente seed)
4. Clicar Consultar → screenshot `17-acompanhamento-resultado.png`
5. Verificar que mostra status da OS do Joao Silva

- [ ] **Step 10: Consolidar relatorio**

Criar `tests/e2e_ui/jornadas.md` listando, pra cada jornada:
- Passos executados + caminho do screenshot
- Erros encontrados (console, network, visual)
- Bugs fixados inline (com SHA do commit)
- Bugs nao fixados (com issue GitHub criada, se houver)

- [ ] **Step 11: Corrigir bugs encontrados**

Para cada bug:
1. Reproduzir localmente
2. Escrever teste unitario/integ que expoe o bug
3. Corrigir
4. Commit: `fix(ui): <descricao curta>`
5. Rerodar a jornada afetada pra confirmar

Se um bug nao for corrigivel nessa PR (escopo diferente, decisao de design), abrir issue com link e continuar.

- [ ] **Step 12: Commit do relatorio + screenshots**

Adicionar ao `.gitignore`:

```
tests/e2e_ui/screenshots/*.png
!tests/e2e_ui/screenshots/.gitkeep
```

```bash
git add .gitignore tests/e2e_ui/jornadas.md tests/e2e_ui/screenshots/.gitkeep
git commit -m "test(ui): add E2E visual journey report with Playwright"
```

(Screenshots ficam locais; o relatorio markdown descreve o que cada um mostra. Alternativa: subir screenshots como artefato do PR via `gh pr comment --body-file` se desejavel.)

- [ ] **Step 13: Derrubar stack**

```bash
docker compose down
```

### Task 5.9: Pre-PR code review via `/code-review` no diff total

**Files:**
- (nenhum — invocacao de skill)

Roda um code review estruturado sobre o diff completo da branch contra `main` antes de abrir o PR. Capta problemas (bugs, seguranca, convencoes do projeto) que revisao humana ainda vai pegar, mas com uma passada automatica primeiro o PR chega mais polido.

- [ ] **Step 1: Confirmar diff e estado da branch**

```bash
git fetch origin
git log --oneline origin/main..HEAD | wc -l   # quantidade de commits na branch
git diff --stat origin/main...HEAD | tail -5  # resumo das mudancas
```

Expected: lista de commits das tasks 1.0 a 5.8, diff stat mostrando criacao de `ui/`, `scripts/seed_usuarios.py`, modificacoes em `pyproject.toml`, `docker-compose.yml`, `Makefile`, `README.md`, `.github/workflows/ci.yml`.

- [ ] **Step 2: Invocar `/code-review` sobre o diff**

No Claude Code, invocar:

```
/code-review
```

Quando pedir o alvo, passar: `diff contra origin/main` (ou simplesmente aceitar o default que ja pega a diff da branch atual contra origin/main).

O skill roda sobre os arquivos modificados e produz uma lista priorizada de issues (bugs, seguranca, violacoes de convencao, TODOs restantes).

- [ ] **Step 3: Triagem dos findings**

Para cada finding do `/code-review`:
- **CRITICO/ALTO**: corrigir agora (commit adicional na mesma branch)
- **MEDIO**: julgar caso a caso — corrigir se for rapido; registrar em `docs/tech-debt.md` se nao
- **BAIXO/informativo**: anotar no corpo do PR como follow-up explicito

- [ ] **Step 4: Corrigir findings CRITICO/ALTO**

Aplicar correcoes na branch, um commit por finding (ou agrupado se forem correlatos). Exemplo de mensagem:

```bash
git commit -m "fix(ui): apply code-review finding — <descricao curta>"
```

- [ ] **Step 5: Rodar pipeline local de novo apos correcoes**

```bash
make check                # lint + typecheck + security + unit tests
uv run pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=60 --no-lint -m "not lento"
```

Expected: tudo verde.

### Task 5.10: Abrir Pull Request

**Files:**
- (nenhum — operacao gh)

- [ ] **Step 1: Empurrar a branch**

```bash
git push -u origin feat/ui-simulacao-nicegui
```

Expected: branch publicada no remote.

- [ ] **Step 2: Criar PR via `gh`**

```bash
gh pr create --title "feat(ui): adiciona UI de simulacao NiceGUI para testes manuais" --body "$(cat <<'EOF'
## Summary

- Adiciona UI de simulacao em Python puro (NiceGUI) para testes manuais integrados da API PytStop.
- Dev-only: nao entra no Dockerfile do backend, nao e artefato de producao. Swagger UI (/docs) continua inalterado.
- Acessivel tanto local (`make ui`) quanto via docker (`make up`).

## Features entregues

- Shell com nav + role switcher (admin/atendente/mecanico) + logout
- Paginas CRUD: clientes (com veiculos e acoes LGPD), catalogo, estoque
- OS: lista, detalhe, stepper visual da maquina de estados, botoes de transicao com enable/disable por papel
- Seed de dados coerentes em 1 clique (3 clientes, 5 veiculos, 5 servicos, 10 itens, 4 OS em estados variados)
- Painel HTTP mostrando request/response das ultimas 50 chamadas (com token mascarado)
- Pagina publica de acompanhamento por placa + documento
- Drift-check garantindo sincronia com o backend na maquina de estados

## Referencias

- Design: `docs/superpowers/specs/2026-04-23-ui-simulacao-design.md`
- Plano: `docs/superpowers/plans/2026-04-23-ui-simulacao.md`

## Test plan

- [ ] `make check` passa (lint + mypy + bandit + testes unitarios >=95% em src/)
- [ ] `uv run pytest tests/unitarios/ui/ --cov=ui --cov-fail-under=60` passa
- [ ] `make up` sobe postgres + app + ui; `make seed-users-docker` popula os 3 papeis
- [ ] Login funciona com cada um dos 3 papeis; switcher troca papel sem relogar manualmente
- [ ] Botao "Gerar dados de teste" popula massa; rerun e idempotente
- [ ] Stepper da OS mostra estado atual; botoes de transicao desabilitam corretamente por papel
- [ ] Painel HTTP lista chamadas com mascaramento do bearer token
- [ ] Acompanhamento publico funciona sem login; rate limit 10/min enforced
- [ ] Swagger UI (http://localhost:8000/docs) continua funcionando inalterado

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Confirmar que PR foi criado**

```bash
gh pr view --json url,number,state | jq
```

Expected: JSON com URL do PR, numero e estado `OPEN`. Anotar o numero do PR para a proxima task.

### Task 5.11: Pos-PR code review via `/code-review:code-review`

**Files:**
- (nenhum — invocacao de skill)

Roda o skill `/code-review:code-review` especificamente sobre o PR aberto. Esse skill foca em feedback estruturado no formato de review de PR (com inline comments sugeridos) que pode ser postado diretamente no GitHub.

- [ ] **Step 1: Invocar `/code-review:code-review` com URL do PR**

No Claude Code:

```
/code-review:code-review <URL-do-PR>
```

- [ ] **Step 2: Avaliar output**

O skill produz:
- Lista de comments sugeridos por arquivo/linha
- Sumario do PR (escopo, coerencia com objetivo)
- Sinais verdes e vermelhos

- [ ] **Step 3: Acao sobre o feedback**

- Se houver feedback acionavel importante → novos commits na branch (triggera re-review de CI)
- Se houver apenas sugestoes de polimento → responder no PR explicando o que acata/rejeita
- Registrar qualquer nit nao acatado como follow-up explicito no corpo do PR

- [ ] **Step 4: Marcar PR como pronto para review humano**

```bash
gh pr edit <numero> --add-label ready-for-review
gh pr comment <numero> --body "Code review automatizado rodado (/code-review + /code-review:code-review). Pronto para revisao humana."
```

---

## Criterio de pronto

Ao final de todas as tasks:

- [ ] UI sobe localmente com `make ui` (backend rodando em :8001)
- [ ] UI sobe via docker com `make up` (porta 8080)
- [ ] `make seed-users` popula 3 papeis no banco idempotentemente
- [ ] Login/logout/switcher funcionam ponta-a-ponta
- [ ] CRUD de clientes, catalogo, estoque funcionam
- [ ] OS: criar, adicionar itens, transicionar pelas 9 acoes (respeitando papel)
- [ ] Stepper visual reflete estado atual
- [ ] Botoes de transicao ficam disable com papel insuficiente
- [ ] Botao "Gerar dados de teste" cria conjunto coerente em <10s
- [ ] Painel HTTP mostra ultimas 50 chamadas com request/response
- [ ] Token mascarado no painel (nunca vaza)
- [ ] LGPD (consentimento, exportar, excluir) acessivel via menu kebab
- [ ] Acompanhamento publico funciona sem login
- [ ] Drift-check quebra CI se backend adicionar novo StatusOrdem
- [ ] Coverage: >=95% em `src/`, >=60% em `ui/`
- [ ] Swagger `/docs` continua funcionando inalterado
- [ ] Nenhuma alteracao em `src/` que afete o backend
- [ ] Jornada E2E visual via Playwright executada e bugs encontrados foram corrigidos
- [ ] Relatorio `tests/e2e_ui/jornadas.md` commitado
- [ ] `/code-review` rodado sobre o diff contra `main` e findings tratados
- [ ] PR aberto contra `main` (branch `feat/ui-simulacao-nicegui`)
- [ ] `/code-review:code-review` rodado sobre o PR e findings tratados
- [ ] PR marcado como pronto para revisao humana



