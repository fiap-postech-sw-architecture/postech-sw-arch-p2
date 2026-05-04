# Troubleshooting -- runtime Docker

> [↑ Raiz do projeto](../../README.md)

Problemas comuns ao rodar o stack do projeto (`make up`, `docker compose up`).
Para troubleshooting de **install** (winget, brew, apt, gh auth, etc.), veja os
guias por plataforma: [macOS](macos.md) - [Linux](linux.md) - [Windows](windows.md).

---

## Docker socket não encontrado

Sintoma ao rodar `docker compose up -d` ou `make up`:

```
failed to connect to the docker API at unix:///Users/<user>/.docker/run/docker.sock
```

O `docker compose` não está encontrando o socket do Docker. O caminho
`~/.docker/run/docker.sock` é o padrão que o Docker configura no seu context,
mas ele nem sempre existe. As opções abaixo dependem do seu runtime.

### Opção 1 -- Docker Desktop: habilitar o socket padrão

O Docker Desktop (4.13+) só cria o socket em `~/.docker/run/` se uma opção
estiver habilitada. Abra **Docker Desktop > Settings > Advanced** e marque:

> **"Allow the default Docker socket to be used (requires password)"**

Reinicie o Docker Desktop e rode `docker compose up -d` novamente. Solução
mais simples -- não exige variável de ambiente nem alteração no projeto.

### Opção 2 -- Docker Desktop: apontar para o socket alternativo

Se preferir não habilitar a opção acima, o Docker Desktop sempre cria um
socket em `~/.docker/desktop/docker.sock`. Exporte `DOCKER_HOST` no `~/.zshrc`
(ou `~/.bashrc`):

```bash
export DOCKER_HOST="unix://${HOME}/.docker/desktop/docker.sock"
```

Execute `source ~/.zshrc` para aplicar no terminal atual.

### Opção 3 -- Colima

Se usa [Colima](https://github.com/abiosoft/colima) como runtime Docker em
vez do Docker Desktop, configure no `~/.zshrc`:

```bash
export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
export TESTCONTAINERS_RYUK_DISABLED=true
```

`DOCKER_HOST` é necessário para que `docker compose` e o testcontainers
encontrem o socket. `TESTCONTAINERS_RYUK_DISABLED` evita erros nos testes
de integração. Execute `source ~/.zshrc` ou abra um novo terminal.

### Opção 4 -- Linux

Verifique se o serviço Docker está ativo:

```bash
sudo systemctl start docker
sudo systemctl enable docker   # iniciar com a maquina
```

Se persistir `permission denied`, você não foi adicionado ao grupo `docker`:
veja o passo "Pos-instalacao -- adicionar usuario ao grupo docker" em
[linux.md](linux.md#pos-instalacao----adicionar-usuario-ao-grupo-docker).

---

## `docker compose` não reconhecido (Compose v2 ausente)

O Quick Start usa `docker compose` (Compose v2 como plugin do Docker CLI).
Se aparecer `unknown command: docker compose`, o plugin não está registrado.

### Docker via Homebrew (macOS) -- duas opções

**Opção A -- registrar o diretório de plugins do Homebrew** (mantém
`brew upgrade docker-compose`):

Adicione em `~/.docker/config.json` a chave `cliPluginsExtraDirs` com o
valor `["$(brew --prefix)/lib/docker/cli-plugins"]` usando o prefixo
retornado por `brew --prefix` (`/opt/homebrew` em Apple Silicon,
`/usr/local` em Intel; veja `brew info docker-compose`).

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

**Opção B -- copiar o plugin para o diretório padrão do usuário** (permite
`brew uninstall docker-compose` depois):

```bash
mkdir -p ~/.docker/cli-plugins
cp "$(brew --prefix docker-compose)/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
docker compose version   # confirma
brew uninstall docker-compose   # opcional, depois que o subcomando funcionar
```

Para atualizar o Compose na opção B, repita a cópia após
`brew install docker-compose` ou baixe o binário em
[releases do Compose](https://github.com/docker/compose/releases).

### Docker via apt (Linux)

Distros antigas instalam `docker-compose` (script Python, V1) em vez do
plugin V2. Este projeto exige V2 (`docker compose`, sem hífen). Desinstale
o V1 e instale o plugin:

```bash
sudo apt remove docker-compose
sudo apt install docker-compose-plugin
```

---

## Outros problemas operacionais

| Sintoma | Onde olhar |
|---|---|
| `/clientes` retorna 500 após restart (CPF/CNPJ inválido) | [`ui/README.md`](../../ui/README.md#clientes-retorna-500-apos-restart) |
| Imagem docker stale após `git pull` | [`ui/README.md`](../../ui/README.md#imagem-docker-stale-apos-git-pull) |
| Porta 8080 ocupada | [`ui/README.md`](../../ui/README.md#porta-8080-em-uso) |
| Hot-reload da UI não funciona | [`ui/README.md`](../../ui/README.md#hot-reload-da-ui-nao-funciona) |
| Testes de integração falham com Ryuk (Colima) | [`macos.md`](macos.md#troubleshooting----especifico-do-macos) |
| `port already in use` em 5432/8000/8080 | [`linux.md`](linux.md#troubleshooting----especifico-do-linux) e [`macos.md`](macos.md#troubleshooting----especifico-do-macos) |

Para troubleshooting amplo do dev loop (Colima, JWT_SECRET, 500s comuns,
verificação end-to-end), veja [`docs/debugging-guide.md`](../debugging-guide.md).

> [↑ Raiz do projeto](../../README.md)
