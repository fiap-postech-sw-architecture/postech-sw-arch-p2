# Setup do zero -- macOS

> [↑ Raiz do projeto](../../README.md)

Guia passo a passo para preparar uma máquina macOS do zero até rodar o projeto. Suporta tanto Apple Silicon (M1/M2/M3) quanto Intel. Tempo estimado: 30-60 min com download da rede.

- **Fase 1** (~20 min): clone-ready -- Xcode CLT, Homebrew, GitHub CLI, runtime Docker.
- **Fase 2** (~10 min): dev-ready -- uv, Python 3.14 (opcional, uv resolve).
- **Fase 3** (opcional): Selenium para testes E2E.

> Stack do projeto: Python 3.14 - FastAPI - SQLAlchemy 2 - PostgreSQL 16 - Alembic - uv - Docker Compose v2 - pytest - ruff - mypy.

> Você não precisa instalar `make`, `bash`, ou `git` separadamente -- todos vêm com o Xcode Command Line Tools (CLT) ou já estão no sistema.

---

## Antes de começar

### Terminal recomendado

O Terminal padrão do macOS funciona. Se preferir uma alternativa: iTerm2, Warp, Alacritty -- escolha pessoal, não afeta nada do que está abaixo.

### Apple Silicon vs Intel

Quase tudo funciona igual. As diferenças relevantes:

- Homebrew: prefixo `/opt/homebrew` em Apple Silicon, `/usr/local` em Intel.
- Algumas imagens Docker só têm build amd64 -- no Apple Silicon roda em emulação Rosetta. Imagens deste projeto (Postgres, python:3.12-slim) são multi-arch, sem problema.

Os comandos abaixo funcionam em ambos. Quando o caminho de prefixo importar, eu menciono.

---

# Fase 1 -- clone-ready

## 1. Xcode Command Line Tools

### Por que

Dá `git`, `make`, compiladores C (`clang`), headers do sistema -- pré-requisito do Homebrew e de várias deps Python que compilam código nativo (psycopg2, cryptography, etc).

### Verificação prévia

```bash
xcode-select -p
git --version
make --version | head -1
```

Se `xcode-select -p` retornar um path (ex.: `/Library/Developer/CommandLineTools`) e `git`/`make` responderem, pula.

### Instalação

```bash
xcode-select --install
```

Abre uma janela gráfica pedindo para baixar o CLT (~3GB). Aceite. Demora 5-15 min dependendo da rede.

### Verificação

```bash
xcode-select -p
git --version
make --version | head -1
```

Esperado: path do CLT, `git version 2.4x.x`, `GNU Make 3.81` (versão do macOS) ou superior.

> macOS traz Make 3.81 por padrão (BSD-friendly). O Makefile do projeto funciona com 3.81. Se quiser 4.x, instale via `brew install make` (vira `gmake`).

### Configuração inicial obrigatória do Git

```bash
git config --global user.name "Seu Nome Completo"
git config --global user.email "seu@email.com"
```

Use o **mesmo email** da sua conta GitHub.

### Configurações recomendadas

```bash
git config --global init.defaultBranch main
git config --global pull.rebase true
git config --global color.ui auto
```

---

## 2. Homebrew

### Por que

Gerenciador de pacotes não-oficial mas essencial no macOS. Tudo da fase 1 (exceto Xcode CLT) e fase 2 instala via brew.

### Verificação prévia

```bash
brew --version
```

Se retornar `Homebrew 4.x`, pula.

### Instalação

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

O instalador pede sua senha (sudo) uma vez para criar `/opt/homebrew` (Apple Silicon) ou `/usr/local` (Intel) com a permissão certa.

### Pós-instalação (Apple Silicon)

O instalador imprime no final 2-3 comandos para adicionar `brew` ao PATH. Execute-os. Típico:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Verificação

```bash
brew --version
brew doctor   # opcional, mas util para detectar problemas
```

---

## 3. GitHub CLI (`gh`)

### Por que

Resolve a autenticação com o GitHub de uma vez (escreve token no Keychain via `osxkeychain` helper, então `git clone https://...` funciona depois). Dá comandos úteis para PRs, issues, runs de CI.

### Verificação prévia

```bash
gh --version
```

Se retornar `gh version 2.x.x`, pula instalação e vá para autenticação.

### Instalação

```bash
brew install gh
```

### Verificação

```bash
gh --version
```

### Autenticação

```bash
gh auth login
```

Responda assim:

| Pergunta                                            | Resposta                     |
| --------------------------------------------------- | ---------------------------- |
| What account do you want to log into?               | **GitHub.com**               |
| What is your preferred protocol for Git operations? | **HTTPS**                    |
| Authenticate Git with your GitHub credentials?      | **Yes**                      |
| How would you like to authenticate GitHub CLI?      | **Login with a web browser** |

Mostra um código `ABCD-1234`. Copia, abre o navegador na URL exibida (`https://github.com/login/device`), cola o código, autoriza.

### Verificação da auth

```bash
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1 --json name,visibility
```

Se retornar JSON com o nome do repo, você tem acesso.

> **Pré-requisito de acesso**: o repo é privado. Se você não foi adicionado como **collaborator** na organização `fiap-postech-sw-architecture`, o comando acima retorna 404 mesmo com `gh auth status` ok. Confira com algum mantenedor da equipe e peça o invite antes de prosseguir.

---

## 4. Runtime Docker

Você tem **duas opções** equivalentes:

- **Docker Desktop** -- mais simples, GUI, mesma experiência que Windows/Linux. Licença grátis para uso pessoal e empresas pequenas (verifique os termos atuais).
- **Colima** -- alternativa open source que roda Docker numa VM Lima. Sem GUI, sem licença para se preocupar, leve.

Os dois funcionam para este projeto. Escolha um. Pode trocar depois.

### Opção A: Docker Desktop

#### Verificação prévia

```bash
docker --version
docker compose version
docker info | grep -i "operating system"
```

Se retornar versões e o ícone da baleia está na barra de menu, pula.

#### Instalação

```bash
brew install --cask docker
```

#### Pós-instalação

1. Abra o **Docker** pelo Launchpad (ícone azul com baleia branca).
2. Aceita o EULA, "Use recommended settings".
3. Espera o ícone da baleia na barra de menu ficar estável.

#### Verificação

```bash
docker --version
docker compose version
docker run --rm hello-world
```

#### Habilitar socket padrão (recomendado)

Docker Desktop 4.13+ só cria `~/.docker/run/docker.sock` se uma opção estiver habilitada. Sem isso, o `scripts/docker-check.sh` do projeto pode não achar o socket.

Em **Docker Desktop > Settings > Advanced**, marque:

> "Allow the default Docker socket to be used (requires password)"

Reinicie o Docker Desktop.

### Opção B: Colima

#### Instalação

```bash
brew install colima docker docker-compose
```

`docker` e `docker-compose` são o CLI; `colima` é a VM que substitui o Docker Desktop.

#### Subir a VM

```bash
colima start
```

Primeira vez demora ~1 min para baixar a imagem da VM Lima. Default é 2 CPUs / 2GB RAM -- suficiente para este projeto.

#### Configuração do socket

Adicione ao `~/.zshrc` (ou `~/.bashrc`):

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
```

`DOCKER_HOST` diz ao CLI onde achar o socket. `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` é necessário para os testes de integração do projeto (que usam testcontainers + Ryuk).

Aplica:

```bash
source ~/.zshrc
```

#### Plugin docker compose v2

Se `docker compose` falhar com `unknown command`, registre o plugin do brew. Em `~/.docker/config.json`, adicione:

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

(Em Intel use `/usr/local/lib/docker/cli-plugins`.)

#### Verificação

```bash
docker --version
docker compose version
docker run --rm hello-world
```

---

## Checklist da fase 1

```bash
git --version
git config --global user.name
git config --global user.email
brew --version
gh --version
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1
docker --version
docker compose version
docker run --rm hello-world
```

Tudo respondendo sem erro = pronto para a fase 2.

---

# Fase 2 -- dev-ready

## 5. uv (gerenciador de pacotes Python)

### Por que

uv é o gerenciador escolhido pelo projeto ([ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md)). Vantagens vs `pip + venv`:

- Lock file determinístico (`uv.lock`) com hashes SHA-256.
- Gerencia o próprio Python: `uv sync` baixa o Python 3.14 automaticamente.
- 10-100x mais rápido que pip.
- `uv run <cmd>` executa no venv sem `activate`.

### Verificação prévia

```bash
uv --version
```

Se retornar `uv 0.x.x`, pula.

### Instalação

```bash
brew install uv
```

### Verificação

```bash
uv --version
```

---

## 6. Python 3.14 (opcional)

### Por que talvez você não precise

`pyproject.toml` exige `requires-python = ">=3.12"`. Se você já instalou o `uv` (passo 5), `uv sync` baixa o Python 3.14 automaticamente em `~/.local/share/uv/python` -- você não precisa fazer nada. **Esta é a forma recomendada.**

Instale via brew **só se** quiser usar `python3.12` direto (fora do `uv run ...`).

### Verificação via uv (recomendado)

Após rodar `uv sync` no projeto:

```bash
uv python list --only-installed
```

Deve listar uma instalação 3.12 baixada pelo uv.

### Instalação do sistema (opcional)

```bash
brew install python@3.12
```

Verifica:

```bash
python3.12 --version
```

---

## Checklist da fase 2

```bash
uv --version
make --version | head -1   # ja instalado pelo Xcode CLT
docker info >/dev/null && echo OK
```

---

# Fase 3 -- opcionais

## 7. Selenium -- para rodar testes `lento` (E2E da UI)

### Por que (e quando pular)

Os testes em `tests/unitarios/ui/componentes/` usam a fixture `screen` da NiceGUI, que sobe Chrome headless e navega na UI. São marcados `@pytest.mark.lento`. Por padrão `make test` e `make check` excluem (`-m "not lento"`), então você não precisa de Selenium para o fluxo normal de dev.

Vale instalar se: quer rodar suite completa local (`make test-lento`), está mexendo em páginas/componentes da UI, ou quer reproduzir falha E2E do CI.

### Pre-requisito: Chrome ou Chromium

Tem 95% de chance de já ter. Senão:

```bash
brew install --cask google-chrome
```

### O que **nao** precisa instalar

**chromedriver** -- Selenium 4.6+ traz o **Selenium Manager** embutido que baixa o chromedriver compatível com sua versão do Chrome automaticamente.

### Instalar `selenium` no projeto

Dentro do repo:

```bash
uv pip install selenium
```

Instala no `.venv` do projeto sem tocar `pyproject.toml`/`uv.lock`.

### Verificação

```bash
uv run python -c "import selenium; print(selenium.__version__)"
```

### Rodar os testes lentos

```bash
uv run pytest tests/unitarios/ui/componentes/ -m lento -v --no-lint
```

Primeira execução baixa o chromedriver. Cache em `~/Library/Caches/selenium/` (ou `~/.cache/selenium/`).

---

# Subindo o projeto

Com a fase 1 e fase 2 prontas:

```bash
git clone https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1.git
cd postech-sw-arch-p1
make reset-db                    # postgres + backend + UI + seed (usuarios + demo)
```

URLs, credenciais seed e variantes (`SKIP_DEMO=1`, `make rebuild`, etc.):
veja o [Quick Start no README raiz](../../README.md#quick-start). Workflow
de dev (uvicorn hot-reload, checks locais, atualizar deps):
[`docs/desenvolvimento.md`](../desenvolvimento.md).

---

# Troubleshooting -- específico do macOS

### `xcode-select --install` não abre janela
Tenta direto pelo Mac App Store -- pesquise "Xcode" e instale (mais pesado: ~12GB), ou baixe só o CLT em https://developer.apple.com/download/all/ filtrando por "Command Line Tools".

### Após atualizar o macOS, `xcrun: error`
Os tools precisam ser reaceitos:
```bash
sudo xcode-select --reset
xcode-select --install
```

### `brew install` reclama de permissões em `/opt/homebrew` ou `/usr/local`
Em geral não deveria acontecer com instalação limpa. Se acontecer:
```bash
sudo chown -R $(whoami) $(brew --prefix)/*
```

### `gh auth login` não abre o navegador
Copie a URL exibida no terminal e cole manualmente.

### `gh repo view` retorna 404
Você não foi adicionado como colaborador no repo, ou logou na conta errada. Confere com `gh auth status`.

### `docker compose` não encontrado (Colima ou Docker via brew)
Compose v2 é plugin do CLI, precisa estar registrado. Adicione ao `~/.docker/config.json`:
```json
{ "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"] }
```
(Use `/usr/local/...` em Intel.) Confirme com `docker compose version`.

### `failed to connect to docker API` em `docker compose up -d`
Socket não encontrado. Veja a seção "Habilitar socket padrão" (Docker Desktop) ou "Configuração do socket" (Colima) acima. O [debugging-guide](../debugging-guide.md) tem mais detalhes.

### Testes de integração falham com erro do Ryuk
Específico de Colima. Confirme que `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` está exportado no shell. Reabra o terminal após editar o `~/.zshrc`.

### Imagens Docker amd64-only no Apple Silicon
Algumas imagens não têm build arm64 e rodam em Rosetta (lentas). As do projeto (Postgres 16, python:3.12-slim) são multi-arch -- não deveria acontecer. Se tiver dúvida:
```bash
docker image inspect <imagem> --format '{{.Architecture}}'
```

### `port already in use` em 5432, 8000, 8080
Algum serviço local está nas portas que o compose quer. Liste:
```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
```
Mate o processo conflitante ou pare o serviço (Postgres rodando localmente, por exemplo).

> [↑ Raiz do projeto](../../README.md)
