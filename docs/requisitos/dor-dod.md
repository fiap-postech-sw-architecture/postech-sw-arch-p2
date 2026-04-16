# Definition of Ready e Definition of Done — Oficina Mecânica

> **Versao**: 1.0 — Fase 1 MVP.

> Documento gerado com assistência de IA (Claude) e revisado pela equipe PytStop.
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
- [ ] Docker Compose funcional (`docker compose up` — [RNF-011](requisitos.md))
- [ ] Migrações Alembic aplicáveis automaticamente no startup

---

## 3. Aplicação ao Projeto

Mapeamento de cada user story contra os checklists DoR e DoD:

| US | Descrição | DoR atendido? | Evidência DoR | DoD checklist |
|---|---|---|---|---|
| US-001 | Cadastrar cliente CPF/CNPJ | Sim | RF-001, ADR-010, US com AC | Código + testes + PR + Docker |
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

## 4. DoR e DoD por Entregável

Além das user stories, cada artefato da entrega tem seus próprios critérios de prontidão e conclusão.

### 4.1 Documentação DDD

**DoR — Pronto para documentar:**

- [ ] Aulas 01-09 assistidas e anotadas
- [ ] Domínio da oficina compreendido (entrevistas com especialistas realizadas)
- [ ] Ferramentas de diagramação disponíveis (egon.io, Mermaid)
- [ ] Glossário de termos de domínio iniciado

**DoD — Documentação concluída:**

- [ ] Glossário com todos os termos da linguagem ubíqua ([glossario.md](glossario.md))
- [ ] Mapa de contextos delimitados com padrões de integração ([mapa-contextos.md](../arquitetura/mapa-contextos.md))
- [ ] 5 diagramas de Domain Storytelling em .egn ([domain-storytelling/](../arquitetura/domain-storytelling/))
- [ ] Event Storming com 2 fluxos detalhados ([event-storming/](../arquitetura/event-storming/))
- [ ] Modelo de domínio com agregados e value objects ([modelo-dominio.md](../arquitetura/modelo-dominio.md))
- [ ] ADRs para decisões relevantes ([adr/](../arquitetura/adr/))
- [ ] RFC de design do sistema ([RFC-001](../arquitetura/rfc/rfc-001-design-do-sistema.md))
- [ ] Referências bibliográficas em todos os documentos

### 4.2 Codigo-fonte

**DoR — Pronto para implementar:**

- [ ] Documentação DDD concluída (DoD 4.1 atendido)
- [ ] Arquitetura definida em ADR-003 (DDD + Onion)
- [ ] User stories com critérios de aceite no PRD
- [ ] Ambiente de desenvolvimento configurado (Python 3.12+, Docker)

**DoD — Codigo-fonte concluído:**

- [ ] Todos os bounded contexts implementados seguindo Onion Architecture
- [ ] Cobertura de testes >= 80% nos domínios críticos (Ordem de Servico, Estoque)
- [ ] Testes unitários e de integração passando
- [ ] Autenticação JWT funcional
- [ ] Swagger/OpenAPI gerado automaticamente
- [ ] Docker Compose funcional (`docker compose up` sobe todo o sistema)
- [ ] Migrações de banco aplicadas automaticamente no startup
- [ ] Code review aprovado em todas as PRs

### 4.3 Relatorio de vulnerabilidades

**DoR — Pronto para análise:**

- [ ] Código-fonte concluído (DoD 4.2 atendido)
- [ ] Ferramentas de scanning configuradas (bandit, pip-audit, trivy)
- [ ] Docker image buildada

**DoD — Relatório concluído:**

- [ ] Scanning estático de código executado (bandit)
- [ ] Auditoria de dependências executada (pip-audit)
- [ ] Scanning de container executado (trivy)
- [ ] Vulnerabilidades críticas e altas resolvidas ou justificadas
- [ ] Relatório documentado com evidências ([relatorio-vulnerabilidades.md](../seguranca/relatorio-vulnerabilidades.md))

### 4.4 Video de demonstração

**DoR — Pronto para gravar:**

- [ ] Código-fonte concluído (DoD 4.2 atendido)
- [ ] Roteiro do vídeo escrito ([roteiro-video.md](../entrega/roteiro-video.md))
- [ ] Ambiente de demonstração funcional
- [ ] Ferramenta de gravação preparada

**DoD — Video concluído:**

- [ ] Duração dentro do limite estabelecido
- [ ] Demonstração de todos os fluxos principais (CRUD cliente, ciclo OS, estoque)
- [ ] Arquitetura explicada brevemente
- [ ] Qualidade de áudio e vídeo adequada
- [ ] Upload realizado na plataforma indicada

### 4.5 PDF de entrega

**DoR — Pronto para montar:**

- [ ] Todos os entregáveis anteriores concluídos (DoD 4.1-4.4)
- [ ] Template de entrega disponível

**DoD — PDF concluído:**

- [ ] Link do repositório GitHub incluso
- [ ] Links de documentação acessíveis
- [ ] Link do vídeo incluso
- [ ] Checklist de entrega preenchido ([entrega-fase-1.md](../entrega/entrega-fase-1.md))
- [ ] PDF exportado e submetido na plataforma FIAP

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
