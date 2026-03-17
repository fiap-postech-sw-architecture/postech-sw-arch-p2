# Dívida Técnica

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

Tech debt são decisões conscientes de débito — itens que sabemos estar incompletos ou ausentes na entrega atual e que aceitamos como limitação conhecida. Não são requisitos adiados nem funcionalidades desejadas; são simplificações deliberadas cujo custo de correção é aceito para o escopo do MVP.

Funcionalidades que não serão implementadas no MVP estão classificadas como Could Have no [PRD](requisitos/prd.md). Requisitos que serão implementados estão nos respectivos RFs em [requisitos.md](requisitos/requisitos.md).

## Itens

| # | Área | Descrição | Severidade | Justificativa |
|---|---|---|---|---|
| TD-001 | Segurança | Sem mecanismo de consentimento explícito LGPD | Média | Sabemos que é necessário para conformidade plena, mas aceitamos a limitação no MVP. Risco baixo sem coleta ativa de dados sensíveis além do cadastro. |
| TD-002 | Domínio | Sem histórico de orçamentos (substituição total do JSONB) | Baixa | Orçamento existe como Value Object imutável, mas sem versionamento em array JSONB com timestamp. Funcionalidade parcial aceita. |
| TD-003 | Infra | Sem CSP headers (Content-Security-Policy) | Baixa | Boa prática de segurança, mas sem front-end servido pela API o impacto é mínimo. Headers básicos (X-Content-Type-Options, HSTS) estão presentes. |
| TD-004 | API | Notificações via stub (LogNotificacaoAdapter) | Baixa | Decisão consciente: o sistema funciona sem notificações reais (push, email, SMS). O adapter de log permite evolução futura sem mudança no domínio. |
| TD-005 | Domínio | Orçamento JSONB sem índices GIN | Baixa | Performance aceitável no MVP com volume baixo de dados. Índices GIN seriam otimização prematura sem métricas de produção. |
| TD-006 | Testes | Mutation testing como meta, não requisito hard | Baixa | Cobertura de linha (90%+) e branch (85%+) nos domínios principais já garante qualidade. Mutmut é bônus para validação adicional. |
