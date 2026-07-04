# Setup do zero -- Windows 11

> [↑ Raiz do projeto](../../README.md)

Guia passo a passo para preparar uma máquina Windows do zero até rodar o projeto. Todas as ferramentas são instaladas via `winget` (gerenciador de pacotes oficial do Windows). Tempo estimado: 30-60 min com download da rede.

- **Fase 1** (~20 min): clone-ready -- PowerShell 7+, Git, GitHub CLI, Docker Desktop.
- **Fase 2** (~10 min): dev-ready -- uv, Python 3.14 (opcional, uv resolve), make.
- **Fase 3** (opcional): Selenium para testes E2E, ou WSL2 Ubuntu como alternativa.

> Stack do projeto: Python 3.14 - FastAPI - SQLAlchemy 2 - PostgreSQL 16 - Alembic - uv - Docker Compose v2 - pytest - ruff - mypy.

---

## Antes de começar

### Abrindo um terminal como Administrador

Os pacotes da fase 1 instalam componentes de sistema (services, drivers WSL, PATH machine-wide), então precisam de UAC:

1. Tecla Windows -> digita `powershell`
2. Botão direito em **Windows PowerShell** -> **Run as administrator**
3. Confirma o UAC

Use esse terminal admin para os passos da fase 1. Os pacotes da fase 2 (uv, make) instalam em **escopo de usuário** com `--scope user` -- não precisam admin.

### Verificando winget

```powershell
winget --version
```

Esperado: `v1.28.x` ou superior. Se não tiver, atualize **App Installer** pela Microsoft Store ou baixe em https://aka.ms/getwinget.

---

# Fase 1 -- clone-ready

## 1. PowerShell 7+

### Por que

Windows PowerShell 5.1 (embutido) é legado. PowerShell 7+ tem `&&`/`||`, ternários, melhor compatibilidade com CLIs modernas e menos quirks de encoding. Coexiste com o 5.1; comando é `pwsh` em vez de `powershell`.

### Verificação prévia

```powershell
pwsh --version
```

Se retornar `PowerShell 7.x.x`, pula esta seção.

### Instalação

PowerShell **admin**:

```powershell
winget install --id Microsoft.PowerShell --source winget --accept-source-agreements --accept-package-agreements
```

### Pós-instalação

Feche o admin, abra um terminal novo (qualquer um) e use `pwsh`:

```powershell
pwsh --version
```

---

## 2. Git para Windows

### Por que

Sem Git, sem clone. O instalador "Git for Windows" também traz:

- **Git Bash** -- terminal estilo Unix com `bash`, `ls`, `grep`, `ssh`, etc. Necessário porque o `Makefile` deste projeto usa `bash -c '...'` em várias regras (não roda em PowerShell).
- **Git Credential Manager (GCM)** -- guarda token do GitHub no Windows Credential Vault. É o que o `gh` usa para autenticar `git push`/`pull` sem te perguntar senha.

### Verificação prévia

```powershell
git --version
```

Se retornar `git version 2.4x.x.windows.x`, pula a instalação -- mas confirme a config inicial abaixo.

### Instalação

PowerShell **admin**:

```powershell
winget install --id Git.Git --source winget --accept-source-agreements --accept-package-agreements
```

Defaults aplicados (recomendados): branch inicial `main`, credential helper GCM, `core.autocrlf=true`. Se quiser controle fino, baixe o instalador interativo em https://git-scm.com/download/win.

### Pós-instalação

Feche e reabra o terminal.

```powershell
git --version
```

### Configuração inicial obrigatória

Sem isso, git recusa criar commits. Em qualquer terminal:

```powershell
git config --global user.name "Seu Nome Completo"
git config --global user.email "seu@email.com"
```

Use o **mesmo email** da sua conta GitHub para que commits apareçam associados ao seu perfil.

### Configurações recomendadas

```powershell
git config --global init.defaultBranch main
git config --global credential.helper manager
git config --global pull.rebase true
git config --global color.ui auto
```

---

## 3. GitHub CLI (`gh`)

### Por que

Resolve autenticação de uma vez (escreve token no GCM, então `git clone https://...` funciona depois). Dá comandos úteis para PRs, issues, runs de CI.

### Verificação prévia

```powershell
gh --version
```

Se retornar `gh version 2.x.x`, pula instalação e vá para autenticação.

### Instalação

PowerShell **admin** (suporta `--scope user` também, mas em admin garante PATH machine-wide):

```powershell
winget install --id GitHub.cli --source winget --accept-source-agreements --accept-package-agreements
```

### Pós-instalação

Feche e reabra o terminal.

```powershell
gh --version
```

### Autenticação

Terminal **normal** (não precisa admin):

```powershell
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

```powershell
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1 --json name,visibility
```

Se o `gh repo view` retornar JSON com o nome do repo, você tem acesso.

> **Pré-requisito de acesso**: o repo é privado. Se você não foi adicionado como **collaborator** na organização `fiap-postech-sw-architecture`, o comando acima retorna 404 mesmo com `gh auth status` ok. Confira com algum mantenedor da equipe e peça o invite antes de prosseguir.

---

## 4. Docker Desktop

### Por que

O projeto roda em containers (Postgres + backend + UI). Docker Desktop é a forma mais comum no Windows.

### Verificação prévia

```powershell
docker --version
docker compose version
```

Se ambos responderem, pula a instalação. Confirma também que o ícone da baleia está na bandeja (sem animação = engine subiu).

### Pré-requisito: WSL 2

```powershell
wsl --status
```

Se não tiver, em PowerShell admin:

```powershell
wsl --install
```

E reinicia.

### Instalação

PowerShell **admin**:

```powershell
winget install --id Docker.DockerDesktop --source winget --accept-source-agreements --accept-package-agreements
```

### Pós-instalação

1. **Reinicie a máquina** (Docker habilita componentes do Windows que exigem reboot).
2. Abre o **Docker Desktop** uma vez pelo menu Iniciar.
3. Aceita o EULA, escolhe "Use recommended settings".
4. Espera o ícone da baleia ficar estável na bandeja.

### Verificação

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

O último comando baixa uma imagem mínima e executa. Se imprimir "Hello from Docker!", está funcionando.

### Erro "DockerDesktop must be owned by an elevated account"

Sobra de uma tentativa anterior. Apaga a pasta vazia e reinstala:

```powershell
Remove-Item 'C:\ProgramData\DockerDesktop' -Recurse -Force
winget install --id Docker.DockerDesktop --source winget --accept-source-agreements --accept-package-agreements
```

---

## Checklist da fase 1

Em qualquer terminal:

```powershell
pwsh --version
git --version
git config --global user.name
git config --global user.email
gh --version
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1
docker --version
docker compose version
docker run --rm hello-world
```

Todos respondendo sem erro = pronto para a fase 2.

---

# Fase 2 -- dev-ready

> **Sem admin nesta fase**: `uv` e `make` instalam em escopo de usuário (`--scope user`). PowerShell normal serve.

## 5. uv (gerenciador de pacotes Python)

### Por que

uv é o gerenciador escolhido pelo projeto ([ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md)). Vantagens vs `pip + venv`:

- Lock file determinístico (`uv.lock`) com hashes SHA-256 -- resolução reproduzível entre máquinas e CI.
- Gerencia o próprio Python: `uv sync` baixa o Python 3.14 automaticamente se não estiver no sistema. Você não precisa instalar Python 3.14 separadamente.
- 10-100x mais rápido que pip.
- `uv run <cmd>` executa no venv sem precisar `activate`.

### Verificação prévia

```powershell
uv --version
```

Se retornar `uv 0.x.x`, pula.

### Instalação (sem admin)

```powershell
winget install --id astral-sh.uv --scope user --accept-source-agreements --accept-package-agreements
```

`--scope user` cai em `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*` e adiciona ao PATH do usuário. Sem UAC.

### Pós-instalação

Feche e reabra qualquer terminal.

```powershell
uv --version
```

---

## 6. Python 3.14 (opcional)

### Por que talvez você não precise

`pyproject.toml` exige `requires-python = ">=3.12"`. Se você já instalou o `uv` (passo 5), `uv sync` baixa o Python 3.14 automaticamente em `%LOCALAPPDATA%\uv\python` -- você não precisa fazer nada manual. **Esta é a forma recomendada.**

Instale Python 3.14 do sistema **só se** quiser usar `python` direto (fora do `uv run ...`), ou se preferir não delegar a versão para o uv.

### Verificação via uv (recomendado)

Após rodar `uv sync` no projeto:

```powershell
uv python list --only-installed
```

Deve listar uma instalação 3.12 baixada pelo uv.

### Instalação do sistema (opcional)

PowerShell admin:

```powershell
winget install --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements
```

Verifica:

```powershell
py -3.12 --version
```

O launcher `py` permite ter múltiplas versões -- `py -3.12`, `py -3.11`, etc.

---

## 7. make (com Git Bash)

### Por que

O `Makefile` é o caminho preferido para os comandos do dia a dia (`make up`, `make seed-demo`, `make reset-db`, `make check`, etc).

### O detalhe importante

O `Makefile` usa `bash -c '...'`, `source script.sh`, `command -v`, `printf` -- sintaxe POSIX/bash, **não PowerShell**. Você **não roda `make` no PowerShell**, e sim no **Git Bash** (instalado junto com o Git for Windows na fase 1).

### Verificação prévia

Abra o **Git Bash** (no menu Iniciar, "Git Bash"):

```bash
make --version
```

Se retornar `GNU Make 4.x`, pula.

### Instalação (sem admin)

PowerShell normal:

```powershell
winget install --id ezwinports.make --scope user --accept-source-agreements --accept-package-agreements
```

User-scope cai em `%LOCALAPPDATA%\Microsoft\WinGet\Packages\ezwinports.make_*\bin\` e é adicionado ao PATH do usuário, acessível tanto em PowerShell quanto Git Bash.

### Pós-instalação

Feche e reabra o Git Bash.

```bash
make --version
bash --version | head -1
```

Esperado: `GNU Make 4.4.x` e `GNU bash, version 5.x`.

---

## Checklist da fase 2

No **Git Bash**:

```bash
uv --version
make --version | head -1
docker info >/dev/null && echo OK
```

---

# Fase 3 -- opcionais

## 8. Selenium -- para rodar testes `lento` (E2E da UI)

### Por que (e quando pular)

Os testes em `tests/unitarios/ui/componentes/` usam a fixture `screen` da NiceGUI, que sobe Chrome headless e navega na UI. São marcados `@pytest.mark.lento`. Por padrão `make test` e `make check` excluem (`-m "not lento"`), então você não precisa de Selenium para o fluxo normal de dev.

Vale instalar se: quer rodar suite completa local (`make test-lento`), está mexendo em páginas/componentes da UI, ou quer reproduzir falha E2E do CI.

### Pré-requisito: Chrome

Tem 99% de chance de já estar instalado. Senão:

```powershell
winget install --id Google.Chrome --scope user --accept-source-agreements --accept-package-agreements
```

### O que **não** precisa instalar

**chromedriver** -- Selenium 4.6+ traz o **Selenium Manager** embutido que baixa o chromedriver compatível com sua versão do Chrome automaticamente, na primeira execução. Sem PATH manual.

### Instalar `selenium` no projeto

No Git Bash, dentro do repo:

```bash
uv pip install selenium
```

Instala no `.venv` do projeto sem tocar `pyproject.toml`/`uv.lock` (decisão consciente do projeto: extras leves por padrão).

### Verificação

```bash
uv run python -c "import selenium; print(selenium.__version__)"
```

### Rodar os testes lentos

```bash
uv run pytest tests/unitarios/ui/componentes/ -m lento -v
```

Primeira execução baixa o chromedriver (segundos). Cache em `%USERPROFILE%\.cache\selenium\`.

---

## 9. WSL2 Ubuntu (alternativa ao caminho Windows nativo)

### Quando considerar

Se você for desenvolver Python intensivamente, vale instalar uma distro Linux real no WSL2:

- README, scripts e Makefile são escritos pensando em Unix -- zero atrito.
- Performance de I/O melhor para `uv sync`, pytest, etc (desde que o código esteja **dentro** do filesystem do WSL, ex.: `~/projetos/`, **não** em `/mnt/c/`).
- Docker Desktop integra com WSL2 -- `docker` funciona dentro da distro sem instalar nada extra.

### Quando pular

Se prefere ficar no Windows nativo, o caminho native (Git Bash + make + uv) funciona perfeitamente. Pula esta seção.

### Verificação prévia

```powershell
wsl --list --verbose
```

Se listar `Ubuntu` (ou outra distro além de `docker-desktop`), pula a instalação.

### Instalação

PowerShell admin:

```powershell
wsl --install -d Ubuntu
```

Após o reboot, o Ubuntu abre uma janela pedindo username e senha (independente da sua conta Windows).

### Setup dentro do Ubuntu

Veja o guia [Linux](linux.md) -- as mesmas instruções valem dentro do WSL.

> Se você usar WSL **e** Windows nativo, você vai ter **duas instalações** (gh/git/uv) e duas autenticações. Escolha qual é sua "casa" e fica nela.

---

# Subindo o projeto

## Antes do primeiro `make`: garantir `make` e `uv` no PATH do Git Bash

Pacotes instalados via `winget --scope user` (caso de `uv` e `ezwinports.make` na fase 2) entram no Windows User PATH, **mas o MSYS2 do Git Bash não herda essas entradas no startup com confiabilidade**. Resultado: `bash: make: command not found` mesmo com o pacote instalado e sessão reaberta. A solução padrão é adicionar os dois caminhos ao `~/.bashrc` -- uma vez só, vale para todas as sessões futuras:

```bash
cat >> ~/.bashrc <<'EOF'

# Pacotes user-scope do winget que o MSYS2 nao herda no startup do Git Bash.
# Cobre 'make' (ezwinports.make) e 'uv' (astral-sh.uv).
export PATH="$HOME/AppData/Local/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$HOME/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"
EOF
source ~/.bashrc
which make uv
```

Esperado: dois paths sob `WinGet/Packages/`. Se o nome do pacote tiver versão no diretório (winget atualizou), ajuste copiando o caminho exato de `ls "$HOME/AppData/Local/Microsoft/WinGet/Packages"`.

> Se você já tem `make` e `uv` no PATH (instalados de outra forma, por exemplo brew/scoop), pula este passo. Confere com `which make uv` antes.

## Comandos do dia a dia

Com a fase 1 e fase 2 prontas, no **Git Bash** dentro do diretório do repo:

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

# Troubleshooting -- específico do Windows

### `winget` não é reconhecido
Atualize o App Installer pela Microsoft Store, ou baixe em https://aka.ms/getwinget.

### `winget install` retorna "already installed"
Tudo certo, pula. Para forçar atualização:
```powershell
winget upgrade --id <pacote>
```

### `git`, `gh` não reconhecidos depois de instalar
Feche **todos** os terminais (incluindo VS Code, IDEs) e abra um novo. PATH só recarrega em processos novos. Se persistir, confirme se o pacote está no PATH:
```powershell
[System.Environment]::GetEnvironmentVariable('Path','User') -split ';' | Where-Object { $_ -like '*WinGet*' }
[System.Environment]::GetEnvironmentVariable('Path','Machine') -split ';' | Where-Object { $_ -like '*GitHub*' -or $_ -like '*Git*' }
```

### `make` ou `uv` não reconhecidos no Git Bash mesmo após reabrir
MSYS2 não herda algumas entradas user-scope do winget no startup. Adicione ambos no `~/.bashrc` -- veja a seção [Antes do primeiro `make`](#antes-do-primeiro-make-garantir-make-e-uv-no-path-do-git-bash) acima.

### `git push`/`pull` pedindo senha o tempo todo
Git Credential Manager não está ativo:
```powershell
git config --global credential.helper manager
gh auth login   # regrava o token no GCM
```

### `gh auth login` não abre o navegador
Copie a URL exibida no terminal e cole manualmente.

### `gh repo view` retorna 404
Você não foi adicionado como colaborador no repo, ou logou na conta errada. Confere com `gh auth status`.

### Docker Desktop trava em "Starting..."
Geralmente WSL 2 mal configurado. Em PowerShell admin:
```powershell
wsl --update
wsl --set-default-version 2
```
E reinicia.

### Política de execução do PowerShell bloqueando scripts
Se algum `.ps1` for bloqueado, em PowerShell admin:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### CRLF warnings no Git
Mensagens `warning: LF will be replaced by CRLF` são normais com `core.autocrlf=true`. Pode ignorar.

### Scripts `.sh` reclamam de `\r: command not found`
Git for Windows converteu LF->CRLF nos scripts. Force LF:
```bash
git config core.autocrlf input
git rm --cached -r .
git reset --hard
```

### `make up` falha com "Nenhum socket Docker encontrado"
Apenas em commits antigos do projeto (anteriores ao fix do `scripts/docker-check.sh` para Windows). Workaround:
```bash
echo 'export DOCKER_HOST="npipe:////./pipe/docker_engine"' >> ~/.bashrc
source ~/.bashrc
```

### `make seed-users-docker` ou `make reset-db` quebram com "No such file or directory" referenciando algo tipo `/app/C:/Users/...`
Era um bug conhecido quando o Makefile passava `/tmp/seed_usuarios.py` pro `docker compose exec`: MSYS2 (Git Bash) traduzia o `/tmp/...` pra um path Windows antes de chegar no docker.exe (binário nativo). O Makefile do projeto agora usa `MSYS_NO_PATHCONV=1` nesses comandos -- a flag desliga a tradução só pros docker compose calls. Se você está numa branch antiga sem esse fix, prefixe manualmente: `MSYS_NO_PATHCONV=1 make seed-users-docker`.

### `winget install` requer admin mesmo com `--scope user`
Algumas versões antigas do winget têm bug que ignora `--scope user`. Atualize:
```powershell
winget upgrade --id Microsoft.AppInstaller
```

### `uv sync` falha com erro de SSL/cert
Em redes corporativas com proxy/MITM, configure `SSL_CERT_FILE` apontando para o cert da empresa. Como último recurso:
```powershell
$env:UV_INSECURE_HOST = "pypi.org"
```

> [↑ Raiz do projeto](../../README.md)
