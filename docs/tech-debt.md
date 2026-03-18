# Dívida Técnica

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

Tech debt são decisões conscientes de débito — itens que sabemos estar incompletos ou ausentes na entrega atual e que aceitamos como limitação conhecida. Não são requisitos adiados nem funcionalidades desejadas; são simplificações deliberadas cujo custo de correção é aceito para o escopo do MVP.

Funcionalidades que não serão implementadas no MVP estão classificadas como Could Have no [PRD](requisitos/prd.md). Requisitos que serão implementados estão nos respectivos RFs em [requisitos.md](requisitos/requisitos.md).

Classificação por tipo conforme disciplina Software Architecture — Aula 5: Gerenciamento de Débito Técnico:

- **Deliberado**: assumido conscientemente pela equipe para acelerar entrega ou validar hipóteses
- **Acidental**: surge sem que a equipe perceba, por desconhecimento ou mudanças inesperadas
- **Planejado**: equipe sabe que a solução não é ideal, documenta e planeja pagar depois
- **Negligenciado**: débito ignorado por muito tempo, mesmo após identificação

## Itens

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-001 | Segurança | Sem mecanismo de consentimento explícito LGPD | Deliberado | Média | Alto | Sim | Crescente | Necessário para conformidade plena com a LGPD, mas deferido no MVP. Risco baixo sem coleta ativa de dados sensíveis além do cadastro. |
| TD-002 | Domínio | Sem histórico de orçamentos (substituição total do JSONB) | Deliberado | Baixa | Baixo | Não | Estável | Orçamento existe como Value Object imutável, mas sem versionamento em array JSONB com timestamp. Funcionalidade parcial aceita. RF-017 (Could Have). |
| TD-003 | Infra | Sem CSP headers (Content-Security-Policy) | Deliberado | Baixa | Baixo | Não | Estável | Boa prática de segurança, mas sem front-end servido pela API o impacto é mínimo. Headers básicos (X-Content-Type-Options, HSTS) estão presentes (RNF-004). |
| TD-004 | API | Notificações via stub (LogNotificacaoAdapter) | Deliberado | Baixa | Baixo | Não | Estável | Decisão consciente: o sistema funciona sem notificações reais (push, email, SMS). O adapter de log permite evolução futura sem mudança no domínio. [ADR-003](arquitetura/adr/003-arquitetura-ddd-onion.md): inversão de dependência viabiliza a troca sem impacto no domínio. |
| TD-005 | Domínio | Orçamento JSONB sem índices GIN | Planejado | Baixa | Médio | Não | Crescente | Performance aceitável no MVP com volume baixo de dados. Índices GIN seriam otimização prematura sem métricas de produção. A ser reavaliado com dados reais. |
| TD-006 | Testes | Mutation testing como meta, não requisito hard | Deliberado | Baixa | Baixo | Não | Estável | Cobertura de linha (90%+) e branch (85%+) nos domínios principais já garante qualidade. Mutmut é bônus para validação adicional. [ADR-005](arquitetura/adr/005-estrategia-testes.md) documenta a estratégia. |

## DDD Tactical Compliance

Débitos aceitáveis no MVP relacionados à conformidade tática do DDD:

| # | Área | Descrição | Tipo | Severidade | Impacto no Negócio | Risco de Produção | Tendência de Crescimento | Justificativa |
|---|---|---|---|---|---|---|---|---|
| TD-007 | Domínio | Value Objects com validação mínima | Deliberado | Baixa | Baixo | Não | Estável | `not-null` e tipo correto são obrigatórios. Validação completa de formato (ex: dígito verificador do CPF) é deferida para brutils ([ADR-010](arquitetura/adr/010-validacao-documentos-brutils.md)). |
| TD-008 | Domínio | Dispatch síncrono de domain events | Planejado | Média | Médio | Sim | Crescente | O mecanismo de dispatch é deferido (RF-018 Transactional Outbox, Could Have); o payload dos eventos não é — cada evento deve carregar `agregado_id`, `ocorrido_em` e campos alterados conforme `DomainEvent` base. |
| TD-009 | Domínio | Eventos mapeados no event storming sem emissão no código | Planejado | Baixa | Baixo | Não | Crescente | Eventos identificados mas ainda sem emissão: `ClienteCadastrado`, `VeiculoAdicionado`, `EstoqueReservado`, `EstoqueLiberado`, `ServicoCadastrado`. A serem implementados com o mecanismo de dispatch (TD-008). |

## Estratégia de Pagamento

Conforme recomendações da disciplina Software Architecture — Aula 5:

1. **Boy Scout Rule**: cada alteração no código deve deixá-lo melhor do que encontrou. Refatorações incrementais junto com novas funcionalidades.
2. **Refatorações incrementais**: não esperar uma janela de sprint exclusivamente técnica. Incluir melhorias técnicas nos sprints regulares, tratando débitos como parte do backlog priorizado.
3. **Reserva de sprint técnico**: negociar com o Product Owner sprints técnicos no roadmap para lidar com débitos de maior impacto (TD-001 e TD-008 são candidatos prioritários).
4. **ADRs como prevenção**: cada decisão técnica registrada em ADR ([ADR-001](arquitetura/adr/001-framework-fastapi.md) a [ADR-010](arquitetura/adr/010-validacao-documentos-brutils.md)) evita débitos invisíveis: decisões sem rastreabilidade cujo racional original se perde.
5. **Métricas de fluxo**: monitorar lead time, cycle time e taxa de falhas para detectar crescimento do débito técnico e justificar refatorações para o negócio.
