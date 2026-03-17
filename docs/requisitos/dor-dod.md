# Definition of Ready e Definition of Done — Oficina Mecânica

> Documento gerado com assistência de IA (Claude) e revisado pelo autor.
> Segue os conceitos da Aula 09 aplicados ao projeto da oficina mecânica.

---

## 1. Definition of Ready (DoR)

O DoR é um portão de qualidade para o início do trabalho. Uma user story só entra em desenvolvimento quando todos os itens abaixo estão atendidos:

- [ ] Documentação de requisitos escrita com fluxo da solução ([levantamento-de-requisitos.md](levantamento-de-requisitos.md))
- [ ] Refinamento técnico realizado com considerações por etapa ([refinamento-tecnico.md](refinamento-tecnico.md))
- [ ] Arquitetura da solução desenhada ([RFC-001](../arquitetura/rfc/rfc-001-design-do-sistema.md))
- [ ] Decisões técnicas documentadas em ADRs relevantes ([ADRs](../arquitetura/adr/))
- [ ] Quebra em user stories com critérios de aceite ([PRD](prd.md))
- [ ] Estimativa em story points ([refinamento-tecnico.md §5](refinamento-tecnico.md))
- [ ] Priorizada via MoSCoW ([PRD](prd.md))
- [ ] Dependências cross-contexto mapeadas (portas identificadas no [Mapa de Contextos](../arquitetura/mapa-contextos.md))
- [ ] Regras de negócio aplicáveis identificadas ([requisitos.md](requisitos.md))

---

## 2. Definition of Done (DoD)

O DoD define os critérios para considerar uma user story concluída. Todos os itens devem ser atendidos:

- [ ] Código implementado seguindo DDD + Onion Architecture ([ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md))
- [ ] Testes unitários e de integração passando (≥ 90% core domains, ≥ 80% demais — [RNF-009](requisitos.md))
- [ ] Code review aprovado (PR com squash merge)
- [ ] Scanning de segurança sem vulnerabilidades críticas ou altas (bandit, pip-audit, trivy — [RNF-010](requisitos.md))
- [ ] Documentação atualizada (Swagger auto-gen, README se necessário)
- [ ] Docker build funcional (`docker-compose up` — [RNF-011](requisitos.md))
- [ ] Migrações Alembic aplicáveis automaticamente no startup

---

## 3. Aplicação ao Projeto

Mapeamento de cada user story contra os checklists DoR e DoD:

| US | Descrição | DoR atendido? | Evidência DoR | DoD checklist |
|---|---|---|---|---|
| US-001 | Cadastrar cliente CPF/CNPJ | Sim | RF-001, ADR-011, US com AC | Código + testes + PR + Docker |
| US-002 | Vincular veículos | Sim | RF-002, modelo de domínio | Código + testes + PR + Docker |
| US-003 | Criar OS | Sim | RF-003, mapa de contextos (ClientePort) | Código + testes cross-context + PR |
| US-004 | Adicionar itens à OS | Sim | RF-003, RN-007, CatalogoPort | Código + testes + guard validado |
| US-005 | Gerar orçamento | Sim | RF-004, RN-008/RN-013 | Código + testes + JSONB validado |
| US-006 | Aprovar orçamento | Sim | RF-005, ADR-008, EstoquePort | Código + testes concorrência + PR |
| US-007 | Cancelar OS | Sim | RF-005, RN-002/RN-003 | Código + testes por status origem |
| US-008 | Gerenciar estoque | Sim | RF-006, RN-011 | Código + testes + soft delete |
| US-009 | Tempo médio | Sim | RF-008 | Código + teste agregação |
| US-010 | Gerenciar catálogo | Sim | RF-010, RN-010 | Código + testes + soft delete |
| US-011 | Iniciar diagnóstico | Sim | RF-005 | Código + teste transição |
| US-012 | Finalizar serviço | Sim | RF-005 | Código + teste transição |
| US-013 | Consulta pública | Sim | RF-007, ClientePort | Código + teste sem auth |

Todas as user stories atendem ao DoR: cada uma tem requisito funcional mapeado, critérios de aceite no PRD, decisões técnicas em ADRs, e estimativa em story points.

---

## Referências

ARAUJO, V. Definition of Ready (DoR) — Mais qualidade no Product Backlog. 2021. Disponível em: <https://www.zup.com.br/blog/definition-of-ready-dor>.

BUTLER, M. Definition of ready and definition of done: What's the difference?. 2021. Disponível em: <https://www.boost.co.nz/blog/2022/06/definition-ready-definition-done>.

HUETHER, D. The Definition Of Done. 2017. Disponível em: <https://www.leadingagile.com/2017/02/definition-of-done/>.

---

## Relação com Outros Documentos

- [Refinamento Técnico](refinamento-tecnico.md) — Especificação técnica que alimenta o DoR
- [Levantamento de Requisitos](levantamento-de-requisitos.md) — Jornada do usuário e análise de riscos
- [PRD](prd.md) — User stories com critérios de aceite
- [Requisitos](requisitos.md) — RF, RNF, RN detalhados
- [RFC-001](../arquitetura/rfc/rfc-001-design-do-sistema.md) — Design técnico
- [ADRs](../arquitetura/adr/) — Decisões arquiteturais
- [Glossário](glossario.md) — Linguagem Ubíqua
