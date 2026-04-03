# Licenciamento de Software e SBOM

* Status: Aceita
* Data: 2026-03-29

## Contexto e Problema

Riscos de cadeia de suprimentos incluem dependencias comprometidas (caso UA-Parser-JS) e incompatibilidades de licenca (GPL forcando abertura de codigo). O projeto utiliza diversas bibliotecas de terceiros. Como garantir que as dependencias nao introduzam riscos legais ou de seguranca?

## Decisao

Adotar politica de licenciamento e rastreabilidade de dependencias:

- **Licencas permissivas obrigatorias**: todas as dependencias diretas devem possuir licenca permissiva (MIT, Apache 2.0, BSD)
- **GPL proibida**: dependencias GPL sao proibidas sem aprovacao explicita da equipe
- **SBOM por release**: geracao de Software Bill of Materials (SBOM) via CycloneDX a cada release
- **Auditoria periodica**: execucao de pip-audit no pipeline CI e revisao mensal de vulnerabilidades em dependencias

## Alternativas Consideradas

* Ignorar licenciamento e cadeia de suprimentos
* Apenas pip-audit (auditoria de vulnerabilidades)
* CycloneDX + pip-audit com politica de licencas (escolhido)

### Ignorar licenciamento e cadeia de suprimentos

Nao adotar politica de licenciamento nem ferramentas de auditoria.

* Bom, porque zero overhead no processo de desenvolvimento
* Bom, porque nao requer configuracao de ferramentas adicionais
* Ruim, porque risco legal de licencas incompativeis (GPL contaminando o projeto)
* Ruim, porque vulnerabilidades em dependencias passam despercebidas
* Ruim, porque nao ha rastreabilidade em caso de incidente na cadeia de suprimentos

### Apenas pip-audit

Auditoria de vulnerabilidades em dependencias via pip-audit no CI.

* Bom, porque detecta CVEs conhecidas em dependencias
* Bom, porque integracao simples com GitHub Actions
* Ruim, porque nao rastreia licencas de dependencias
* Ruim, porque nao gera SBOM para auditoria retroativa
* Ruim, porque nao previne adicao de dependencias com licencas restritivas

### CycloneDX + pip-audit com politica de licencas (escolhido)

SBOM, auditoria de vulnerabilidades e politica explicita de licencas.

* Bom, porque rastreabilidade de todas as dependencias e suas licencas
* Bom, porque SBOM permite auditoria retroativa em caso de incidente (ex: dependencia comprometida)
* Bom, porque politica de licencas previne riscos legais antes da adicao de dependencias
* Bom, porque pip-audit detecta vulnerabilidades continuamente no CI
* Ruim, porque overhead de geracao do SBOM a cada release
* Ruim, porque necessidade de verificar licenca manualmente antes de adicionar nova dependencia

## Consequencias

### Positivas

* Inventario de dependencias e suas licencas via SBOM
* Conformidade com boas praticas de seguranca de cadeia de suprimentos
* Prevencao de licencas incompativeis (GPL) que poderiam forcar abertura do codigo
* Deteccao continua de vulnerabilidades em dependencias via pip-audit
* Capacidade de auditoria retroativa em caso de incidente

### Negativas

* Necessidade de verificar licenca antes de adicionar qualquer nova dependencia
* Overhead de geracao e armazenamento do SBOM a cada release
* Possivel bloqueio de dependencias uteis que possuam licenca GPL

## Decisoes Relacionadas

- [ADR-011](011-pipeline-seguranca-analise-estatica.md): Pipeline de seguranca -- pip-audit faz parte do pipeline CI
- [ADR-010](010-validacao-documentos-brutils.md): brutils possui licenca MIT, compativel com a politica

## Notas

- Referencia: Dev-Seguro Aula 03, OWASP Software Component Verification Standard (SCVS)
- CycloneDX: formato padrao OWASP para SBOM, suportado por ferramentas de seguranca
- RNF-015: dependencias auditadas mensalmente via pip-audit; zero vulnerabilidades criticas
- RNF-016: SBOM gerado via CycloneDX a cada release
