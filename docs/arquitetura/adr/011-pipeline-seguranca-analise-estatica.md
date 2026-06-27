# Pipeline de Segurança e Análise Estática

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-29

## Contexto e Problema

O Tech Challenge exige segurança como requisito (RNF-010), incluindo análise estática automatizada e ferramentas OWASP para detecção precoce de vulnerabilidades. Como garantir que vulnerabilidades sejam detectadas antes de chegarem à produção?

## Decisão

Adotar pipeline de segurança em três camadas complementares, distinguindo o que roda automaticamente no CI dos scans executados localmente como evidência de fechamento:

**Camada 1 -- Lint e tipagem (CI + `make check` local):**
- **ruff**: lint e formatação de código Python (substitui flake8, isort, black). Roda no CI (`ruff check`/`ruff format --check`) e via `make format`/`make check`
- **mypy** (modo strict): verificação estática de tipos para prevenir erros em runtime. Roda no CI e via `make typecheck`
- **import-linter** (`lint-imports`): contratos de dependência entre camadas (proíbe domínio → infraestrutura). Roda no CI e via `make lint-arch`

**Camada 2 -- Segurança automatizada no CI (GitHub Actions, `.github/workflows/ci.yml`):**
- **bandit**: análise estática de segurança Python (SAST), detecta padrões inseguros como uso de `eval()`, `pickle`, SQL concatenado — job dedicado no CI (`--severity-level high`)
- **SBOM CycloneDX** (`make sbom`): inventário de dependências da cadeia de suprimentos, publicado como artefato (ver [ADR-012](012-licenciamento-software-sbom.md))
- **CodeQL** (`make codeql-quality`, `.github/codeql/codeql-config.yml`, `scripts/codeql_quality.sh`): análise semântica de qualidade/segurança. Por ser pesado, é executado sob demanda (localmente ou em job manual), não em todo push

**Camada 3 -- Scans manuais de fechamento (locais, evidência em `docs/seguranca/`):**
- **pip-audit**: auditoria de dependências contra a base de CVEs conhecidas
- **gitleaks**: detecção de segredos (API keys, senhas, tokens) no working tree e no histórico Git
- **trivy**: scan de vulnerabilidades de filesystem e da imagem Docker (OS packages, bibliotecas)
- **OWASP ZAP** (baseline): varredura dinâmica de superfície HTTP

Esses scans rodam manualmente nas janelas de fechamento de fase e seus relatórios ficam versionados em `docs/seguranca/` — não são gates de PR. A integração de um quality gate centralizado (SonarQube) fica como evolução: existe `sonar-project.properties`, mas o scanner ainda não está acionado em CI.

## Alternativas Consideradas

* Apenas ruff + mypy (lint e tipagem)
* Apenas SonarQube (análise abrangente)
* Pipeline completo em camadas (lint + SAST + dependências + segredos + imagem)

### Apenas ruff + mypy

Ferramentas de lint e verificação de tipos executadas via `make check` local e no CI.

* Bom, porque é rápido e dá feedback de estilo e tipos cedo
* Bom, porque detecta erros de tipo e estilo antes do merge
* Ruim, porque não detecta vulnerabilidades de segurança (padrões inseguros, CVEs)
* Ruim, porque não detecta segredos no histórico Git
* Ruim, porque não verifica vulnerabilidades na imagem Docker

### Apenas SonarQube

Análise estática centralizada via SonarQube no pipeline CI.

* Bom, porque oferece visão unificada de qualidade, segurança e cobertura
* Bom, porque possui dashboard com histórico de métricas
* Ruim, porque não detecta segredos no histórico Git (fora do escopo do SonarQube)
* Ruim, porque não audita vulnerabilidades em dependências Python (CVEs)
* Ruim, porque não verifica a imagem Docker
* Ruim, porque requer infraestrutura adicional (servidor SonarQube)

### Pipeline completo em camadas (escolhido)

Ferramentas especializadas cobrindo lint, SAST, dependências, segredos e imagem Docker.

* Bom, porque cada ferramenta cobre uma superfície de ataque distinta
* Bom, porque `make check` local fornece feedback rápido ao desenvolvedor antes do push
* Bom, porque o CI (bandit + import-linter) garante que nenhum código inseguro é mergeado
* Bom, porque atende ao RNF-010 de forma verificável
* Ruim, porque o pipeline de CI fica mais lento (~2-3 minutos adicionais)
* Ruim, porque requer manutenção de configurações de múltiplas ferramentas

## Consequências

### Positivas

* Detecção precoce de vulnerabilidades: bandit e import-linter rodam em todo push, barrando código inseguro antes do merge
* Atendimento verificável ao RNF-010 (segurança como requisito), com evidências versionadas em `docs/seguranca/`
* SBOM CycloneDX gerado e publicado como artefato a cada execução do CI (cadeia de suprimentos)
* Detecção de segredos (gitleaks), auditoria de dependências (pip-audit) e scan de imagem/filesystem (trivy) cobertos pelos scans manuais de fechamento, com relatórios arquivados
* CodeQL disponível para análise semântica aprofundada quando necessário

### Negativas

* Tempo de CI aumentado por bandit e SBOM (~1-2 minutos por execução)
* Necessidade de manter configurações de bandit, CodeQL e dos scanners manuais (gitleaks, pip-audit, trivy, ZAP)
* Scans manuais dependem de disciplina de processo: por não serem gates de PR, exigem que sejam efetivamente executados nas janelas de fechamento
* Falsos positivos do bandit podem bloquear PRs temporariamente (necessidade de triagem)

## Decisões Relacionadas

- [ADR-005](005-estrategia-testes.md): Estratégia de testes -- complementa a cobertura de qualidade
- [ADR-012](012-licenciamento-software-sbom.md): Licenciamento e SBOM -- pip-audit é parte da estratégia de cadeia de suprimentos

## Notas

- Referência: OWASP Testing Guide, Dev-Seguro Aulas 04 e 05
- RNF-010: o sistema deve possuir ferramentas de análise estática e auditoria de segurança

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
