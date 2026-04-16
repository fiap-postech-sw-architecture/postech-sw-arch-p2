# C4 — Diagrama de Contexto (Level 1)

> **Versao**: 1.0 — Fase 1 MVP.

Visao de mais alto nivel do sistema, mostrando o PytStop e seus relacionamentos com atores e sistemas externos. Baseado no modelo C4 de Simon Brown (Software Architecture — Aula 2).

## Diagrama

```mermaid
C4Context
    title Diagrama de Contexto — PytStop

    Person(admin, "Admin", "Gerente da oficina.")

    System(pytstop, "PytStop", "Sistema Integrado de Atendimento<br/>e Execucao de Servicos.<br/>Gerencia o ciclo completo de<br/>Ordens de Servico, clientes,<br/>estoque e catalogo.")

    Rel(admin, pytstop, "Gerencia OS, clientes,<br/>estoque e catalogo", "HTTPS / JWT")
```

## Atores

| Ator | Papel (`Papel` enum) | Descricao |
|---|---|---|
| **Admin** | `Papel.Admin` | Gerente da oficina. Unico papel no MVP conforme glossario. |

O papel `Mecanico` esta planejado para evolucao futura; consulte o [glossario](../../requisitos/glossario.md). No MVP o mecanico opera com credenciais de Admin, por isso nao aparece como ator separado no diagrama.

## Sistemas Externos

Nenhum sistema externo no MVP. O Tech Challenge define um sistema autocontido com autenticacao propria via JWT ([ADR-004](../adr/004-autenticacao-jwt.md)) e banco de dados local.

## Rastreabilidade

- Nome do sistema: conforme [PRD](../../requisitos/prd.md) e [RFC-001](../rfc/rfc-001-design-do-sistema.md)
- Papel Admin: conforme [glossario](../../requisitos/glossario.md) (contexto Autenticacao)
- Decisao arquitetural: [ADR-003](../adr/003-arquitetura-ddd-onion.md)
