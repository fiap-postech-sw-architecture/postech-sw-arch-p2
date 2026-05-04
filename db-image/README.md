# db-image -- Imagens GHCR + compose standalone (fast check)

Pasta com (1) build context da imagem postgres seedada, (2) o
`docker-compose.yml` standalone que examinador da banca usa pra rodar a
stack completa em 1 comando, e (3) o tutorial QUICKSTART.

> **Pra examinador rodar a demo: ler [`QUICKSTART.md`](QUICKSTART.md)**.
> Este README cobre a OPERACAO da pipeline (build/push/prune).

## Conteudo

| Arquivo | Versionado? | Descricao |
|---|---|---|
| [`QUICKSTART.md`](QUICKSTART.md) | sim | Tutorial fast-check pra banca (5 min) |
| `docker-compose.yml` | sim | Compose standalone (puxa as 3 imagens do GHCR; sem build, sem source) |
| `Dockerfile` | sim | `FROM postgres:16` + dump + ARG/LABEL/ENV de versionamento |
| `99-version.sh` | sim | Script de initdb que loga a SHA na primeira inicializacao do postgres |
| `00-init.sql` | **nao** (gitignored) | Dump gerado por `make ghcr-dump` (artefato de build) |

## Imagens publicadas (GHCR, privadas)

`make update-ghcr` publica 3 packages, com 1 versao cada (prune deleta
historico a cada update):

| Package | Tags | Conteudo |
|---|---|---|
| `ghcr.io/jbamaral/postech-sw-arch-p1-db` | `seeded`, `latest` | postgres:16 + dump da DB seedada (7 clientes, 10 veiculos, 8 OS, etc.) |
| `ghcr.io/jbamaral/postech-sw-arch-p1-app` | `latest` | FastAPI backend |
| `ghcr.io/jbamaral/postech-sw-arch-p1-ui` | `latest` | NiceGUI sandbox |

Todas embutem SHA do commit como `LABEL org.opencontainers.image.revision`
(OCI standard) + `ENV PYTSTOP_GIT_SHA` + log no startup. Ver
[QUICKSTART.md](QUICKSTART.md) pra exemplos de leitura.

## Pre-requisitos pra rodar `update-ghcr`

| Requisito | Como configurar |
|---|---|
| `docker` (engine + buildx) | parte do setup base do projeto |
| `make reset-db` funcionando | `update-ghcr` reusa o seed via reset-db |
| `docker login ghcr.io` com **`write:packages`** | PAT classic com `write:packages` (NAO o de leitura usado no fast-check). `echo $TOKEN \| docker login ghcr.io -u <user> --password-stdin` |
| `gh` CLI com **`read:packages,delete:packages`** | `gh auth refresh -s read:packages,delete:packages` (adiciona escopos ao login existente sem precisar relogar). Verifique com `gh auth status` |
| `jq` no PATH | macOS: `brew install jq`; Linux: `apt install jq`; Windows: `winget install jqlang.jq` ou `choco install jq` (no Git Bash, ambos resolvem o binario no PATH) |

## Comandos make

Todos rodados a partir da raiz do repo.

| Target | O que faz |
|---|---|
| `make ghcr-dump` | `pg_dump` da DB rodando -> `db-image/00-init.sql` |
| `make ghcr-build` | `docker build` das **3 imagens** com SHA injetada como build args. `--provenance=false --sbom=false` garante que cada push vire 1 versao no GHCR |
| `make ghcr-push` | `docker push` das 4 tags (db:seeded + db:latest + app:latest + ui:latest) |
| `make ghcr-prune` | Apaga via `gh api` versoes "untagged" dos **3 packages** (mantem so a tagueada corrente em cada) |
| `make update-ghcr` | Pipeline completo: rotaciona `ENCRYPTION_KEY` -> `reset-db` -> `ghcr-build` -> `ghcr-push` -> `ghcr-prune` -> patcha nova key em `db-image/docker-compose.yml`. **Destrutivo** (dropa volume `postgres_data`). Veja secao "Pos-condicoes do `update-ghcr`" abaixo |

## Pos-condicoes do `update-ghcr`

Apos o pipeline rodar com sucesso, dois efeitos colaterais que precisam de acao manual:

1. **`db-image/docker-compose.yml` foi modificado** com a `ENCRYPTION_KEY` rotacionada que cifra o snapshot recem-publicado. **Sem committar essa mudanca, qualquer um que clonar o repo nao vai conseguir abrir os CPF/CNPJ do dump** (decryption error). O target imprime no fim os comandos exatos pra commitar.

2. **`.env.dev` local volta pra `OLD_KEY`** (via `trap` na saida) -- mas a DB local ficou seedada com `NEW_KEY`. Resultado: listar clientes localmente vai falhar ate voce rodar `make reset-db` (reseed com `OLD_KEY`).

Por que rotacionar a key a cada publicacao: a key cifra CPF/CNPJ no dump seedado e fica committada em texto plano em `db-image/docker-compose.yml` (dados sao sinteticos, sem PII real). Rotacionar garante que (a) a key publica so vale pro snapshot atual, (b) leak da key historica nao decifra snapshots novos, e (c) o `.env.dev` local fica com key DIFERENTE da publicada, evitando reuso acidental do valor publico em ambiente nao-demo.

## Versionamento (auto-gerado, nunca commitado)

A SHA do `HEAD` e injetada em todo build (local OU GHCR) via:

1. **Makefile** computa `GIT_SHA := $(shell git rev-parse HEAD)` no parse,
   exporta pra `DOCKER_COMPOSE` wrapper como env var.
2. **`docker-compose.yml`** (local) e **build args dos targets GHCR**
   passam `GIT_SHA`/`GIT_DATE` pros Dockerfiles.
3. **Cada Dockerfile** declara `ARG GIT_SHA=unknown` (fallback se rodado
   sem make), gera `LABEL org.opencontainers.image.revision=${GIT_SHA}`
   + `ENV PYTSTOP_GIT_SHA=${GIT_SHA}`.
4. **Cada servico** loga no startup -- entrypoint do app (`entrypoint.sh`),
   wrapper-CMD da ui (`bash -c "echo ... && exec python -m ui"`),
   wrapper-entrypoint do postgres (compose) ou initdb-script da imagem
   seedada (`99-version.sh`), e o lifespan do FastAPI (`src/main.py`).

A SHA so reflete o `HEAD` commitado -- mudancas no working tree nao
aparecem como `-dirty`. Comite antes de rodar `update-ghcr` se quiser que
a SHA reflita o estado real.

## Customizacao

Variaveis sobrescritiveis na linha de comando. Defaults: `GHCR_REGISTRY=ghcr.io`, `GHCR_USER=jbamaral`, `GHCR_PREFIX=postech-sw-arch-p1` (gera `<prefix>-db`, `<prefix>-app`, `<prefix>-ui`).

```bash
make update-ghcr GHCR_USER=fork-user GHCR_PREFIX=postech-sw-arch-p1
```

Em forks, sobrescrever `GHCR_USER` e fazer `docker login` / `gh auth refresh` com o usuario do fork. O `ghcr-prune` valida que `gh` esta autenticado como `GHCR_USER` antes de rodar -- se divergir, falha rapido com mensagem.

## Por que `--provenance=false --sbom=false`?

Por default o buildx publica 3 manifests por push (image manifest +
attestation manifest + SBOM manifest), e dois deles ficam "untagged" no
GHCR mesmo sendo referenciados pela tag corrente. Se o `ghcr-prune`
deletar versoes untagged, ele quebra essas referencias e torna a tag
inutilizavel.

Desligar attestations faz cada push virar **uma unica versao** no GHCR,
permitindo que o prune simples (delete tudo que esta untagged) seja
seguro. Trade-off: imagem nao vem com SLSA provenance attestation -- ok
pra esta finalidade (demo/snapshot interno), nao recomendado pra
distribuicao publica de imagens em producao.
