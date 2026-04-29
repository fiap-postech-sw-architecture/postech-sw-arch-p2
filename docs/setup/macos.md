# Setup do zero -- macOS

Guia passo a passo para preparar uma maquina macOS do zero ate rodar o projeto. Suporta tanto Apple Silicon (M1/M2/M3) quanto Intel. Tempo estimado: 30-60 min com download da rede.

- **Fase 1** (~20 min): clone-ready -- Xcode CLT, Homebrew, GitHub CLI, runtime Docker.
- **Fase 2** (~10 min): dev-ready -- uv, Python 3.12 (opcional, uv resolve).
- **Fase 3** (opcional): Selenium para testes E2E.

> Stack do projeto: Python 3.12 - FastAPI - SQLAlchemy 2 - PostgreSQL 16 - Alembic - uv - Docker Compose v2 - pytest - ruff - mypy.

> Voce nao precisa instalar `make`, `bash`, ou `git` separadamente -- todos vem com o Xcode Command Line Tools (CLT) ou ja estao no sistema.

---

## Antes de comecar

### Terminal recomendado

O Terminal padrao do macOS funciona. Se preferir uma alternativa: iTerm2, Warp, Alacritty -- escolha pessoal, nao afeta nada do que esta abaixo.

### Apple Silicon vs Intel

Quase tudo funciona igual. As diferencas relevantes:

- Homebrew: prefixo `/opt/homebrew` em Apple Silicon, `/usr/local` em Intel.
- Algumas imagens Docker so tem build amd64 -- no Apple Silicon roda em emulacao Rosetta. Imagens deste projeto (Postgres, python:3.12-slim) sao multi-arch, sem problema.

Os comandos abaixo funcionam em ambos. Quando o caminho de prefixo importar, eu menciono.

---

# Fase 1 -- clone-ready

## 1. Xcode Command Line Tools

### Por que

Da `git`, `make`, compiladores C (`clang`), headers do sistema -- pre-requisito do Homebrew e de varias deps Python que compilam codigo nativo (psycopg2, cryptography, etc).

### Verificacao previa

```bash
xcode-select -p
git --version
make --version | head -1
```

Se `xcode-select -p` retornar um path (ex.: `/Library/Developer/CommandLineTools`) e `git`/`make` responderem, pula.

### Instalacao

```bash
xcode-select --install
```

Abre uma janela grafica pedindo para baixar o CLT (~3GB). Aceite. Demora 5-15 min dependendo da rede.

### Verificacao

```bash
xcode-select -p
git --version
make --version | head -1
```

Esperado: path do CLT, `git version 2.4x.x`, `GNU Make 3.81` (versao do macOS) ou superior.

> macOS traz Make 3.81 por padrao (BSD-friendly). O Makefile do projeto funciona com 3.81. Se quiser 4.x, instale via `brew install make` (vira `gmake`).

### Configuracao inicial obrigatoria do Git

```bash
git config --global user.name "Seu Nome Completo"
git config --global user.email "seu@email.com"
```

Use o **mesmo email** da sua conta GitHub.

### Configuracoes recomendadas

```bash
git config --global init.defaultBranch main
git config --global pull.rebase true
git config --global color.ui auto
```

---

## 2. Homebrew

### Por que

Gerenciador de pacotes nao-oficial mas essencial no macOS. Tudo da fase 1 (exceto Xcode CLT) e fase 2 instala via brew.

### Verificacao previa

```bash
brew --version
```

Se retornar `Homebrew 4.x`, pula.

### Instalacao

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

O instalador pede sua senha (sudo) uma vez para criar `/opt/homebrew` (Apple Silicon) ou `/usr/local` (Intel) com a permissao certa.

### Pos-instalacao (Apple Silicon)

O instalador imprime no final 2-3 comandos para adicionar `brew` ao PATH. Execute-os. Tipico:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Verificacao

```bash
brew --version
brew doctor   # opcional, mas util para detectar problemas
```

---

## 3. GitHub CLI (`gh`)

### Por que

Resolve a autenticacao com o GitHub de uma vez (escreve token no Keychain via `osxkeychain` helper, entao `git clone https://...` funciona depois). Da comandos uteis para PRs, issues, runs de CI.

### Verificacao previa

```bash
gh --version
```

Se retornar `gh version 2.x.x`, pula instalacao e va para autenticacao.

### Instalacao

```bash
brew install gh
```

### Verificacao

```bash
gh --version
```

### Autenticacao

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

Mostra um codigo `ABCD-1234`. Copia, abre o navegador na URL exibida (`https://github.com/login/device`), cola o codigo, autoriza.

### Verificacao da auth

```bash
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1 --json name,visibility
```

Se retornar JSON com o nome do repo, voce tem acesso.

> **Pre-requisito de acesso**: o repo e privado. Se voce nao foi adicionado como **collaborator** na organizacao `fiap-postech-sw-architecture`, o comando acima retorna 404 mesmo com `gh auth status` ok. Confira com algum mantenedor da equipe e peca o invite antes de prosseguir.

---

## 4. Runtime Docker

Voce tem **duas opcoes** equivalentes:

- **Docker Desktop** -- mais simples, GUI, mesma experiencia que Windows/Linux. Licenca gratis para uso pessoal e empresas pequenas (verifique os termos atuais).
- **Colima** -- alternativa open source que roda Docker numa VM Lima. Sem GUI, sem licenca para se preocupar, leve.

Os dois funcionam para este projeto. Escolha um. Pode trocar depois.

### Opcao A: Docker Desktop

#### Verificacao previa

```bash
docker --version
docker compose version
docker info | grep -i "operating system"
```

Se retornar versoes e o icone da baleia esta na barra de menu, pula.

#### Instalacao

```bash
brew install --cask docker
```

#### Pos-instalacao

1. Abra o **Docker** pelo Launchpad (icone azul com baleia branca).
2. Aceita o EULA, "Use recommended settings".
3. Espera o icone da baleia na barra de menu ficar estavel.

#### Verificacao

```bash
docker --version
docker compose version
docker run --rm hello-world
```

#### Habilitar socket padrao (recomendado)

Docker Desktop 4.13+ so cria `~/.docker/run/docker.sock` se uma opcao estiver habilitada. Sem isso, o `scripts/docker-check.sh` do projeto pode nao achar o socket.

Em **Docker Desktop > Settings > Advanced**, marque:

> "Allow the default Docker socket to be used (requires password)"

Reinicie o Docker Desktop.

### Opcao B: Colima

#### Instalacao

```bash
brew install colima docker docker-compose
```

`docker` e `docker-compose` sao o CLI; `colima` e a VM que substitui o Docker Desktop.

#### Subir a VM

```bash
colima start
```

Primeira vez demora ~1 min para baixar a imagem da VM Lima. Default e 2 CPUs / 2GB RAM -- suficiente para este projeto.

#### Configuracao do socket

Adicione ao `~/.zshrc` (ou `~/.bashrc`):

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
```

`DOCKER_HOST` diz ao CLI onde achar o socket. `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` e necessario para os testes de integracao do projeto (que usam testcontainers + Ryuk).

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

#### Verificacao

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

uv e o gerenciador escolhido pelo projeto ([ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md)). Vantagens vs `pip + venv`:

- Lock file deterministico (`uv.lock`) com hashes SHA-256.
- Gerencia o proprio Python: `uv sync` baixa o Python 3.12 automaticamente.
- 10-100x mais rapido que pip.
- `uv run <cmd>` executa no venv sem `activate`.

### Verificacao previa

```bash
uv --version
```

Se retornar `uv 0.x.x`, pula.

### Instalacao

```bash
brew install uv
```

### Verificacao

```bash
uv --version
```

---

## 6. Python 3.12 (opcional)

### Por que talvez voce nao precise

`pyproject.toml` exige `requires-python = ">=3.12"`. Se voce ja instalou o `uv` (passo 5), `uv sync` baixa o Python 3.12 automaticamente em `~/.local/share/uv/python` -- voce nao precisa fazer nada. **Esta e a forma recomendada.**

Instale via brew **so se** quiser usar `python3.12` direto (fora do `uv run ...`).

### Verificacao via uv (recomendado)

Apos rodar `uv sync` no projeto:

```bash
uv python list --only-installed
```

Deve listar uma instalacao 3.12 baixada pelo uv.

### Instalacao do sistema (opcional)

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

Os testes em `tests/unitarios/ui/componentes/` usam a fixture `screen` da NiceGUI, que sobe Chrome headless e navega na UI. Sao marcados `@pytest.mark.lento`. Por padrao `make test` e `make check` excluem (`-m "not lento"`), entao voce nao precisa de Selenium para o fluxo normal de dev.

Vale instalar se: quer rodar suite completa local (`make test-lento`), esta mexendo em paginas/componentes da UI, ou quer reproduzir falha E2E do CI.

### Pre-requisito: Chrome ou Chromium

Tem 95% de chance de ja ter. Senao:

```bash
brew install --cask google-chrome
```

### O que **nao** precisa instalar

**chromedriver** -- Selenium 4.6+ traz o **Selenium Manager** embutido que baixa o chromedriver compativel com sua versao do Chrome automaticamente.

### Instalar `selenium` no projeto

Dentro do repo:

```bash
uv pip install selenium
```

Instala no `.venv` do projeto sem tocar `pyproject.toml`/`uv.lock`.

### Verificacao

```bash
uv run python -c "import selenium; print(selenium.__version__)"
```

### Rodar os testes lentos

```bash
uv run pytest tests/unitarios/ui/componentes/ -m lento -v --no-lint
```

Primeira execucao baixa o chromedriver. Cache em `~/Library/Caches/selenium/` (ou `~/.cache/selenium/`).

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

# Troubleshooting -- especifico do macOS

### `xcode-select --install` nao abre janela
Tenta direto pelo Mac App Store -- pesquise "Xcode" e instale (mais pesado: ~12GB), ou baixe so o CLT em https://developer.apple.com/download/all/ filtrando por "Command Line Tools".

### Apos atualizar o macOS, `xcrun: error`
Os tools precisam ser reaceitos:
```bash
sudo xcode-select --reset
xcode-select --install
```

### `brew install` reclama de permissoes em `/opt/homebrew` ou `/usr/local`
Em geral nao deveria acontecer com instalacao limpa. Se acontecer:
```bash
sudo chown -R $(whoami) $(brew --prefix)/*
```

### `gh auth login` nao abre o navegador
Copie a URL exibida no terminal e cole manualmente.

### `gh repo view` retorna 404
Voce nao foi adicionado como colaborador no repo, ou logou na conta errada. Confere com `gh auth status`.

### `docker compose` nao encontrado (Colima ou Docker via brew)
Compose v2 e plugin do CLI, precisa estar registrado. Adicione ao `~/.docker/config.json`:
```json
{ "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"] }
```
(Use `/usr/local/...` em Intel.) Confirme com `docker compose version`.

### `failed to connect to docker API` em `docker compose up -d`
Socket nao encontrado. Veja a secao "Habilitar socket padrao" (Docker Desktop) ou "Configuracao do socket" (Colima) acima. O [debugging-guide](../debugging-guide.md) tem mais detalhes.

### Testes de integracao falham com erro do Ryuk
Especifico de Colima. Confirme que `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` esta exportado no shell. Reabra o terminal apos editar o `~/.zshrc`.

### Imagens Docker amd64-only no Apple Silicon
Algumas imagens nao tem build arm64 e rodam em Rosetta (lentas). As do projeto (Postgres 16, python:3.12-slim) sao multi-arch -- nao deveria acontecer. Se tiver duvida:
```bash
docker image inspect <imagem> --format '{{.Architecture}}'
```

### `port already in use` em 5432, 8000, 8080
Algum servico local esta nas portas que o compose quer. Liste:
```bash
lsof -nP -iTCP:5432 -sTCP:LISTEN
```
Mate o processo conflitante ou pare o servico (Postgres rodando localmente, por exemplo).
