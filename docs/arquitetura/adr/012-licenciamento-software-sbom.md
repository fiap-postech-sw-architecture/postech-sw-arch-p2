# Licenciamento de Software e SBOM

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)

* Status: Aceita
* Data: 2026-03-29

## Contexto e Problema

Riscos de cadeia de suprimentos incluem dependências comprometidas (caso UA-Parser-JS) e incompatibilidades de licença (GPL forçando abertura de código). O projeto utiliza diversas bibliotecas de terceiros. Como garantir que as dependências não introduzam riscos legais ou de segurança?

## Decisão

Adotar política de licenciamento e rastreabilidade de dependências:

- **Licenças permissivas obrigatórias**: todas as dependências diretas devem possuir licença permissiva (MIT, Apache 2.0, BSD)
- **GPL proibida**: dependências GPL são proibidas sem aprovação explícita da equipe
- **SBOM por release**: geração de Software Bill of Materials (SBOM) via CycloneDX a cada release
- **Auditoria periódica**: execução de pip-audit no pipeline CI e revisão mensal de vulnerabilidades em dependências

## Alternativas Consideradas

* Ignorar licenciamento e cadeia de suprimentos
* Apenas pip-audit (auditoria de vulnerabilidades)
* CycloneDX + pip-audit com política de licenças (escolhido)

### Ignorar licenciamento e cadeia de suprimentos

Não adotar política de licenciamento nem ferramentas de auditoria.

* Bom, porque zero overhead no processo de desenvolvimento
* Bom, porque não requer configuração de ferramentas adicionais
* Ruim, porque risco legal de licenças incompatíveis (GPL contaminando o projeto)
* Ruim, porque vulnerabilidades em dependências passam despercebidas
* Ruim, porque não há rastreabilidade em caso de incidente na cadeia de suprimentos

### Apenas pip-audit

Auditoria de vulnerabilidades em dependências via pip-audit no CI.

* Bom, porque detecta CVEs conhecidas em dependências
* Bom, porque integração simples com GitHub Actions
* Ruim, porque não rastreia licenças de dependências
* Ruim, porque não gera SBOM para auditoria retroativa
* Ruim, porque não previne adição de dependências com licenças restritivas

### CycloneDX + pip-audit com política de licenças (escolhido)

SBOM, auditoria de vulnerabilidades e política explícita de licenças.

* Bom, porque rastreabilidade de todas as dependências e suas licenças
* Bom, porque SBOM permite auditoria retroativa em caso de incidente (ex: dependência comprometida)
* Bom, porque política de licenças previne riscos legais antes da adição de dependências
* Bom, porque pip-audit detecta vulnerabilidades continuamente no CI
* Ruim, porque overhead de geração do SBOM a cada release
* Ruim, porque necessidade de verificar licença manualmente antes de adicionar nova dependência

## Consequências

### Positivas

* Inventário de dependências e suas licenças via SBOM
* Conformidade com boas práticas de segurança de cadeia de suprimentos
* Prevenção de licenças incompatíveis (GPL) que poderiam forçar abertura do código
* Detecção contínua de vulnerabilidades em dependências via pip-audit
* Capacidade de auditoria retroativa em caso de incidente

### Negativas

* Necessidade de verificar licença antes de adicionar qualquer nova dependência
* Overhead de geração e armazenamento do SBOM a cada release
* Possível bloqueio de dependências úteis que possuam licença GPL

## Decisões Relacionadas

- [ADR-011](011-pipeline-seguranca-analise-estatica.md): Pipeline de segurança -- pip-audit faz parte do pipeline CI
- [ADR-010](010-validacao-documentos-brutils.md): brutils possui licença MIT, compatível com a política

## Notas

- Referência: Dev-Seguro Aula 03, OWASP Software Component Verification Standard (SCVS)
- CycloneDX: formato padrão OWASP para SBOM, suportado por ferramentas de segurança
- RNF-015: dependências auditadas mensalmente via pip-audit; zero vulnerabilidades críticas
- RNF-016: SBOM gerado via CycloneDX a cada release

> [↑ Raiz do projeto](../../../README.md) · [↑ Arquitetura](../README.md)
