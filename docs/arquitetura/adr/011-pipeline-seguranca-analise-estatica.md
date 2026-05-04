# Pipeline de Segurança e Análise Estática

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-29

## Contexto e Problema

O Tech Challenge exige segurança como requisito (RNF-010), incluindo análise estática automatizada e ferramentas OWASP para detecção precoce de vulnerabilidades. Como garantir que vulnerabilidades sejam detectadas antes de chegarem à produção?

## Decisão

Adotar pipeline de segurança em três camadas complementares:

**Camada 1 -- Pre-commit (local):**
- **ruff**: lint e formatação de código Python (substitui flake8, isort, black)
- **mypy** (modo strict): verificação estática de tipos para prevenir erros em runtime

**Camada 2 -- CI (GitHub Actions):**
- **bandit**: análise estática de segurança Python (SAST), detecta padrões inseguros como uso de `eval()`, `pickle`, SQL concatenado
- **pip-audit**: auditoria de dependências contra base de dados de CVEs conhecidas
- **gitleaks**: detecção de segredos (API keys, senhas, tokens) no histórico Git
- **trivy**: scan de vulnerabilidades na imagem Docker (OS packages, bibliotecas)

**Camada 3 -- Quality gate (PR):**
- **SonarQube**: métricas de qualidade, code smells, cobertura de testes e duplicação de código (quando disponível)

## Alternativas Consideradas

* Apenas ruff + mypy (lint e tipagem)
* Apenas SonarQube (análise abrangente)
* Pipeline completo em camadas (lint + SAST + dependências + segredos + imagem)

### Apenas ruff + mypy

Ferramentas de lint e verificação de tipos executadas localmente no pre-commit.

* Bom, porque é rápido e não impacta o tempo de CI
* Bom, porque detecta erros de tipo e estilo antes do commit
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
* Bom, porque pre-commit fornece feedback rápido ao desenvolvedor
* Bom, porque CI garante que nenhum código inseguro é mergeado
* Bom, porque atende ao RNF-010 de forma verificável
* Ruim, porque o pipeline de CI fica mais lento (~2-3 minutos adicionais)
* Ruim, porque requer manutenção de configurações de múltiplas ferramentas

## Consequências

### Positivas

* Detecção precoce de vulnerabilidades antes de chegarem à produção
* Atendimento verificável ao RNF-010 (segurança como requisito)
* Prevenção de segredos comitados no repositório (gitleaks)
* Auditoria contínua de dependências contra CVEs conhecidas (pip-audit)
* Imagem Docker verificada antes do deploy (trivy)

### Negativas

* Tempo de CI aumentado em ~2-3 minutos por execução
* Necessidade de manter configurações de bandit, gitleaks e trivy
* Falsos positivos podem bloquear PRs temporariamente (necessidade de triagem)

## Decisões Relacionadas

- [ADR-005](005-estrategia-testes.md): Estratégia de testes -- complementa a cobertura de qualidade
- [ADR-012](012-licenciamento-software-sbom.md): Licenciamento e SBOM -- pip-audit é parte da estratégia de cadeia de suprimentos

## Notas

- Referência: OWASP Testing Guide, Dev-Seguro Aulas 04 e 05
- RNF-010: o sistema deve possuir ferramentas de análise estática e auditoria de segurança

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
