# Segurança

> [↑ Raiz do projeto](../../README.md)

> **Versão**: 1.1 — Fase 1 MVP + scans de fechamento da fase 2.

Documentação de segurança do projeto, incluindo análise de vulnerabilidades e evidências de scanning.

## Documentos

| Arquivo | Descrição |
|---------|-----------|
| [plano-seguranca.md](plano-seguranca.md) | Plano de segurança — modelo de ameaças, controles de acesso, resposta a incidentes e conformidade LGPD |
| [relatorio-vulnerabilidades.md](relatorio-vulnerabilidades.md) | Relatório de vulnerabilidades — scanning estático (bandit), auditoria de dependências (pip-audit) e scanning de container (trivy) |
| [scan-fase-2.md](scan-fase-2.md) | Scans de fechamento da fase 2 — bandit, pip-audit (upgrades aplicados) e gitleaks (working tree + histórico) |

## Relação com Outros Documentos

- [Requisitos Não Funcionais](../requisitos/requisitos.md) — RNF-010 (scanning de segurança)
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) — Estratégia de autenticação JWT
- [DoR/DoD](../requisitos/dor-dod.md) — Critérios de prontidão e conclusão do relatório (seção 4.3)

> [↑ Raiz do projeto](../../README.md)
