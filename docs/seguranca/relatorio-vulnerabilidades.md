# Relatório de Vulnerabilidades

## Escopo

Análise de segurança do MVP back-end do sistema de oficina mecânica (Fase 1).

## Metodologia

Referência: OWASP API Security Top 10 (2023).

Ferramentas utilizadas:
- **bandit** — Análise estática de segurança Python (SAST)
- **pip-audit** — Auditoria de dependências vulneráveis
- **gitleaks** — Detecção de segredos no histórico Git
- **trivy** — Scan de vulnerabilidades na imagem Docker

## Achados

| # | Severidade | Descrição | CVSS | Status | Mitigação |
|---|---|---|---|---|---|
| 1 | Baixa | CPF/CNPJ armazenado em texto plano | 3.1 | Risco aceito | Documentado. Remediação planejada com pgcrypto pós-MVP. |
| 2 | Informativo | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | — | Risco aceito | Cronograma de implementação pós-MVP documentado. |
| 3 | Informativo | Sem mecanismo de consentimento explícito | — | Risco aceito | Escopo do MVP não inclui coleta de consentimento. |
| 4 | Informativo | JWT sem revogação | 2.0 | Risco aceito | Tokens de 15 min. Tabela blacklist JTI planejada. |

> Tabela a ser atualizada com achados reais dos scans na fase de implementação.

## Conformidade LGPD

| Aspecto | Status MVP | Plano de Evolução |
|---|---|---|
| Mascaramento de dados sensíveis em respostas | Implementado (CPF/CNPJ mascarado em listagens) | — |
| Remoção de PII em logs | Implementado (processador structlog) | Criptografia em nível de campo |
| Armazenamento de CPF/CNPJ | Texto plano (risco aceito, Art. 46) | Criptografia via pgcrypto |
| Direito de acesso (Art. 18, I) | Não implementado | Endpoint `GET /clientes/{id}/dados-pessoais` |
| Portabilidade (Art. 18, V) | Não implementado | Endpoint de exportação JSON |
| Exclusão (Art. 18, VI) | Não implementado | Anonimização com preservação de histórico de OS |
| Consentimento | Não implementado | Mecanismo de opt-in na criação de cliente |

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

1. Implementar criptografia de CPF/CNPJ via pgcrypto
2. Adicionar endpoints LGPD Art. 18
3. Implementar revogação de JWT (tabela blacklist JTI)
4. Adicionar WAF com rate limiting por usuário autenticado
5. Migrar segredo JWT para KMS
6. Adicionar CSP headers
7. Implementar mecanismo de consentimento
