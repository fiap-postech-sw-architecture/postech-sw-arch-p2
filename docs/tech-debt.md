# Dívida Técnica

Registro de decisões conscientes de simplificação no MVP que devem ser endereçadas em fases futuras.

## Itens

| # | Área | Descrição | Severidade | Fase Alvo |
|---|---|---|---|---|
| TD-001 | Segurança | CPF/CNPJ armazenado em texto plano (LGPD Art. 46) | Alta | F2 |
| TD-002 | Segurança | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | Alta | F2 |
| TD-003 | Segurança | JWT sem revogação (tokens curtos de 15 min) | Média | F2 |
| TD-004 | Segurança | Sem mecanismo de consentimento explícito | Média | F2 |
| TD-005 | Auth | Papel único (Admin). Mecânico usa Admin. | Baixa | F2 |
| TD-006 | Auth | Sem refresh tokens | Baixa | F2 |
| TD-007 | Domínio | Sem histórico de orçamentos (substituição total) | Baixa | F3 |
| TD-008 | Domínio | Sem orçamentos complementares durante execução | Baixa | F3 |
| TD-009 | Infra | Segredo JWT em variável de ambiente (não em KMS) | Média | F2 |
| TD-010 | Infra | Sem CSP headers | Baixa | F2 |
| TD-011 | Observabilidade | Eventos de domínio despachados sincronamente in-process | Média | F3 |
| TD-012 | Observabilidade | Falha de despacho de evento não causa rollback | Média | F3 |
| TD-013 | API | Sem notificações push/email/SMS | Baixa | F3 |
| TD-014 | Domínio | Orcamento JSONB sem índices GIN (consultas limitadas) | Baixa | F3 |
| TD-015 | Testes | Mutation testing como meta, não requisito hard | Baixa | F2 |

## Critérios de Priorização

- **Alta**: Risco de conformidade (LGPD) ou segurança. Endereçar na próxima fase.
- **Média**: Limitação técnica com workaround aceitável. Planejar para F2-F3.
- **Baixa**: Melhoria de qualidade. Endereçar quando conveniente.
