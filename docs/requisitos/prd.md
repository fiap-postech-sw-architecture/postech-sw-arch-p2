# PRD — Sistema Integrado de Atendimento e Execução de Serviços

## Declaração do Problema

Uma oficina mecânica de médio porte opera com anotações manuais e planilhas, gerando erros na priorização de atendimentos, falhas no controle de peças, dificuldade no acompanhamento de serviços, perda de histórico e ineficiência nos fluxos de orçamento.

O sistema proposto é um MVP back-end que digitaliza a gestão de ordens de serviço, clientes, veículos, catálogo de serviços e estoque de peças, permitindo ao cliente acompanhar o andamento do serviço via API.

Ver [Levantamento de Requisitos](levantamento-de-requisitos.md) para a narrativa metodológica com jornadas atual e da solução.

## Objetivos

- Digitalizar o ciclo completo da Ordem de Serviço (recebimento → entrega)
- Aplicar Domain-Driven Design com Linguagem Ubíqua em português
- Controlar estoque de peças com reserva atômica na aprovação de orçamento
- Permitir consulta pública de status por placa + documento
- Garantir 90%+ de cobertura de testes nos domínios principais (Ordem de Serviço e Estoque) e 80%+ nos demais domínios
- Proteger endpoints administrativos com JWT

## Não-Objetivos

- Interface gráfica (front-end)
- Notificações reais (push, email, SMS) — stub via `LogNotificacaoAdapter`
- Integração com sistemas externos (ERP, contabilidade)
- Agendamento de serviços
- Pagamento ou faturamento
- Relatórios gerenciais além do tempo médio de execução

## Personas

### Admin (Gerente da Oficina)

**Perfil**: Responsável pela operação da oficina. Cadastra clientes, veículos, serviços e gerencia o estoque. Acompanha todas as ordens de serviço e toma decisões de negócio (aprovação de orçamentos, cancelamentos).

**Necessidades**:
- Visão completa de todas as OS em andamento
- Controle de estoque com alertas de nível baixo
- Métricas de tempo de execução para planejamento
- Segurança no acesso aos dados (autenticação obrigatória)

**Frustrações atuais**:
- Informações espalhadas em papéis e planilhas
- Sem visibilidade do estoque em tempo real
- Dificuldade em priorizar atendimentos

### Mecânico (Técnico)

> No MVP, o Mecânico compartilha o papel Admin. Diferenciação de papéis planejada para evolução futura.

**Perfil**: Profissional que executa diagnósticos e serviços. Inicia o diagnóstico, identifica serviços necessários e finaliza a execução.

**Necessidades**:
- Saber quais OS estão atribuídas e seus status
- Registrar início de diagnóstico e conclusão de serviço
- Consultar peças disponíveis no estoque

**Frustrações atuais**:
- Não saber a prioridade dos atendimentos
- Descobrir falta de peça durante a execução

### Cliente (Proprietário do Veículo)

**Perfil**: Pessoa física ou jurídica que traz veículos à oficina. Quer acompanhar o andamento do serviço sem precisar ligar ou ir presencialmente.

**Necessidades**:
- Consultar status da OS a qualquer momento
- Saber quando o veículo está pronto para retirada
- Transparência no orçamento

**Frustrações atuais**:
- Sem visibilidade do andamento
- Ter que ligar para saber se o carro está pronto

## Histórias de Usuário

### Admin

| ID | História | Critérios de Aceite | Prioridade |
|---|---|---|---|
| US-001 | Como Admin, quero cadastrar um cliente por CPF/CNPJ para manter o registro da oficina. | CPF/CNPJ validado. Duplicata retorna 409. Dados mascarados em listagem. | Must |
| US-002 | Como Admin, quero vincular veículos a um cliente para rastrear o histórico por veículo. | Placa única. Veículo criado via endpoint do cliente. Formato antigo e Mercosul aceitos. | Must |
| US-003 | Como Admin, quero criar uma OS associando cliente e veículo para iniciar o atendimento. | OS criada com status Recebida. Cliente e veículo devem existir. | Must |
| US-004 | Como Admin, quero adicionar serviços e peças à OS para compor o orçamento. | Item referencia serviço do catálogo. Preço obtido do catálogo. Só aceito em Recebida/EmDiagnostico. | Must |
| US-005 | Como Admin, quero gerar o orçamento automaticamente para enviar ao cliente. | Total calculado dos itens. Requer >= 1 item. Status muda para AguardandoAprovacao. | Must |
| US-006 | Como Admin, quero aprovar o orçamento para iniciar a execução. | Status muda para EmExecucao. Estoque reservado atomicamente. Estoque insuficiente bloqueia aprovação. | Must |
| US-007 | Como Admin, quero cancelar uma OS para lidar com rejeições e abandonos. | Cancelamento possível de Recebida, EmDiagnostico, AguardandoAprovacao, EmExecucao. Estoque liberado se em execução. Motivo obrigatório em EmExecucao. | Must |
| US-008 | Como Admin, quero gerenciar o estoque de peças para manter o controle de disponibilidade. | CRUD com quantidade. Quantidade > 0. Soft delete quando sem OS ativas. | Must |
| US-009 | Como Admin, quero ver o tempo médio de execução por serviço para planejar a operação. | Endpoint de métricas. Média calculada de OS finalizadas. OS sem itens excluída. | Should |
| US-010 | Como Admin, quero gerenciar o catálogo de serviços para definir o que a oficina oferece. | CRUD de serviços. Desativação soft delete. Serviço referenciado não pode ser excluído. | Must |

### Mecânico

| ID | História | Critérios de Aceite | Prioridade |
|---|---|---|---|
| US-011 | Como Mecânico, quero iniciar o diagnóstico de uma OS para registrar que comecei a avaliação. | Status muda de Recebida para EmDiagnostico. | Must |
| US-012 | Como Mecânico, quero finalizar o serviço para indicar que o veículo está pronto. | Status muda de EmExecucao para Finalizada. | Must |

### Cliente

| ID | História | Critérios de Aceite | Prioridade |
|---|---|---|---|
| US-013 | Como Cliente, quero consultar o status da minha OS por placa e documento para acompanhar o andamento. | Consulta pública sem JWT. Retorna status atual e serviços. Identificação por placa + CPF/CNPJ. | Must |

## Priorização MoSCoW

### Must Have (Obrigatório — Entregáveis do Tech Challenge)

- Cadastro e gestão de clientes (CPF/CNPJ) e veículos
- Ciclo completo da OS (7 status, máquina de estados)
- Geração e aprovação de orçamento
- Gestão de estoque com reserva atômica
- Consulta pública de acompanhamento
- Autenticação JWT
- CRUD de serviços oferecidos
- Validação de dados sensíveis
- Testes com 90%+ nos domínios principais e 80%+ nos demais
- Dockerfile e docker-compose
- Documentação DDD (Event Storming, glossário, diagramas)

### Should Have (Desejável)

- Métricas de tempo médio de execução
- Alerta de estoque baixo (evento de domínio, log) — sem RF correspondente, depende de implementação
- Rate limiting nos endpoints
- Scanning de segurança (bandit, pip-audit, gitleaks, trivy)
- Relatório de vulnerabilidades
- Encriptação de PII (CPF/CNPJ) — TD-001
- Revogação de JWT (tabela blacklist + JTI) — TD-003
- Refresh tokens — TD-006
- Papel Mecânico diferenciado via Enum (RBAC) — TD-005
- Endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) — TD-002
- Transactional outbox para eventos de domínio — TD-011, TD-012
- Docker Compose secrets para JWT — TD-009

### Could Have (Opcional)

- Mutation testing (mutmut) como requisito hard — TD-015
- Contract testing (schemathesis)
- Logging estruturado com PII filtering
- Histórico de orçamentos (array JSONB) — TD-007
- Orçamentos complementares durante execução — TD-008
- Índices GIN para orçamento JSONB — TD-014
- Consentimento explícito LGPD — TD-004
- CSP headers — TD-010
- Notificações stub (LogNotificacaoAdapter) — TD-013

### Won't Have (Fora de Escopo)

- Front-end ou interface gráfica
- Notificações reais (push, email, SMS)
- Integração com sistemas externos
- Agendamento de serviços
- Pagamento ou faturamento

## Critérios de Sucesso

1. Requisitos funcionais RF-001 a RF-010 implementados e testados. RF-011 a RF-019 conforme estratégia de corte em tech-debt.md
2. Cobertura de testes >= 90% nos domínios principais (OS e Estoque), >= 80% nos demais
3. Docker-compose funcional com `docker-compose up` e migrações automáticas
4. Swagger UI acessível em desenvolvimento com todos os endpoints documentados
5. Consulta pública de acompanhamento funcional sem autenticação
6. Scanning de segurança sem vulnerabilidades críticas ou altas

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| SQLAlchemy imperative mapping com complexidade inesperada | Alto | Spike de 4h com go/no-go gates. Fallback para declarative mapping (ADR-006). |
| Deadlocks na reserva de estoque | Médio | Locks em ordem crescente de `item_id`. `NOWAIT` para falhar rápido. Testes de concorrência. |
| Cobertura de 90% nos domínios principais pode exigir tempo desproporcional em edge cases | Médio | Mutation testing para priorizar testes de maior valor. Metas por faixa, não globais. |
| Tempo insuficiente para todos os entregáveis | Alto | Priorização MoSCoW. Feature freeze S5. EMV (entrega mínima viável) definida. |
| CPF armazenado em texto plano (LGPD) | Baixo (MVP) | Documentado como risco aceito no relatório de vulnerabilidades. Remediação planejada com pgcrypto. |
