# Gerenciador de pacotes e ambientes virtuais com uv

* Status: Aceita
* Data: 2026-04-19 (proposta) / 2026-04-29 (aceita)

## Contexto e Problema

O projeto hoje declara dependencias em `pyproject.toml` (PEP 621, build-backend `setuptools`) e o fluxo documentado no README e CI usa `python -m venv .venv`, `pip install -e ".[test]"` e `pytest`. Nao existe lockfile commitado, de modo que duas instalacoes do projeto (em maquinas distintas ou em execucoes distintas do CI) podem resolver versoes transitivas diferentes das mesmas restricoes em `pyproject.toml`.

A PR #75 introduziu um arquivo `uv.lock` (gerado por `uv lock`) e alterou o trecho de Desenvolvimento Local do README para usar `uv sync --extra test`. Essa mudanca funciona localmente, mas impacta onboarding, CI, Dockerfile, Makefile e a politica de atualizacao de dependencias.

**Qual ferramenta devemos adotar como gerenciador oficial de dependencias e ambientes virtuais do projeto?**

## Decisão

Adotar **uv** como gerenciador oficial de dependencias e ambientes virtuais do projeto. O `uv.lock` e fonte canonica de versoes resolvidas; `uv sync --extra test --frozen` e o comando de instalacao padrao para dev e CI.

Esta secao foi consolidada em 2026-04-29 apos uso na pratica: o Quick Start, os [guias de setup por plataforma](../../setup/), o [`docs/desenvolvimento.md`](../../desenvolvimento.md), o `Makefile` e o `Dockerfile` ja consomem `uv sync` e `uv run`. As alternativas listadas abaixo permanecem documentadas como historico das opcoes consideradas; o fallback `python -m venv` + `pip install` continua suportado apenas como contingencia para ambientes onde `uv` nao esta disponivel.

Criterios sugeridos para a discussao:

* **Reprodutibilidade**: lockfile com hashes de pacotes (SHA-256), compativel com `--frozen`/`--check` em CI.
* **Onboarding**: facilidade de instalacao da propria ferramenta (curl, brew, pipx, apt) e comandos de uso rotineiro (instalar, atualizar, rodar).
* **Integracao com CI e Docker**: action oficial, cache de resolucao, imagens base prontas.
* **Compatibilidade com `pyproject.toml` PEP 621 existente**: evitar rewrite do `pyproject.toml` com extensoes proprietarias.
* **Velocidade de resolucao/instalacao**: relevante para tempo de CI e iteracao local.
* **Maturidade e saude da comunidade**: manutencao ativa, licenca, base instalada.
* **Custo de reversao**: facilidade de voltar atras se a ferramenta for descontinuada ou apresentar problema.

## Alternativas Consideradas

* [`uv`](https://docs.astral.sh/uv/) (Astral)
* `python -m venv` + `pip install -e ".[test]"` (status quo)
* [`pip-tools`](https://github.com/jazzband/pip-tools) (`pip-compile` + `pip-sync`)
* [Poetry](https://python-poetry.org/)
* [PDM](https://pdm-project.org/)
* [Hatch](https://hatch.pypa.io/)

### uv (Astral)

Instalador e resolver escrito em Rust, integrando gerenciamento de ambiente virtual (`uv sync`), lockfile (`uv lock`), execucao (`uv run`) e instalacao do proprio Python (`uv python install`). Le `pyproject.toml` PEP 621 sem alteracoes.

* Bom, porque mantem o `pyproject.toml` atual sem exigir secao proprietaria (PEP 621 nativo)
* Bom, porque produz `uv.lock` com hashes SHA-256 por wheel, permitindo `uv sync --frozen` e `uv lock --check` em CI
* Bom, porque `uv sync` e `uv lock` sao tipicamente 10x-100x mais rapidos que `pip install`/`pip-compile`
* Bom, porque [`astral-sh/setup-uv`](https://github.com/astral-sh/setup-uv) ja oferece cache por chave de `uv.lock`
* Bom, porque a imagem `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` facilita a migracao do Dockerfile
* Bom, porque `uv run <cmd>` elimina a necessidade de ativar o venv
* Ruim, porque adiciona um binario externo a instalar no onboarding (curl/brew/pipx)
* Ruim, porque e uma ferramenta jovem (1.0 em 2024), com algumas arestas em edge cases (e.g., monorepos, build backends customizados)
* Ruim, porque concentra mais responsabilidades na Astral (mesmo fornecedor do `ruff`), ampliando a superficie de single-vendor lock-in
* Ruim, porque ambientes de rede restrita (VPNs corporativas, laboratorios FIAP) podem bloquear `astral.sh`; e necessario fornecer instrucao alternativa (pipx/apt)

### python -m venv + pip install (status quo)

Uso apenas de ferramentas da biblioteca padrao e do PyPA (`venv`, `pip`).

* Bom, porque vem com Python — zero ferramentas extras a instalar
* Bom, porque documentacao universal, resposta pronta em qualquer ambiente
* Bom, porque e o denominador comum — qualquer alternativa precisa continuar aceitando este fluxo
* Ruim, porque **nao gera lockfile** — `pip install` resolve versoes transitivas a cada execucao, produzindo dev/CI/prod drift silencioso
* Ruim, porque `pip install -e ".[test]"` nao fornece garantia de hashes, abrindo espaco para supply-chain (mitigavel com `--require-hashes` + `requirements.txt`, mas o projeto nao usa)
* Ruim, porque e o caminho mais lento (resolucao + download sequencial sem cache otimizado)

### pip-tools (pip-compile + pip-sync)

Duas ferramentas leves do PyPA para gerar `requirements.txt` a partir de `pyproject.toml` e sincronizar o venv.

* Bom, porque produz `requirements.txt` com hashes (`pip-compile --generate-hashes`)
* Bom, porque nao introduz um novo formato de arquivo — `requirements.txt` e universalmente aceito
* Bom, porque permanece proximo ao `pip` padrao (curva de aprendizado baixa)
* Ruim, porque exige dois arquivos (`requirements.txt` + `requirements-test.txt`) para extras
* Ruim, porque nao gerencia o Python em si, nem o venv
* Ruim, porque `pip-compile` e ordens de grandeza mais lento que `uv lock`
* Ruim, porque a maintainance e dirigida pela comunidade Jazzband (voluntarios), sem time dedicado

### Poetry

Gerenciador historicamente popular com lockfile proprio (`poetry.lock`).

* Bom, porque maduro (2018), grande base instalada, bem documentado
* Bom, porque `poetry.lock` cobre hashes e resolucao deterministica
* Bom, porque `poetry run <cmd>` funciona como `uv run`
* Ruim, porque historicamente exige secao `[tool.poetry]` em `pyproject.toml` com schema proprietario (PEP 621 so ficou estavel no Poetry 2.0 em 2025) — migracao nao-trivial
* Ruim, porque resolver relativamente lento (dependency hell em projetos grandes)
* Ruim, porque historico de breaking changes entre versoes (1.0 → 1.2 → 1.5 → 2.0)
* Ruim, porque dois build-backends (setuptools no projeto, poetry-core se adotarmos) geraria inconsistencia

### PDM

Gerenciador moderno, PEP 621 nativo, suporta PEP 582 (`__pypackages__`) alem de venv.

* Bom, porque PEP 621 nativo (sem rewrite do `pyproject.toml`)
* Bom, porque `pdm.lock` com hashes
* Bom, porque mantem compatibilidade com multiplos build-backends
* Ruim, porque base instalada menor que Poetry ou uv
* Ruim, porque velocidade inferior ao uv (resolver em Python)
* Ruim, porque a feature PEP 582 desvia de practicas tradicionais de venv e pode confundir contribuintes

### Hatch

Ferramenta oficial do PyPA, com foco em ambientes de teste/matriz e build.

* Bom, porque e mantido pelo PyPA (governanca oficial)
* Bom, porque combina gerenciamento de ambientes, execucao (`hatch run`) e build em uma unica ferramenta
* Bom, porque PEP 621 nativo
* Ruim, porque a feature de lockfile (`hatch.lock`/PEP 751) ainda esta em evolucao
* Ruim, porque mais focado em bibliotecas (multiplos ambientes de teste) do que em aplicacoes; simples `uv sync` equivalente e menos idiomatico
* Ruim, porque adocao fora do ecossistema core Python ainda e limitada

## Consequências

A decisao final tera consequencias diferentes para cada alternativa. Esta secao antecipa as consequencias se o time escolher **uv**, ja que essa e a alternativa pilotada pela PR #75. Se a escolha for outra, esta secao deve ser revisada.

### Positivas (caso uv seja aprovado)

* `uv.lock` com hashes estabelece reprodutibilidade bit-a-bit entre dev, CI e producao
* Tempo de CI reduzido (resolucao + instalacao mais rapidas)
* `uv run <cmd>` elimina o passo de ativacao do venv, reduzindo friccao em scripts e documentacao
* Atualizacao de dependencias vira uma operacao deterministica (`uv lock --upgrade`) com diff revisavel

### Negativas (caso uv seja aprovado)

* Contribuintes precisam instalar `uv` antes do primeiro `make check` — onboarding adicional
* Ambientes de rede restrita exigem fallback documentado (pip + venv)
* CI e Dockerfile precisam ser atualizados em PR separada para realmente consumir o `uv.lock` (caso contrario, dev e producao divergem)
* Aumenta o acoplamento com a Astral (mesmo fornecedor de `ruff`), concentrando risco de vendor

### Neutras

* `pyproject.toml` continua como fonte unica de dependencias declaradas, independente da ferramenta escolhida
* Fallback `python -m venv .venv && pip install -e ".[test]"` permanece funcional enquanto a ADR estiver em discussao

## Politica de Atualizacao de Dependencias (caso uv seja aprovado)

Esta secao documenta a operacao diaria esperada do lockfile, para evitar os dois anti-padroes mais comuns: (a) nunca atualizar (acumular divida de seguranca) e (b) atualizar sem revisao (quebrar produto silenciosamente). O [README](../../../README.md#atualizando-dependencias) contem a tabela-referencia de comandos; esta secao define **quando** e **quem** executa cada um.

### Cadencia proposta

| Evento | Gatilho | Responsavel | Comando basico |
|---|---|---|---|
| Lock refresh mensal | Inicio de cada mes ou sprint | Pessoa de platform/devops | `uv lock --upgrade && uv sync --extra test && make all` |
| Patch de seguranca | CVE relevante, alerta do Dependabot/GHSA ou saida de `pip-audit` | Primeiro a detectar | `uv lock --upgrade-package <nome> && uv sync --extra test` |
| Bump de major/minor intencional | Decisao de produto (ex.: subir FastAPI, SQLAlchemy) | Autor da mudanca | Editar range em `pyproject.toml`, depois `uv lock && uv sync --extra test` |
| Nova dependencia | Necessidade de codigo | Autor da mudanca | `uv add <pacote>` (ou `uv add --optional test <pacote>`) |
| Remocao de dependencia | Codigo que usava foi deletado | Autor da mudanca | `uv remove <pacote>` |

Cada tipo gera uma PR separada com `pyproject.toml` (quando mudou) e `uv.lock` commitados juntos e revisados lado a lado.

### Verificacoes obrigatorias antes do merge de um upgrade

1. `uv sync --extra test --frozen` a partir de um clone limpo — garante que o lockfile resolve sem mutacao.
2. `make all` (format + check + integracao) passando no CI com as novas versoes.
3. `uv run --with pip-audit pip-audit` — sem CVEs de severidade alta ou critica nas versoes resolvidas.
4. Se o upgrade tocar FastAPI, Pydantic, SQLAlchemy ou pyjwt: smoke test E2E manual adicional (`pytest tests/e2e/`).

### Convencoes de commit

* `chore(deps): monthly lock refresh` — refresh periodico que so bumpa transitivas dentro dos ranges.
* `chore(deps): bump <pacote> to <versao>` — upgrade de uma dependencia direta.
* `fix(deps): patch <cve-id> via <pacote> <versao>` — patch de seguranca urgente.
* `feat(deps): add <pacote> for <motivo>` — nova dependencia.

### Rollback

Se um upgrade quebrar algo nao capturado pelos testes, reverter o commit que tocou `uv.lock` restaura o estado anterior exato — o ponto da committagem do lockfile e justamente permitir isso com `git revert`. Para bumps maiores (editar `pyproject.toml` + lock), reverter o commit basta; para bumps so via `uv lock --upgrade`, tambem.

### Automacao opcional (fora do escopo desta ADR)

Renovate ou Dependabot podem automatizar a PR do lock refresh mensal. Recomendacao: configurar apenas **grouped updates** para transitivas (evita 30 PRs) e manter patches de seguranca com PR individual para revisao humana.

## Decisões Relacionadas

- [ADR-011](011-pipeline-seguranca-analise-estatica.md): Pipeline de seguranca e analise estatica — a escolha do gerenciador impacta como `ruff`, `mypy`, `bandit` e `pip-audit` sao invocados (direto vs `uv run` vs `poetry run`)
- [ADR-005](005-estrategia-testes.md): Estrategia de testes — `pytest` e invocado a partir do ambiente construido pela ferramenta escolhida

## Notas

* PR de referencia: [#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/75)
* Se o time aprovar `uv`, uma PR de follow-up deve cobrir: (a) migracao de `.github/workflows/ci.yml` para `astral-sh/setup-uv@v4` + `uv sync --frozen`; (b) migracao do `Dockerfile` para imagem base uv ou `pip install --require-hashes` a partir de export do `uv.lock`; (c) prefixo `uv run` nos alvos do `Makefile`; (d) politica de atualizacao do lockfile (cadencia, PR automatizada).
* Documentacao de referencia: https://docs.astral.sh/uv/, https://peps.python.org/pep-0621/, https://github.com/astral-sh/setup-uv.

