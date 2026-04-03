# Pipeline de Seguranca e Analise Estatica

* Status: Aceita
* Data: 2026-03-29

## Contexto e Problema

O Tech Challenge exige seguranca como requisito (RNF-010), incluindo analise estatica automatizada e ferramentas OWASP para deteccao precoce de vulnerabilidades. Como garantir que vulnerabilidades sejam detectadas antes de chegarem a producao?

## Decisao

Adotar pipeline de seguranca em tres camadas complementares:

**Camada 1 -- Pre-commit (local):**
- **ruff**: lint e formatacao de codigo Python (substitui flake8, isort, black)
- **mypy** (modo strict): verificacao estatica de tipos para prevenir erros em runtime

**Camada 2 -- CI (GitHub Actions):**
- **bandit**: analise estatica de seguranca Python (SAST), detecta padroes inseguros como uso de `eval()`, `pickle`, SQL concatenado
- **pip-audit**: auditoria de dependencias contra base de dados de CVEs conhecidas
- **gitleaks**: deteccao de segredos (API keys, senhas, tokens) no historico Git
- **trivy**: scan de vulnerabilidades na imagem Docker (OS packages, bibliotecas)

**Camada 3 -- Quality gate (PR):**
- **SonarQube**: metricas de qualidade, code smells, cobertura de testes e duplicacao de codigo (quando disponivel)

## Alternativas Consideradas

* Apenas ruff + mypy (lint e tipagem)
* Apenas SonarQube (analise abrangente)
* Pipeline completo em camadas (lint + SAST + dependencias + segredos + imagem)

### Apenas ruff + mypy

Ferramentas de lint e verificacao de tipos executadas localmente no pre-commit.

* Bom, porque e rapido e nao impacta o tempo de CI
* Bom, porque detecta erros de tipo e estilo antes do commit
* Ruim, porque nao detecta vulnerabilidades de seguranca (padroes inseguros, CVEs)
* Ruim, porque nao detecta segredos no historico Git
* Ruim, porque nao verifica vulnerabilidades na imagem Docker

### Apenas SonarQube

Analise estatica centralizada via SonarQube no pipeline CI.

* Bom, porque oferece visao unificada de qualidade, seguranca e cobertura
* Bom, porque possui dashboard com historico de metricas
* Ruim, porque nao detecta segredos no historico Git (fora do escopo do SonarQube)
* Ruim, porque nao audita vulnerabilidades em dependencias Python (CVEs)
* Ruim, porque nao verifica a imagem Docker
* Ruim, porque requer infraestrutura adicional (servidor SonarQube)

### Pipeline completo em camadas (escolhido)

Ferramentas especializadas cobrindo lint, SAST, dependencias, segredos e imagem Docker.

* Bom, porque cada ferramenta cobre uma superficie de ataque distinta
* Bom, porque pre-commit fornece feedback rapido ao desenvolvedor
* Bom, porque CI garante que nenhum codigo inseguro e mergeado
* Bom, porque atende ao RNF-010 de forma verificavel
* Ruim, porque o pipeline de CI fica mais lento (~2-3 minutos adicionais)
* Ruim, porque requer manutencao de configuracoes de multiplas ferramentas

## Consequencias

### Positivas

* Deteccao precoce de vulnerabilidades antes de chegarem a producao
* Atendimento verificavel ao RNF-010 (seguranca como requisito)
* Prevencao de segredos comitados no repositorio (gitleaks)
* Auditoria continua de dependencias contra CVEs conhecidas (pip-audit)
* Imagem Docker verificada antes do deploy (trivy)

### Negativas

* Tempo de CI aumentado em ~2-3 minutos por execucao
* Necessidade de manter configuracoes de bandit, gitleaks e trivy
* Falsos positivos podem bloquear PRs temporariamente (necessidade de triagem)

## Decisoes Relacionadas

- [ADR-005](005-estrategia-testes.md): Estrategia de testes -- complementa a cobertura de qualidade
- [ADR-012](012-licenciamento-software-sbom.md): Licenciamento e SBOM -- pip-audit e parte da estrategia de cadeia de suprimentos

## Notas

- Referencia: OWASP Testing Guide, Dev-Seguro Aulas 04 e 05
- RNF-010: o sistema deve possuir ferramentas de analise estatica e auditoria de seguranca
