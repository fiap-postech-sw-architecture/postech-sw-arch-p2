# Setup do zero -- Windows 11

Guia passo a passo para preparar uma maquina Windows do zero ate rodar o projeto. Todas as ferramentas sao instaladas via `winget` (gerenciador de pacotes oficial do Windows). Tempo estimado: 30-60 min com download da rede.

- **Fase 1** (~20 min): clone-ready -- PowerShell 7+, Git, GitHub CLI, Docker Desktop.
- **Fase 2** (~10 min): dev-ready -- uv, Python 3.12 (opcional, uv resolve), make.
- **Fase 3** (opcional): Selenium para testes E2E, ou WSL2 Ubuntu como alternativa.

> Stack do projeto: Python 3.12 - FastAPI - SQLAlchemy 2 - PostgreSQL 16 - Alembic - uv - Docker Compose v2 - pytest - ruff - mypy.

---

## Antes de comecar

### Abrindo um terminal como Administrador

Os pacotes da fase 1 instalam componentes de sistema (services, drivers WSL, PATH machine-wide), entao precisam de UAC:

1. Tecla Windows -> digita `powershell`
2. Botao direito em **Windows PowerShell** -> **Run as administrator**
3. Confirma o UAC

Use esse terminal admin para os passos da fase 1. Os pacotes da fase 2 (uv, make) instalam em **escopo de usuario** com `--scope user` -- nao precisam admin.

### Verificando winget

```powershell
winget --version
```

Esperado: `v1.28.x` ou superior. Se nao tiver, atualize **App Installer** pela Microsoft Store ou baixe em https://aka.ms/getwinget.

---

# Fase 1 -- clone-ready

## 1. PowerShell 7+

### Por que

Windows PowerShell 5.1 (embutido) e legado. PowerShell 7+ tem `&&`/`||`, ternarios, melhor compatibilidade com CLIs modernas e menos quirks de encoding. Coexiste com o 5.1; comando e `pwsh` em vez de `powershell`.

### Verificacao previa

```powershell
pwsh --version
```

Se retornar `PowerShell 7.x.x`, pula esta secao.

### Instalacao

PowerShell **admin**:

```powershell
winget install --id Microsoft.PowerShell --source winget --accept-source-agreements --accept-package-agreements
```

### Pos-instalacao

Feche o admin, abra um terminal novo (qualquer um) e use `pwsh`:

```powershell
pwsh --version
```

---

## 2. Git para Windows

### Por que

Sem Git, sem clone. O instalador "Git for Windows" tambem traz:

- **Git Bash** -- terminal estilo Unix com `bash`, `ls`, `grep`, `ssh`, etc. Necessario porque o `Makefile` deste projeto usa `bash -c '...'` em varias regras (nao roda em PowerShell).
- **Git Credential Manager (GCM)** -- guarda token do GitHub no Windows Credential Vault. E o que o `gh` usa para autenticar `git push`/`pull` sem te perguntar senha.

### Verificacao previa

```powershell
git --version
```

Se retornar `git version 2.4x.x.windows.x`, pula a instalacao -- mas confirme a config inicial abaixo.

### Instalacao

PowerShell **admin**:

```powershell
winget install --id Git.Git --source winget --accept-source-agreements --accept-package-agreements
```

Defaults aplicados (recomendados): branch inicial `main`, credential helper GCM, `core.autocrlf=true`. Se quiser controle fino, baixe o instalador interativo em https://git-scm.com/download/win.

### Pos-instalacao

Feche e reabra o terminal.

```powershell
git --version
```

### Configuracao inicial obrigatoria

Sem isso, git recusa criar commits. Em qualquer terminal:

```powershell
git config --global user.name "Seu Nome Completo"
git config --global user.email "seu@email.com"
```

Use o **mesmo email** da sua conta GitHub para que commits apareçam associados ao seu perfil.

### Configuracoes recomendadas

```powershell
git config --global init.defaultBranch main
git config --global credential.helper manager
git config --global pull.rebase true
git config --global color.ui auto
```

---

## 3. GitHub CLI (`gh`)

### Por que

Resolve autenticacao de uma vez (escreve token no GCM, entao `git clone https://...` funciona depois). Da comandos uteis para PRs, issues, runs de CI.

### Verificacao previa

```powershell
gh --version
```

Se retornar `gh version 2.x.x`, pula instalacao e va para autenticacao.

### Instalacao

PowerShell **admin** (suporta `--scope user` tambem, mas em admin garante PATH machine-wide):

```powershell
winget install --id GitHub.cli --source winget --accept-source-agreements --accept-package-agreements
```

### Pos-instalacao

Feche e reabra o terminal.

```powershell
gh --version
```

### Autenticacao

Terminal **normal** (nao precisa admin):

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

Mostra um codigo `ABCD-1234`. Copia, abre o navegador na URL exibida (`https://github.com/login/device`), cola o codigo, autoriza.

### Verificacao da auth

```powershell
gh auth status
gh repo view fiap-postech-sw-architecture/postech-sw-arch-p1 --json name,visibility
```

Se o `gh repo view` retornar JSON com o nome do repo, voce tem acesso.

> **Pre-requisito de acesso**: o repo e privado. Se voce nao foi adicionado como **collaborator** na organizacao `fiap-postech-sw-architecture`, o comando acima retorna 404 mesmo com `gh auth status` ok. Confira com algum mantenedor da equipe e peca o invite antes de prosseguir.

---

## 4. Docker Desktop

### Por que

O projeto roda em containers (Postgres + backend + UI). Docker Desktop e a forma mais comum no Windows.

### Verificacao previa

```powershell
docker --version
docker compose version
```

Se ambos responderem, pula a instalacao. Confirma tambem que o icone da baleia esta na bandeja (sem animacao = engine subiu).

### Pre-requisito: WSL 2

```powershell
wsl --status
```

Se nao tiver, em PowerShell admin:

```powershell
wsl --install
```

E reinicia.

### Instalacao

PowerShell **admin**:

```powershell
winget install --id Docker.DockerDesktop --source winget --accept-source-agreements --accept-package-agreements
```

### Pos-instalacao

1. **Reinicie a maquina** (Docker habilita componentes do Windows que exigem reboot).
2. Abre o **Docker Desktop** uma vez pelo menu Iniciar.
3. Aceita o EULA, escolhe "Use recommended settings".
4. Espera o icone da baleia ficar estavel na bandeja.

### Verificacao

```powershell
docker --version
docker compose version
docker run --rm hello-world
```

O ultimo comando baixa uma imagem minima e executa. Se imprimir "Hello from Docker!", esta funcionando.

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

> **Sem admin nesta fase**: `uv` e `make` instalam em escopo de usuario (`--scope user`). PowerShell normal serve.

## 5. uv (gerenciador de pacotes Python)

### Por que

uv e o gerenciador escolhido pelo projeto ([ADR-014](../arquitetura/adr/014-gerenciador-pacotes-uv.md)). Vantagens vs `pip + venv`:

- Lock file deterministico (`uv.lock`) com hashes SHA-256 -- resolucao reproduzivel entre maquinas e CI.
- Gerencia o proprio Python: `uv sync` baixa o Python 3.12 automaticamente se nao estiver no sistema. Voce nao precisa instalar Python 3.12 separadamente.
- 10-100x mais rapido que pip.
- `uv run <cmd>` executa no venv sem precisar `activate`.

### Verificacao previa

```powershell
uv --version
```

Se retornar `uv 0.x.x`, pula.

### Instalacao (sem admin)

```powershell
winget install --id astral-sh.uv --scope user --accept-source-agreements --accept-package-agreements
```

`--scope user` cai em `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*` e adiciona ao PATH do usuario. Sem UAC.

### Pos-instalacao

Feche e reabra qualquer terminal.

```powershell
uv --version
```

---

## 6. Python 3.12 (opcional)

### Por que talvez voce nao precise

`pyproject.toml` exige `requires-python = ">=3.12"`. Se voce ja instalou o `uv` (passo 5), `uv sync` baixa o Python 3.12 automaticamente em `%LOCALAPPDATA%\uv\python` -- voce nao precisa fazer nada manual. **Esta e a forma recomendada.**

Instale Python 3.12 do sistema **so se** quiser usar `python` direto (fora do `uv run ...`), ou se preferir nao delegar a versao para o uv.

### Verificacao via uv (recomendado)

Apos rodar `uv sync` no projeto:

```powershell
uv python list --only-installed
```

Deve listar uma instalacao 3.12 baixada pelo uv.

### Instalacao do sistema (opcional)

PowerShell admin:

```powershell
winget install --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements
```

Verifica:

```powershell
py -3.12 --version
```

O launcher `py` permite ter multiplas versoes -- `py -3.12`, `py -3.11`, etc.

---

## 7. make (com Git Bash)

### Por que

O `Makefile` e o caminho preferido para os comandos do dia a dia (`make up`, `make seed-demo`, `make reset-db`, `make check`, etc).

### O detalhe importante

O `Makefile` usa `bash -c '...'`, `source script.sh`, `command -v`, `printf` -- sintaxe POSIX/bash, **nao PowerShell**. Voce **nao roda `make` no PowerShell**, e sim no **Git Bash** (instalado junto com o Git for Windows na fase 1).

### Verificacao previa

Abra o **Git Bash** (no menu Iniciar, "Git Bash"):

```bash
make --version
```

Se retornar `GNU Make 4.x`, pula.

### Instalacao (sem admin)

PowerShell normal:

```powershell
winget install --id ezwinports.make --scope user --accept-source-agreements --accept-package-agreements
```

User-scope cai em `%LOCALAPPDATA%\Microsoft\WinGet\Packages\ezwinports.make_*\bin\` e e adicionado ao PATH do usuario, acessivel tanto em PowerShell quanto Git Bash.

### Pos-instalacao

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

Os testes em `tests/unitarios/ui/componentes/` usam a fixture `screen` da NiceGUI, que sobe Chrome headless e navega na UI. Sao marcados `@pytest.mark.lento`. Por padrao `make test` e `make check` excluem (`-m "not lento"`), entao voce nao precisa de Selenium para o fluxo normal de dev.

Vale instalar se: quer rodar suite completa local (`make test-lento`), esta mexendo em paginas/componentes da UI, ou quer reproduzir falha E2E do CI.

### Pre-requisito: Chrome

Tem 99% de chance de ja estar instalado. Senao:

```powershell
winget install --id Google.Chrome --scope user --accept-source-agreements --accept-package-agreements
```

### O que **nao** precisa instalar

**chromedriver** -- Selenium 4.6+ traz o **Selenium Manager** embutido que baixa o chromedriver compativel com sua versao do Chrome automaticamente, na primeira execucao. Sem PATH manual.

### Instalar `selenium` no projeto

No Git Bash, dentro do repo:

```bash
uv pip install selenium
```

Instala no `.venv` do projeto sem tocar `pyproject.toml`/`uv.lock` (decisao consciente do projeto: extras leves por padrao).

### Verificacao

```bash
uv run python -c "import selenium; print(selenium.__version__)"
```

### Rodar os testes lentos

```bash
uv run pytest tests/unitarios/ui/componentes/ -m lento -v --no-lint
```

Primeira execucao baixa o chromedriver (segundos). Cache em `%USERPROFILE%\.cache\selenium\`.

---

## 9. WSL2 Ubuntu (alternativa ao caminho Windows nativo)

### Quando considerar

Se voce for desenvolver Python intensivamente, vale instalar uma distro Linux real no WSL2:

- README, scripts e Makefile sao escritos pensando em Unix -- zero atrito.
- Performance de I/O melhor para `uv sync`, pytest, etc (desde que o codigo esteja **dentro** do filesystem do WSL, ex.: `~/projetos/`, **nao** em `/mnt/c/`).
- Docker Desktop integra com WSL2 -- `docker` funciona dentro da distro sem instalar nada extra.

### Quando pular

Se prefere ficar no Windows nativo, o caminho native (Git Bash + make + uv) funciona perfeitamente. Pula esta secao.

### Verificacao previa

```powershell
wsl --list --verbose
```

Se listar `Ubuntu` (ou outra distro alem de `docker-desktop`), pula a instalacao.

### Instalacao

PowerShell admin:

```powershell
wsl --install -d Ubuntu
```

Apos o reboot, o Ubuntu abre uma janela pedindo username e senha (independente da sua conta Windows).

### Setup dentro do Ubuntu

Veja o guia [Linux](linux.md) -- as mesmas instrucoes valem dentro do WSL.

> Se voce usar WSL **e** Windows nativo, voce vai ter **duas instalacoes** (gh/git/uv) e duas autenticacoes. Escolha qual e sua "casa" e fica nela.

---

# Subindo o projeto

## Antes do primeiro `make`: garantir `make` e `uv` no PATH do Git Bash

Pacotes instalados via `winget --scope user` (caso de `uv` e `ezwinports.make` na fase 2) entram no Windows User PATH, **mas o MSYS2 do Git Bash nao herda essas entradas no startup com confiabilidade**. Resultado: `bash: make: command not found` mesmo com o pacote instalado e sessao reaberta. A solucao padrao e adicionar os dois caminhos ao `~/.bashrc` -- uma vez so, vale para todas as sessoes futuras:

```bash
cat >> ~/.bashrc <<'EOF'

# Pacotes user-scope do winget que o MSYS2 nao herda no startup do Git Bash.
# Cobre 'make' (ezwinports.make) e 'uv' (astral-sh.uv).
export PATH="$HOME/AppData/Local/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$HOME/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"
EOF
source ~/.bashrc
which make uv
```

Esperado: dois paths sob `WinGet/Packages/`. Se o nome do pacote tiver versao no diretorio (winget atualizou), ajuste copiando o caminho exato de `ls "$HOME/AppData/Local/Microsoft/WinGet/Packages"`.

> Se voce ja tem `make` e `uv` no PATH (instalados de outra forma, por exemplo brew/scoop), pula este passo. Confere com `which make uv` antes.

## Comandos do dia a dia

Com a fase 1 e fase 2 prontas, no **Git Bash** dentro do diretorio do repo:

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

# Troubleshooting -- especifico do Windows

### `winget` nao e reconhecido
Atualize o App Installer pela Microsoft Store, ou baixe em https://aka.ms/getwinget.

### `winget install` retorna "already installed"
Tudo certo, pula. Para forcar atualizacao:
```powershell
winget upgrade --id <pacote>
```

### `git`, `gh` nao reconhecidos depois de instalar
Feche **todos** os terminais (incluindo VS Code, IDEs) e abra um novo. PATH so recarrega em processos novos. Se persistir, confirme se o pacote esta no PATH:
```powershell
[System.Environment]::GetEnvironmentVariable('Path','User') -split ';' | Where-Object { $_ -like '*WinGet*' }
[System.Environment]::GetEnvironmentVariable('Path','Machine') -split ';' | Where-Object { $_ -like '*GitHub*' -or $_ -like '*Git*' }
```

### `make` ou `uv` nao reconhecidos no Git Bash mesmo apos reabrir
MSYS2 nao herda algumas entradas user-scope do winget no startup. Adicione ambos no `~/.bashrc` -- veja a secao [Antes do primeiro `make`](#antes-do-primeiro-make-garantir-make-e-uv-no-path-do-git-bash) acima.

### `git push`/`pull` pedindo senha o tempo todo
Git Credential Manager nao esta ativo:
```powershell
git config --global credential.helper manager
gh auth login   # regrava o token no GCM
```

### `gh auth login` nao abre o navegador
Copie a URL exibida no terminal e cole manualmente.

### `gh repo view` retorna 404
Voce nao foi adicionado como colaborador no repo, ou logou na conta errada. Confere com `gh auth status`.

### Docker Desktop trava em "Starting..."
Geralmente WSL 2 mal configurado. Em PowerShell admin:
```powershell
wsl --update
wsl --set-default-version 2
```
E reinicia.

### Politica de execucao do PowerShell bloqueando scripts
Se algum `.ps1` for bloqueado, em PowerShell admin:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### CRLF warnings no Git
Mensagens `warning: LF will be replaced by CRLF` sao normais com `core.autocrlf=true`. Pode ignorar.

### Scripts `.sh` reclamam de `\r: command not found`
Git for Windows converteu LF->CRLF nos scripts. Force LF:
```bash
git config core.autocrlf input
git rm --cached -r .
git reset --hard
```

### `make up` falha com "Nenhum socket Docker encontrado"
Apenas em commits antigos do projeto (anteriores a fix do `scripts/docker-check.sh` para Windows). Workaround:
```bash
echo 'export DOCKER_HOST="npipe:////./pipe/docker_engine"' >> ~/.bashrc
source ~/.bashrc
```

### `make seed-users-docker` ou `make reset-db` quebram com "No such file or directory" referenciando algo tipo `/app/C:/Users/...`
Era um bug conhecido quando o Makefile passava `/tmp/seed_usuarios.py` pro `docker compose exec`: MSYS2 (Git Bash) traduzia o `/tmp/...` pra um path Windows antes de chegar no docker.exe (binario nativo). O Makefile do projeto agora usa `MSYS_NO_PATHCONV=1` nesses comandos -- a flag desliga a traducao so pros docker compose calls. Se voce esta numa branch antiga sem esse fix, prefixe manualmente: `MSYS_NO_PATHCONV=1 make seed-users-docker`.

### `winget install` requer admin mesmo com `--scope user`
Algumas versoes antigas do winget tem bug que ignora `--scope user`. Atualize:
```powershell
winget upgrade --id Microsoft.AppInstaller
```

### `uv sync` falha com erro de SSL/cert
Em redes corporativas com proxy/MITM, configure `SSL_CERT_FILE` apontando para o cert da empresa. Como ultimo recurso:
```powershell
$env:UV_INSECURE_HOST = "pypi.org"
```
