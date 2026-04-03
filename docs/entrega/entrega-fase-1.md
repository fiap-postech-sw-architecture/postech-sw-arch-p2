# Documento de Entrega — Fase 1

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

## Dados do Grupo

| Campo | Valor |
|---|---|
| Nome do grupo | PytStop |
| Turma | 15SOAT |

### Membros

| Nome | Discord |
|---|---|
| João Amaral | jbamaral |
| Allan Aurélio | PLACEHOLDER |
| Carlos Silva | PLACEHOLDER |
| Guilherme Sousa | PLACEHOLDER |
| Nicolas Gerbi | PLACEHOLDER |

## Links

| Recurso | URL |
|---|---|
| Documentação | [docs/](../../docs/) (neste repositório) |
| Repositório | [github.com/jbamaral/postech-sw-arch-p1](https://github.com/jbamaral/postech-sw-arch-p1) |
| Event Storming | [Workshop de Event Storming](../arquitetura/event-storming/workshop-event-storming.md) |
| Event Storming (Miro) | [Miro Board — Event Storming](https://miro.com/app/board/uXjVGqQ_lk4=/) |
| Domain Storytelling (Miro) | [Miro Board — Domain Storytelling](https://miro.com/app/board/uXjVGqQ_lk4=/) |
| Vídeo | *(link a ser adicionado)* |

## Entregáveis

### Documentação DDD

- [Domain Storytelling — Diagramas](../arquitetura/domain-storytelling/)
- [Especialistas de Domínio — Entrevistas](../arquitetura/domain-storytelling/especialistas-de-dominio.md)
- [Event Storming — Fluxo 1: Ciclo de Vida da OS](../arquitetura/event-storming/fluxo-1-ciclo-os.md)
- [Event Storming — Fluxo 2: Gestão de Estoque](../arquitetura/event-storming/fluxo-2-gestao-estoque.md)
- [Workshop de Event Storming](../arquitetura/event-storming/workshop-event-storming.md)
- [Glossário — Linguagem Ubíqua](../requisitos/glossario.md)
- [Mapa de Contextos](../arquitetura/mapa-contextos.md)
- [Modelo de Domínio](../arquitetura/modelo-dominio.md)

### Arquitetura

- [RFC-001: Design do Sistema](../arquitetura/rfc/rfc-001-design-do-sistema.md)
- [ADRs (000-013)](../arquitetura/adr/)
- [C4 — Diagrama de Contexto](../arquitetura/c4/c4-contexto.md)
- [C4 — Diagrama de Container](../arquitetura/c4/c4-container.md)
- [C4 — Diagrama de Componentes](../arquitetura/c4/c4-componentes.md)
- [Guia de Documentação de Arquitetura (HLD/LLD)](../arquitetura/README.md)
- [DAS — Documento de Aprovação da Solução](documento-aprovacao-solucao.md)

### Qualidade

- [Estratégia de Testes](../qualidade/estrategia-testes.md)

### Requisitos

- [Requisitos Funcionais e Não-Funcionais](../requisitos/requisitos.md)
- [PRD](../requisitos/prd.md)
- [Tech Challenge (original)](../requisitos/desafio-tech-fase-1.md)
- [Levantamento de Requisitos](../requisitos/levantamento-de-requisitos.md)
- [Refinamento Técnico](../requisitos/refinamento-tecnico.md)
- [Definition of Ready / Definition of Done](../requisitos/dor-dod.md)
- [Matriz de Rastreabilidade](../requisitos/matriz-rastreabilidade.md)

### Segurança

- [Relatório de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)
- [Plano de Segurança](../seguranca/plano-seguranca.md)

### Código

- README.md com instruções de uso
- Dockerfile e docker-compose.yml
- APIs RESTful documentadas via Swagger
- Testes automatizados com cobertura >= 80% nos domínios críticos

## Relatório de Vulnerabilidades (Resumo)

*(Resumo a ser preenchido após execução dos scans de segurança na fase de implementação)*

## Geração do PDF

```bash
pandoc docs/entrega/entrega-fase-1.md -o entrega-fase-1.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  -V mainfont="DejaVu Sans"
```
