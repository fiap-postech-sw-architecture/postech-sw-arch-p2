# Setup do zero -- Linux

> [↑ Raiz do projeto](../../README.md)

Guia passo a passo para preparar uma máquina Linux do zero até rodar o projeto. Tempo estimado: 20-40 min com download da rede.

- **Fase 1** (~15 min): clone-ready -- build essentials, GitHub CLI, Docker Engine.
- **Fase 2** (~5 min): dev-ready -- uv, Python 3.12 (opcional, uv resolve).
- **Fase 3** (opcional): Selenium para testes E2E.

> Stack do projeto: Python 3.12 - FastAPI - SQLAlchemy 2 - PostgreSQL 16 - Alembic - uv - Docker Compose v2 - pytest - ruff - mypy.

> Os comandos são para **Ubuntu 22.04+ / Debian 12+** (apt). Para Fedora/RHEL/Arch, ajuste o gerenciador (`dnf`/`pacman`) e o nome dos pacotes -- a estrutura é idêntica.

---

## Antes de começar

### Atualizar a base

Antes de instalar nada novo, atualize índices e pacotes existentes:

```bash
sudo apt update && sudo apt upgrade -y
```

### Distros suportadas implicitamente

- Ubuntu 22.04 LTS, 24.04 LTS
- Debian 12 (Bookworm)
- Linux Mint 21+
- Pop!_OS 22.04+

Para outras distros (Fedora, RHEL, Arch, Alpine, etc.), os passos são análogos -- só muda o gerenciador. As diferenças são marcadas em cada seção.

---

# Fase 1 -- clone-ready

## 1. Build essentials e Git

### Por que

`build-essential` dá `make`, `gcc`, headers C -- necessários para compilar deps Python nativas (psycopg2, cryptography, bcrypt). `git` é óbvio. `curl` e `ca-certificates` para baixar o instalador do uv e adicionar repos apt.

### Verificação prévia

```bash
git --version
make --version | head -1
gcc --version | head -1
curl --version | head -1
```

Se todos responderem, pula.

### Instalação (Ubuntu/Debian)

```bash
sudo apt install -y build-essential git curl ca-certificates gnupg lsb-release
```

### Instalação (Fedora/RHEL)

```bash
sudo dnf groupinstall "Development Tools"
sudo dnf install -y git curl
```

### Instalação (Arch)

```bash
sudo pacman -S --needed base-devel git curl
```

### Verificação

```bash
git --version
make --version | head -1
gcc --version | head -1
```

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

# Credential helper (escolha uma):

# 1. cache em memoria (15 min default)
git config --global credential.helper cache

# 2. armazenamento em texto puro (NAO recomendado)
# git config --global credential.helper store

# 3. libsecret (recomendado em GNOME/KDE -- requer passo extra)
# Veja: https://git-scm.com/docs/git-credential-libsecret
```

> **Dica**: o `gh auth login` (passo 3) configura o credential helper sozinho na maioria das distros. Pula este sub-passo se for usar `gh`.

---

## 2. GitHub CLI (`gh`)

### Por que

Resolve a autenticação de uma vez (escreve token no credential store, então `git clone https://...` funciona depois). Dá comandos úteis para PRs, issues, runs de CI.

### Verificação prévia

```bash
gh --version
```

Se retornar `gh version 2.x.x`, pula instalação e vai para autenticação.

### Instalação via repo oficial (Ubuntu/Debian)

Os repos default do Ubuntu trazem versões desatualizadas. Use o repo oficial do GitHub:

```bash
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y
```

### Instalação (Fedora/RHEL)

```bash
sudo dnf install 'dnf-command(config-manager)'
sudo dnf config-manager addrepo --from-repofile=https://cli.github.com/packages/rpm/gh-cli.repo
sudo dnf install gh
```

### Instalação (Arch)

```bash
sudo pacman -S github-cli
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

## 3. Docker Engine

Você tem **duas opções**:

- **Docker Engine (recomendado)** -- daemon nativo, sem GUI, instalado via repo oficial. Performance máxima.
- **Docker Desktop** -- mesma experiência que Windows/macOS, GUI, roda numa VM. Útil se você já conhece dos outros SOs.

Para este projeto, Docker Engine é mais comum em Linux. Os passos abaixo focam nele.

### Verificação prévia

```bash
docker --version
docker compose version
docker info >/dev/null && echo OK
```

Se tudo responder, pula.

### Remover versões antigas (Ubuntu/Debian)

```bash
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null
```

(Não tem problema se nada estiver instalado -- o comando é idempotente.)

### Instalação via repo oficial (Ubuntu/Debian)

```bash
# Chave GPG e repo oficial
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/$(. /etc/os-release; echo "$ID")/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$(. /etc/os-release; echo "$ID") \
  $(. /etc/os-release; echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Instalação (Fedora/RHEL)

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

### Instalação (Arch)

```bash
sudo pacman -S docker docker-compose
sudo systemctl enable --now docker
```

> **Evite a versão snap do docker no Ubuntu** -- ela tem confinamento que quebra `docker compose` montar volumes em paths arbitrários. Use sempre o repo oficial.

### Pós-instalação -- adicionar usuário ao grupo docker

Sem isso, você precisa rodar `sudo docker ...` toda vez. Adicione seu usuário ao grupo `docker`:

```bash
sudo usermod -aG docker $USER
```

**Reabra a sessão** (logout/login, ou reinicia) para o grupo entrar em vigor. Em uma sessão SSH, basta fazer logout e login.

### Verificação

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Se `docker run hello-world` falhar com `permission denied while trying to connect to the Docker daemon socket`, você não reabriu a sessão após `usermod` -- faz logout/login.

---

## Checklist da fase 1

```bash
git --version
git config --global user.name
git config --global user.email
gh --version
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1
docker --version
docker compose version
docker run --rm hello-world
make --version | head -1
```

Tudo respondendo sem erro = pronto para a fase 2.

---

# Fase 2 -- dev-ready

## 4. uv (gerenciador de pacotes Python)

### Por que

uv é o gerenciador escolhido pelo projeto ([ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md)). Vantagens vs `pip + venv`:

- Lock file determinístico (`uv.lock`) com hashes SHA-256.
- Gerencia o próprio Python: `uv sync` baixa o Python 3.12 automaticamente.
- 10-100x mais rápido que pip.
- `uv run <cmd>` executa no venv sem `activate`.

### Verificação prévia

```bash
uv --version
```

Se retornar `uv 0.x.x`, pula.

### Instalação -- script oficial (recomendado)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Instala em `~/.local/bin/uv`. Adiciona ao PATH editando seu `~/.bashrc` ou `~/.zshrc` (o instalador faz isso, mas você precisa abrir um shell novo).

### Instalação -- alternativa via pipx

```bash
sudo apt install pipx       # ou dnf/pacman equivalente
pipx install uv
```

### Instalação -- alternativa Arch

```bash
sudo pacman -S uv
```

### Pós-instalação

Recarregue o PATH:

```bash
source ~/.bashrc          # ou ~/.zshrc
```

Ou abra um terminal novo.

### Verificação

```bash
uv --version
```

---

## 5. Python 3.12 (opcional)

### Por que talvez você não precise

`pyproject.toml` exige `requires-python = ">=3.12"`. Se você já instalou o `uv`, `uv sync` baixa o Python 3.12 automaticamente em `~/.local/share/uv/python` -- sem precisar mexer no sistema. **Esta é a forma recomendada.**

Instale no sistema **só se** quiser usar `python3.12` direto (fora do `uv run ...`).

### Verificação via uv (recomendado)

Após rodar `uv sync` no projeto:

```bash
uv python list --only-installed
```

Deve listar uma instalação 3.12 baixada pelo uv.

### Instalação do sistema (opcional, Ubuntu 22.04)

Ubuntu 22.04 traz Python 3.10 default. Para ter o 3.12 do sistema, use o PPA deadsnakes:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### Instalação do sistema (Ubuntu 24.04+)

Já vem com 3.12:

```bash
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### Instalação (Fedora 39+)

```bash
sudo dnf install -y python3.12
```

### Instalação (Arch)

Sempre rolling -- já tem o Python mais recente. Pode usar `python` direto se for >=3.12.

### Verificação

```bash
python3.12 --version
```

---

## Checklist da fase 2

```bash
uv --version
make --version | head -1
docker info >/dev/null && echo OK
```

---

# Fase 3 -- opcionais

## 6. Selenium -- para rodar testes `lento` (E2E da UI)

### Por que (e quando pular)

Os testes em `tests/unitarios/ui/componentes/` usam a fixture `screen` da NiceGUI, que sobe Chrome headless e navega na UI. São marcados `@pytest.mark.lento`. Por padrão `make test` e `make check` excluem (`-m "not lento"`), então você não precisa de Selenium para o fluxo normal de dev.

Vale instalar se: quer rodar suite completa local (`make test-lento`), está mexendo em páginas/componentes da UI, ou quer reproduzir falha E2E do CI.

### Pré-requisito: Chrome ou Chromium

```bash
# Ubuntu/Debian
sudo apt install -y chromium-browser

# Fedora
sudo dnf install -y chromium

# Arch
sudo pacman -S chromium
```

Ou Google Chrome (via .deb oficial em https://www.google.com/chrome/).

### O que **nao** precisa instalar

**chromedriver** -- Selenium 4.6+ traz o **Selenium Manager** embutido que baixa o chromedriver compatível automaticamente.

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

Primeira execução baixa o chromedriver. Cache em `~/.cache/selenium/`.

> **WSL2**: se você está rodando dentro do WSL2 no Windows, Chrome headless funciona desde que você tenha o WSLg habilitado (default em Windows 11). Caso contrário, considere rodar os testes lentos no Windows nativo.

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

# Troubleshooting -- específico do Linux

### `permission denied while trying to connect to the Docker daemon socket`
Você não foi adicionado ao grupo `docker` ou não reabriu a sessão após `sudo usermod -aG docker $USER`. Confira com:
```bash
groups | grep docker
```
Se não aparecer `docker`, refaz o `usermod` e faz logout/login.

### `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`
O daemon não está rodando.
```bash
sudo systemctl start docker
sudo systemctl enable docker   # iniciar com a maquina
```

### `gh auth login` não abre o navegador
Em servidor headless ou WSL sem WSLg, copie a URL exibida e cole no navegador da máquina cliente.

### `gh repo view` retorna 404
Você não foi adicionado como colaborador no repo, ou logou na conta errada. Confere com `gh auth status`.

### `apt-get install` reclama de chave GPG do Docker/GitHub
Possível mismatch de versão do `gnupg`. Atualize:
```bash
sudo apt install -y gnupg ca-certificates
```
E refaça a importação da chave (passos da seção do Docker/gh acima).

### Versão do Docker Compose `1.x` (Python) instalada
Algumas distros antigas têm `docker-compose` (script Python, V1) em vez do plugin Compose V2. Este projeto exige V2 (`docker compose`, sem hífen). Desinstale o V1 e instale o plugin:
```bash
sudo apt remove docker-compose
sudo apt install docker-compose-plugin
```

### `iptables` mal configurado quebra a rede dos containers
Sintoma: containers não conseguem fazer DNS ou alcançar a internet.
```bash
sudo iptables -L -n | grep DOCKER   # confere se tem chains DOCKER
```
Se nao tiver, restart:
```bash
sudo systemctl restart docker
```
Se persistir, pode ser conflito com firewall (ufw, firewalld, nftables) -- veja a documentação do Docker em https://docs.docker.com/network/iptables/.

### Testes de integração falham com erro do Ryuk
Específico de containers rootless ou Docker Desktop. Confirme que `/var/run/docker.sock` está acessível ou exporte:
```bash
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
```

### `port already in use` em 5432, 8000, 8080
Algum serviço local já escuta nessas portas. Liste:
```bash
sudo ss -tlnp | grep -E ':(5432|8000|8080)'
```
Postgres do sistema ocupando 5432 é o caso mais comum. Pare:
```bash
sudo systemctl stop postgresql
```

### WSL2 -- I/O lento dentro de `/mnt/c/`
Se você clonou o repo em `/mnt/c/...` (filesystem do Windows acessado pelo WSL), `uv sync` e pytest ficam ordens de magnitude mais lentos. Mova o repo para o filesystem do WSL:
```bash
mv /mnt/c/projetos/postech-sw-arch-p1 ~/projetos/
cd ~/projetos/postech-sw-arch-p1
```

> [↑ Raiz do projeto](../../README.md)
