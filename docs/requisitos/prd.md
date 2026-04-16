# PRD — Sistema Integrado de Atendimento e Execução de Serviços

> **Versao**: 1.0 — Fase 1 MVP.

## Declaração do Problema

Uma oficina mecânica de médio porte opera com anotações manuais e planilhas, gerando erros na priorização de atendimentos, falhas no controle de peças, dificuldade no acompanhamento de serviços, perda de histórico e ineficiência nos fluxos de orçamento.

O sistema proposto é um MVP back-end que digitaliza a gestão de ordens de serviço, clientes, veículos, catálogo de serviços e estoque de peças, permitindo ao cliente acompanhar o andamento do serviço via API.

Ver [Levantamento de Requisitos](levantamento-de-requisitos.md) para a narrativa metodológica, [Refinamento Técnico](refinamento-tecnico.md) para a especificação técnica e [DoR/DoD](dor-dod.md) para os gates de qualidade.

## Objetivos

- Digitalizar o ciclo completo da Ordem de Serviço (recebimento → entrega)
- Aplicar Domain-Driven Design com Linguagem Ubíqua em português
- Controlar estoque de peças com reserva atômica na aprovação de orçamento
- Permitir consulta pública de status por placa + documento
- Garantir 90%+ de cobertura de testes nos domínios principais (Ordem de Serviço e Estoque) e 80%+ nos demais domínios
- Proteger endpoints administrativos com JWT

## Não-Objetivos

- Interface gráfica (front-end)
- Notificações reais (push, email, SMS)
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
| US-008 | Como Admin, quero gerenciar o estoque de peças para manter o controle de disponibilidade. | CRUD com quantidade. Quantidade > 0. Exclusão lógica (soft delete) quando sem OS ativas. | Must |
| US-009 | Como Admin, quero ver o tempo médio de execução por serviço para planejar a operação. | Endpoint de métricas. Média calculada de OS finalizadas. OS sem itens excluída. | Should |
| US-010 | Como Admin, quero gerenciar o catálogo de serviços para definir o que a oficina oferece. | CRUD de serviços. Desativação soft delete. Serviço referenciado não pode ser excluído. | Must |
| US-014 | Como Admin, quero registrar a entrega do veículo ao cliente para fechar o ciclo da OS. | Status muda de Finalizada para Entregue. Estado terminal — OS não aceita mais transições. | Must |

### Mecânico

| ID | História | Critérios de Aceite | Prioridade |
|---|---|---|---|
| US-011 | Como Mecânico, quero iniciar o diagnóstico de uma OS para registrar que comecei a avaliação. | Status muda de Recebida para EmDiagnostico. | Must |
| US-012 | Como Mecânico, quero finalizar o serviço para indicar que o veículo está pronto. | Status muda de EmExecucao para Finalizada. | Must |

### Cliente

| ID | História | Critérios de Aceite | Prioridade |
|---|---|---|---|
| US-013 | Como Cliente, quero consultar o status da minha OS por placa e documento para acompanhar o andamento. | Consulta pública sem JWT. Retorna status atual e serviços. Identificação por placa + CPF/CNPJ. Documento mascarado na resposta. Se múltiplas OS, retorna a mais recente. | Must |

## Priorização MoSCoW

### Must Have (Obrigatório — Entregáveis do Tech Challenge)

- Cadastro e gestão de clientes (CPF/CNPJ) e veículos
- Ciclo completo da OS (7 status base, máquina de estados)
- Geração e aprovação de orçamento
- Gestão de estoque com reserva atômica
- Consulta pública de acompanhamento
- Autenticação JWT
- CRUD de serviços oferecidos
- Validação de dados sensíveis
- Testes com 90%+ nos domínios principais e 80%+ nos demais
- Dockerfile e Docker Compose (`docker-compose.yml`)
- README.md com instruções de uso e objetivos
- Documentação DDD (Event Storming, glossário, diagramas)

### Should Have (Desejável)

- Métricas de tempo médio de execução
- Rate limiting nos endpoints
- Scanning de segurança (bandit, pip-audit, gitleaks, trivy)
- Relatório de vulnerabilidades
- Encriptação de dados pessoais identificáveis (PII): CPF/CNPJ — RF-011
- Papel Mecânico diferenciado via Enum (RBAC) — RF-014
- Docker Compose secrets para JWT

### Could Have (Opcional)

- Revogação de JWT (tabela blacklist + JTI) — RF-012
- Refresh tokens — RF-013
- Endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) — RF-015
- Orçamentos complementares durante execução — RF-016
- Histórico de orçamentos (array JSONB) — RF-017, TD-002
- Transactional outbox para eventos de domínio — RF-018
- Consentimento explícito LGPD — RF-019, TD-001
- Mutation testing (mutmut) como requisito hard — TD-006
- Contract testing (schemathesis)
- Logging estruturado com PII filtering
- Índices GIN para orçamento JSONB — TD-005
- CSP headers — TD-003
- Alerta de estoque baixo (evento de domínio, log)
- Notificações stub (LogNotificacaoAdapter) — TD-004

### Won't Have (Fora de Escopo)

- Front-end ou interface gráfica
- Notificações reais (push, email, SMS)
- Integração com sistemas externos
- Agendamento de serviços
- Pagamento ou faturamento

## Critérios de Sucesso

1. Requisitos funcionais Must Have (RF-001 a RF-010) implementados e testados. Should Have e Could Have conforme priorização MoSCoW acima
2. Cobertura de testes >= 90% nos domínios principais (OS e Estoque), >= 80% nos demais
3. Docker Compose funcional com `docker compose up` e migrações automáticas
4. Swagger UI acessível em desenvolvimento com todos os endpoints documentados
5. Consulta pública de acompanhamento funcional sem autenticação
6. Scanning de segurança sem vulnerabilidades críticas ou altas

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| SQLAlchemy imperative mapping com complexidade inesperada | Alto | Spike de 4h com go/no-go gates. Fallback para declarative mapping (ADR-006). |
| Deadlocks na reserva de estoque | Médio | Locks em ordem crescente de `item_id`. `NOWAIT` para falhar rápido. Testes de concorrência. |
| Cobertura de 90% nos domínios principais pode exigir tempo desproporcional em edge cases | Médio | Mutation testing para priorizar testes de maior valor. Metas por faixa, não globais. |
| Tempo insuficiente para todos os entregáveis | Alto | Priorização MoSCoW. Feature freeze na semana 5. Entrega mínima viável definida pelos Must Have. |
| CPF armazenado em texto plano (LGPD) | Baixo | Risco aceito no MVP. Documentado no relatório de vulnerabilidades. Encriptação via pgcrypto planejada (RF-011, Should Have). |
