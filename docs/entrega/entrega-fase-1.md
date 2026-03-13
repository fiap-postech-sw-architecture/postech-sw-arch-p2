# Documento de Entrega — Fase 1

## Dados do Grupo

| Campo | Valor |
|---|---|
| Nome do grupo | Solo (individual) |
| Participante | João Amaral |
| Discord | jbamaral |
| Turma | 15SOAT |

## Links

| Recurso | URL |
|---|---|
| Documentação | [docs/](../../docs/) (neste repositório) |
| Repositório | [github.com/jbamaral/postech-sw-arch-p1](https://github.com/jbamaral/postech-sw-arch-p1) |
| Event Storming (Miro) | *(link a ser adicionado após criação do board)* |
| Vídeo | *(link a ser adicionado)* |

## Entregáveis

### Documentação DDD

- [Domain Storytelling — Diagramas](../arquitetura/domain-storytelling/)
- [Especialistas de Domínio — Entrevistas](../arquitetura/domain-storytelling/especialistas-de-dominio.md)
- [Event Storming — Fluxo 1: Ciclo de Vida da OS](../arquitetura/event-storming/fluxo-1-ciclo-os.md)
- [Event Storming — Fluxo 2: Gestão de Estoque](../arquitetura/event-storming/fluxo-2-gestao-estoque.md)
- [Glossário — Linguagem Ubíqua](../requisitos/glossario.md)
- [Mapa de Contextos](../arquitetura/mapa-contextos.md)
- [Modelo de Domínio](../arquitetura/modelo-dominio.md)

### Arquitetura

- [RFC-001: Design do Sistema](../arquitetura/rfc/rfc-001-design-do-sistema.md)
- [ADRs (000-011)](../arquitetura/adr/)

### Requisitos

- [Requisitos Funcionais e Não-Funcionais](../requisitos/requisitos.md)
- [PRD](../requisitos/prd.md)
- [Tech Challenge (original)](../requisitos/desafio-tech-fase-1.md)

### Segurança

- [Relatório de Vulnerabilidades](../seguranca/relatorio-vulnerabilidades.md)

### Código

- README.md com instruções de uso
- Dockerfile e docker-compose.yml
- APIs RESTful documentadas via Swagger
- Testes automatizados com cobertura >= 90% nos domínios principais

## Relatório de Vulnerabilidades (Resumo)

*(Resumo a ser preenchido após execução dos scans de segurança na fase de implementação)*

## Geração do PDF

```bash
pandoc docs/entrega/entrega-fase-1.md -o entrega-fase-1.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  -V mainfont="DejaVu Sans"
```
