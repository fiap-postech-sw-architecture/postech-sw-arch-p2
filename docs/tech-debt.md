# Dívida Técnica

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

Registro de decisões conscientes de simplificação no MVP que serão endereçadas em versões iterativas dentro da Fase 1.

## Versões MVP

| Versão | Foco | Semana | Tech Debt Incorporado |
|---|---|---|---|
| MVP-0.01 | Scaffolding: Docker, middlewares | S2 | TD-009, TD-010 |
| MVP-0.02 | Spike: mapeamento imperativo go/no-go | S2 | — |
| MVP-0.03 | Cliente + Veículo | S3 | TD-001, TD-005 |
| MVP-0.04 | Catálogo + OS + orçamento complementar | S4 | TD-007, TD-008, TD-014 |
| MVP-0.05 | Estoque + Auth (JWT, RBAC) | S5 | TD-003, TD-005 (RBAC completo), TD-006 |
| MVP-0.06 | Integração cross-contexto, LGPD | S5–S6 | TD-002, TD-004, TD-011, TD-012 |
| MVP-0.07 | Endurecimento: scans, cobertura | S6–S7 | TD-013, TD-015 |
| MVP-1.0 | Docs + entrega | S8 | Consolidação |

## Itens

| # | Área | Descrição | Severidade | Versão MVP |
|---|---|---|---|---|
| TD-001 | Segurança | CPF/CNPJ armazenado em texto plano (LGPD Art. 46) | Alta | MVP-0.03 |
| TD-002 | Segurança | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | Alta | MVP-0.06 |
| TD-003 | Segurança | JWT sem revogação (tokens curtos de 15 min) | Média | MVP-0.05 |
| TD-004 | Segurança | Sem mecanismo de consentimento explícito | Média | MVP-0.06 |
| TD-005 | Auth | Papel único (Admin). Mecânico usa Admin. | Baixa | MVP-0.03 / MVP-0.05 |
| TD-006 | Auth | Sem refresh tokens | Baixa | MVP-0.05 |
| TD-007 | Domínio | Sem histórico de orçamentos (substituição total) | Baixa | MVP-0.04 |
| TD-008 | Domínio | Sem orçamentos complementares durante execução | Baixa | MVP-0.04 |
| TD-009 | Infra | Segredo JWT em variável de ambiente (não em secrets) | Média | MVP-0.01 |
| TD-010 | Infra | Sem CSP headers | Baixa | MVP-0.01 |
| TD-011 | Observabilidade | Eventos de domínio despachados sincronamente in-process | Média | MVP-0.06 |
| TD-012 | Observabilidade | Falha de despacho de evento não causa rollback | Média | MVP-0.06 |
| TD-013 | API | Sem notificações push/email/SMS | Baixa | MVP-0.07 |
| TD-014 | Domínio | Orcamento JSONB sem índices GIN (consultas limitadas) | Baixa | MVP-0.04 |
| TD-015 | Testes | Mutation testing como meta, não requisito hard | Baixa | MVP-0.07 |

## Estratégia de Corte

Se o tempo apertar, cortar na ordem reversa de prioridade:

1. TD-013 (notificações stub)
2. TD-015 (mutation testing hard)
3. TD-004 (consentimento LGPD)
4. TD-007 (histórico orçamento)

Inegociáveis: TD-001, TD-002, TD-003, TD-005, TD-006, TD-008, TD-009, TD-010, TD-011, TD-012, TD-014.

## Critérios de Priorização

- **Alta**: Risco de conformidade (LGPD) ou segurança.
- **Média**: Limitação técnica com workaround aceitável.
- **Baixa**: Melhoria de qualidade.
