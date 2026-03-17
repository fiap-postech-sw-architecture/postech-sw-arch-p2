# Relatório de Vulnerabilidades

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

> **Status**: Parcial — seções de ferramentas automatizadas aguardam execução do pipeline CI.

## Escopo

Análise de segurança do MVP back-end do sistema de oficina mecânica (Fase 1).

## Metodologia

Referência: OWASP API Security Top 10 (2023).

Ferramentas utilizadas:
- **SonarQube** — Análise estática de código e qualidade (SAST, code smells, cobertura)
- **OWASP ZAP** — Teste dinâmico de segurança de aplicações (DAST/pentest automatizado)
- **bandit** — Análise estática de segurança Python (SAST)
- **pip-audit** — Auditoria de dependências vulneráveis
- **gitleaks** — Detecção de segredos no histórico Git
- **trivy** — Scan de vulnerabilidades na imagem Docker

## Achados

| # | Severidade | Descrição | CVSS | Status | Mitigação |
|---|---|---|---|---|---|
| 1 | Baixa | CPF/CNPJ armazenado em texto plano | 3.1 | Em remediação | Encriptação via pgcrypto no MVP (RF-011). |
| 2 | Informativo | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | — | Em remediação | Implementação no MVP (RF-015). |
| 3 | Informativo | Sem mecanismo de consentimento explícito | — | Risco aceito | Escopo do MVP não inclui coleta de consentimento. |
| 4 | Informativo | JWT ainda sem revogação e sem refresh tokens implementados | 2.0 | Em remediação | Tabela `tokens_revogados` com JTI e refresh tokens com rotação (RF-012, RF-013). |

## Conformidade LGPD

| Aspecto | Status MVP | Plano de Evolução |
|---|---|---|
| Mascaramento de dados sensíveis em respostas | Planejado (CPF/CNPJ mascarado em listagens) | — |
| Remoção de PII em logs | Planejado (processador structlog) | Criptografia em nível de campo |
| Armazenamento de CPF/CNPJ | Em remediação — encriptação via pgcrypto (RF-011) | — |
| Direito de acesso (Art. 18, I) | Em remediação (RF-015) | Endpoint `GET /clientes/{id}/dados-pessoais` |
| Portabilidade (Art. 18, V) | Em remediação (RF-015) | Endpoint de exportação JSON |
| Exclusão (Art. 18, VI) | Em remediação (RF-015) | Anonimização com preservação de histórico de OS |
| Consentimento | Não implementado | Mecanismo de opt-in na criação de cliente |

## Análise Estática e Qualidade (SonarQube)

```
(Output do SonarQube a ser inserido após execução)
```

## Teste Dinâmico de Segurança (OWASP ZAP)

```
(Output do OWASP ZAP a ser inserido após execução)
```

## Análise Estática (bandit)

```
(Output do bandit a ser inserido após execução)
```

## Auditoria de Dependências (pip-audit)

```
(Output do pip-audit a ser inserido após execução)
```

## Detecção de Segredos (gitleaks)

```
(Output do gitleaks a ser inserido após execução)
```

## Scan de Imagem Docker (trivy)

```
(Output do trivy a ser inserido após execução)
```

## Recomendações para Produção

1. Adicionar WAF com rate limiting por usuário autenticado
2. Migrar segredo JWT para KMS (mitigado no MVP via validação de comprimento no startup)
3. Adicionar CSP headers (TD-003)
4. Implementar mecanismo de consentimento explícito (RF-019, TD-001)

## Referências

- [Tech Debt](../tech-debt.md) — Dívida técnica
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) — Autenticação JWT

- [Requisitos](../requisitos/requisitos.md) — RF-011, RF-012, RF-013, RF-015, RF-019
