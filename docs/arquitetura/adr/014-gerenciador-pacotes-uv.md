# Gerenciador de pacotes e ambientes virtuais com uv

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-04-19 (proposta) / 2026-04-29 (aceita)

## Contexto e Problema

O projeto hoje declara dependências em `pyproject.toml` (PEP 621, build-backend `setuptools`) e o fluxo documentado no README e CI usa `python -m venv .venv`, `pip install -e ".[test]"` e `pytest`. Não existe lockfile commitado, de modo que duas instalações do projeto (em máquinas distintas ou em execuções distintas do CI) podem resolver versões transitivas diferentes das mesmas restrições em `pyproject.toml`.

A PR #75 introduziu um arquivo `uv.lock` (gerado por `uv lock`) e alterou o trecho de Desenvolvimento Local do README para usar `uv sync --extra test`. Essa mudança funciona localmente, mas impacta onboarding, CI, Dockerfile, Makefile e a política de atualização de dependências.

**Qual ferramenta devemos adotar como gerenciador oficial de dependências e ambientes virtuais do projeto?**

## Decisão

Adotar **uv** como gerenciador oficial de dependências e ambientes virtuais do projeto. O `uv.lock` é fonte canônica de versões resolvidas; `uv sync --extra test --frozen` é o comando de instalação padrão para dev e CI.

Esta seção foi consolidada em 2026-04-29 após uso na prática: o Quick Start, os [guias de setup por plataforma](../../setup/), o [`docs/desenvolvimento.md`](../../desenvolvimento.md), o `Makefile` e o `Dockerfile` já consomem `uv sync` e `uv run`. As alternativas listadas abaixo permanecem documentadas como histórico das opções consideradas; o fallback `python -m venv` + `pip install` continua suportado apenas como contingência para ambientes onde `uv` não está disponível.

Critérios sugeridos para a discussão:

* **Reprodutibilidade**: lockfile com hashes de pacotes (SHA-256), compatível com `--frozen`/`--check` em CI.
* **Onboarding**: facilidade de instalação da própria ferramenta (curl, brew, pipx, apt) e comandos de uso rotineiro (instalar, atualizar, rodar).
* **Integração com CI e Docker**: action oficial, cache de resolução, imagens base prontas.
* **Compatibilidade com `pyproject.toml` PEP 621 existente**: evitar rewrite do `pyproject.toml` com extensões proprietárias.
* **Velocidade de resolução/instalação**: relevante para tempo de CI e iteração local.
* **Maturidade e saúde da comunidade**: manutenção ativa, licença, base instalada.
* **Custo de reversão**: facilidade de voltar atrás se a ferramenta for descontinuada ou apresentar problema.

## Alternativas Consideradas

* [`uv`](https://docs.astral.sh/uv/) (Astral)
* `python -m venv` + `pip install -e ".[test]"` (status quo)
* [`pip-tools`](https://github.com/jazzband/pip-tools) (`pip-compile` + `pip-sync`)
* [Poetry](https://python-poetry.org/)
* [PDM](https://pdm-project.org/)
* [Hatch](https://hatch.pypa.io/)

### uv (Astral)

Instalador e resolver escrito em Rust, integrando gerenciamento de ambiente virtual (`uv sync`), lockfile (`uv lock`), execução (`uv run`) e instalação do próprio Python (`uv python install`). Lê `pyproject.toml` PEP 621 sem alterações.

* Bom, porque mantém o `pyproject.toml` atual sem exigir seção proprietária (PEP 621 nativo)
* Bom, porque produz `uv.lock` com hashes SHA-256 por wheel, permitindo `uv sync --frozen` e `uv lock --check` em CI
* Bom, porque `uv sync` e `uv lock` são tipicamente 10x-100x mais rápidos que `pip install`/`pip-compile`
* Bom, porque [`astral-sh/setup-uv`](https://github.com/astral-sh/setup-uv) já oferece cache por chave de `uv.lock`
* Bom, porque a imagem `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` facilita a migração do Dockerfile
* Bom, porque `uv run <cmd>` elimina a necessidade de ativar o venv
* Ruim, porque adiciona um binário externo a instalar no onboarding (curl/brew/pipx)
* Ruim, porque é uma ferramenta jovem (1.0 em 2024), com algumas arestas em edge cases (e.g., monorepos, build backends customizados)
* Ruim, porque concentra mais responsabilidades na Astral (mesmo fornecedor do `ruff`), ampliando a superfície de single-vendor lock-in
* Ruim, porque ambientes de rede restrita (VPNs corporativas, laboratórios FIAP) podem bloquear `astral.sh`; é necessário fornecer instrução alternativa (pipx/apt)

### python -m venv + pip install (status quo)

Uso apenas de ferramentas da biblioteca padrão e do PyPA (`venv`, `pip`).

* Bom, porque vem com Python — zero ferramentas extras a instalar
* Bom, porque documentação universal, resposta pronta em qualquer ambiente
* Bom, porque é o denominador comum — qualquer alternativa precisa continuar aceitando este fluxo
* Ruim, porque **não gera lockfile** — `pip install` resolve versões transitivas a cada execução, produzindo dev/CI/prod drift silencioso
* Ruim, porque `pip install -e ".[test]"` não fornece garantia de hashes, abrindo espaço para supply-chain (mitigável com `--require-hashes` + `requirements.txt`, mas o projeto não usa)
* Ruim, porque é o caminho mais lento (resolução + download sequencial sem cache otimizado)

### pip-tools (pip-compile + pip-sync)

Duas ferramentas leves do PyPA para gerar `requirements.txt` a partir de `pyproject.toml` e sincronizar o venv.

* Bom, porque produz `requirements.txt` com hashes (`pip-compile --generate-hashes`)
* Bom, porque não introduz um novo formato de arquivo — `requirements.txt` é universalmente aceito
* Bom, porque permanece próximo ao `pip` padrão (curva de aprendizado baixa)
* Ruim, porque exige dois arquivos (`requirements.txt` + `requirements-test.txt`) para extras
* Ruim, porque não gerencia o Python em si, nem o venv
* Ruim, porque `pip-compile` é ordens de grandeza mais lento que `uv lock`
* Ruim, porque a manutenção é dirigida pela comunidade Jazzband (voluntários), sem time dedicado

### Poetry

Gerenciador historicamente popular com lockfile próprio (`poetry.lock`).

* Bom, porque maduro (2018), grande base instalada, bem documentado
* Bom, porque `poetry.lock` cobre hashes e resolução determinística
* Bom, porque `poetry run <cmd>` funciona como `uv run`
* Ruim, porque historicamente exige seção `[tool.poetry]` em `pyproject.toml` com schema proprietário (PEP 621 só ficou estável no Poetry 2.0 em 2025) — migração não-trivial
* Ruim, porque a resolução é relativamente lenta (dependency hell em projetos grandes)
* Ruim, porque histórico de breaking changes entre versões (1.0 → 1.2 → 1.5 → 2.0)
* Ruim, porque dois build-backends (setuptools no projeto, poetry-core se adotarmos) geraria inconsistência

### PDM

Gerenciador moderno, PEP 621 nativo, suporta PEP 582 (`__pypackages__`) além de venv.

* Bom, porque PEP 621 nativo (sem rewrite do `pyproject.toml`)
* Bom, porque `pdm.lock` com hashes
* Bom, porque mantém compatibilidade com múltiplos build-backends
* Ruim, porque base instalada menor que Poetry ou uv
* Ruim, porque velocidade inferior ao uv (resolver em Python)
* Ruim, porque a feature PEP 582 desvia de práticas tradicionais de venv e pode confundir contribuintes

### Hatch

Ferramenta oficial do PyPA, com foco em ambientes de teste/matriz e build.

* Bom, porque é mantido pelo PyPA (governança oficial)
* Bom, porque combina gerenciamento de ambientes, execução (`hatch run`) e build em uma única ferramenta
* Bom, porque PEP 621 nativo
* Ruim, porque a feature de lockfile (`hatch.lock`/PEP 751) ainda está em evolução
* Ruim, porque mais focado em bibliotecas (múltiplos ambientes de teste) do que em aplicações; simples `uv sync` equivalente é menos idiomático
* Ruim, porque adoção fora do ecossistema core Python ainda é limitada

## Consequências

A decisão final terá consequências diferentes para cada alternativa. Esta seção antecipa as consequências se o time escolher **uv**, já que essa é a alternativa pilotada pela PR #75. Se a escolha for outra, esta seção deve ser revisada.

### Positivas (caso uv seja aprovado)

* `uv.lock` com hashes estabelece reprodutibilidade bit-a-bit entre dev, CI e produção
* Tempo de CI reduzido (resolução + instalação mais rápidas)
* `uv run <cmd>` elimina o passo de ativação do venv, reduzindo fricção em scripts e documentação
* Atualização de dependências vira uma operação determinística (`uv lock --upgrade`) com diff revisável

### Negativas (caso uv seja aprovado)

* Contribuintes precisam instalar `uv` antes do primeiro `make check` — onboarding adicional
* Ambientes de rede restrita exigem fallback documentado (pip + venv)
* CI e Dockerfile precisam ser atualizados em PR separada para realmente consumir o `uv.lock` (caso contrário, dev e produção divergem)
* Aumenta o acoplamento com a Astral (mesmo fornecedor de `ruff`), concentrando risco de vendor

### Neutras

* `pyproject.toml` continua como fonte única de dependências declaradas, independente da ferramenta escolhida
* Fallback `python -m venv .venv && pip install -e ".[test]"` permanece funcional enquanto a ADR estiver em discussão

## Política de Atualização de Dependências (caso uv seja aprovado)

Esta seção documenta a operação diária esperada do lockfile, para evitar os dois antipadrões mais comuns: (a) nunca atualizar (acumular dívida de segurança) e (b) atualizar sem revisão (quebrar produto silenciosamente). O [README](../../../README.md#atualizando-dependencias) contém a tabela-referência de comandos; esta seção define **quando** e **quem** executa cada um.

### Cadência proposta

| Evento | Gatilho | Responsável | Comando básico |
|---|---|---|---|
| Lock refresh mensal | Início de cada mês ou sprint | Pessoa de platform/devops | `uv lock --upgrade && uv sync --extra test && make all` |
| Patch de segurança | CVE relevante, alerta do Dependabot/GHSA ou saída de `pip-audit` | Primeiro a detectar | `uv lock --upgrade-package <nome> && uv sync --extra test` |
| Bump de major/minor intencional | Decisão de produto (ex.: subir FastAPI, SQLAlchemy) | Autor da mudança | Editar range em `pyproject.toml`, depois `uv lock && uv sync --extra test` |
| Nova dependência | Necessidade de código | Autor da mudança | `uv add <pacote>` (ou `uv add --optional test <pacote>`) |
| Remoção de dependência | Código que usava foi deletado | Autor da mudança | `uv remove <pacote>` |

Cada tipo gera uma PR separada com `pyproject.toml` (quando mudou) e `uv.lock` commitados juntos e revisados lado a lado.

### Verificações obrigatórias antes do merge de um upgrade

1. `uv sync --extra test --frozen` a partir de um clone limpo — garante que o lockfile resolve sem mutação.
2. `make all` (format + check + integração) passando no CI com as novas versões.
3. `uv run --with pip-audit pip-audit` — sem CVEs de severidade alta ou crítica nas versões resolvidas.
4. Se o upgrade tocar FastAPI, Pydantic, SQLAlchemy ou pyjwt: smoke test E2E manual adicional (`pytest tests/e2e/`).

### Convenções de commit

* `chore(deps): monthly lock refresh` — refresh periódico que só bumpa transitivas dentro dos ranges.
* `chore(deps): bump <pacote> to <versao>` — upgrade de uma dependência direta.
* `fix(deps): patch <cve-id> via <pacote> <versao>` — patch de segurança urgente.
* `feat(deps): add <pacote> for <motivo>` — nova dependência.

### Rollback

Se um upgrade quebrar algo não capturado pelos testes, reverter o commit que tocou `uv.lock` restaura o estado anterior exato — o ponto da committagem do lockfile é justamente permitir isso com `git revert`. Para bumps maiores (editar `pyproject.toml` + lock), reverter o commit basta; para bumps só via `uv lock --upgrade`, também.

### Automação opcional (fora do escopo desta ADR)

Renovate ou Dependabot podem automatizar a PR do lock refresh mensal. Recomendação: configurar apenas **grouped updates** para transitivas (evita 30 PRs) e manter patches de segurança com PR individual para revisão humana.

## Decisões Relacionadas

- [ADR-011](011-pipeline-seguranca-analise-estatica.md): Pipeline de segurança e análise estática — a escolha do gerenciador impacta como `ruff`, `mypy`, `bandit` e `pip-audit` são invocados (direto vs `uv run` vs `poetry run`)
- [ADR-005](005-estrategia-testes.md): Estratégia de testes — `pytest` é invocado a partir do ambiente construído pela ferramenta escolhida

## Notas

* PR de referência: [#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/75)
* Se o time aprovar `uv`, uma PR de follow-up deve cobrir: (a) migração de `.github/workflows/ci.yml` para `astral-sh/setup-uv@v4` + `uv sync --frozen`; (b) migração do `Dockerfile` para imagem base uv ou `pip install --require-hashes` a partir de export do `uv.lock`; (c) prefixo `uv run` nos alvos do `Makefile`; (d) política de atualização do lockfile (cadência, PR automatizada).
* Documentação de referência: https://docs.astral.sh/uv/, https://peps.python.org/pep-0621/, https://github.com/astral-sh/setup-uv.

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

