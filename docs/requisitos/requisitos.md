# Requisitos — Sistema Integrado de Atendimento e Execução de Serviços

> **Status**: DRAFT — documento em elaboração, sujeito a revisão pela equipe PytStop.

## Requisitos Funcionais

| RF | Descrição | Critérios de Aceite | Origem Tech Challenge |
|---|---|---|---|
| RF-001 | Cadastro de cliente por CPF/CNPJ | CPF/CNPJ validado algoritmicamente na criação. Um cliente por documento (unique). Resposta 409 se duplicado. | "Identificação do cliente por CPF/CNPJ" + "CRUD de clientes" |
| RF-002 | Vinculação de veículo a cliente | Veículo criado via `POST /api/v1/clientes/{id}/veiculos` com placa, marca, modelo, ano. Placa única entre todos os clientes. Veículo sem ciclo de vida independente. | "Cadastro de veículo (placa, marca, modelo, ano)" + "CRUD de veículos" |
| RF-003 | Criação de OS com itens | OS criada com status Recebida e zero itens. Itens adicionados/removidos em Recebida ou EmDiagnostico. Cada item referencia um serviço do catálogo e opcionalmente um item de estoque. | "Inclusão dos serviços solicitados" + "Possibilidade de incluir peças e insumos" |
| RF-004 | Geração automática de orçamento | Orçamento calculado a partir dos itens da OS. Objeto de valor imutável armazenado como JSONB. Requer pelo menos 1 item. Transiciona de EmDiagnostico para AguardandoAprovacao. | "Orçamento gerado automaticamente com base nos serviços e peças" |
| RF-005 | Máquina de estados da OS (7+1 status) | 7 status base: Recebida, EmDiagnostico, AguardandoAprovacao, EmExecucao, Finalizada, Entregue, Cancelada. 9 transições base. RF-016 adiciona AguardandoAprovacaoComplementar (8º status, +3 transições). Transições inválidas retornam 409. Cancelamento libera estoque se em EmExecucao. | "Status da OS" + "Alteração automática dos status" |
| RF-006 | Gestão de estoque (peças e insumos) | CRUD de itens de estoque com controle de quantidade. Reserva via `SELECT FOR UPDATE NOWAIT` na aprovação do orçamento. Tudo-ou-nada. Locks em ordem crescente de `item_id`. | "CRUD de peças e insumos, com controle de estoque" |
| RF-007 | Consulta pública de acompanhamento | Consulta por placa + CPF/CNPJ sem autenticação. Retorna status atual da OS e serviços incluídos. Se houver múltiplas OS para a mesma placa+documento, retorna a mais recente (maior `criado_em`). | "Permitir consulta por parte do cliente via API" |
| RF-008 | Tempo médio de execução por serviço | Endpoint `GET /api/v1/ordens-de-servico/metricas`. Calcula média ponderada por tempo de execução das OS finalizadas. OS sem itens excluída da agregação. | "Monitoramento do tempo médio de execução dos serviços" |
| RF-009 | Autenticação JWT | Login com credenciais retorna token JWT HS256 (15 min). Endpoints administrativos protegidos. Papel (Enum) no payload. Enforcement explícito de algoritmo no decode. | "Implementação de autenticação JWT para APIs administrativas" |
| RF-010 | CRUD de serviços oferecidos | Cadastro, listagem, atualização e desativação de serviços do catálogo. Serviço referenciado por OS históricas não pode ser excluído (soft delete via flag `ativo`). | "CRUD de serviços" |
| RF-011 | Encriptação de PII (CPF/CNPJ) | CPF/CNPJ armazenado com encriptação (pgcrypto ou app-level). Decriptação sob demanda para consultas autorizadas. | LGPD Art. 46 |
| RF-012 | Revogação de JWT | Tabela de blacklist com JTI. Token revogado antes do `exp` é rejeitado. Logout invalida o token corrente. | Segurança |
| RF-013 | Refresh tokens | Endpoint de renovação de token via refresh token com rotação. Refresh token com TTL configurável. | Segurança |
| RF-014 | RBAC com Enum Papel | Papéis Admin e Mecanico com permissões diferenciadas. Mecânico não pode cadastrar clientes nem gerenciar estoque. | Auth |
| RF-015 | Endpoints LGPD Art. 18 | Endpoints para acesso, portabilidade (export JSON) e exclusão (anonimização) dos dados pessoais do cliente. Cross-contexto. | LGPD Art. 18 |
| RF-016 | Orçamento complementar | Transição EmExecucao → AguardandoAprovacaoComplementar → EmExecucao para serviços adicionais durante execução. | Domínio |
| RF-017 | Histórico de orçamentos | Orçamentos anteriores mantidos como array JSONB com timestamp. Consulta do histórico via endpoint da OS. | Domínio (TD-002) |
| RF-018 | Transactional outbox | Eventos de domínio persistidos em tabela `outbox` na mesma transação. Background task despacha eventos. | Observabilidade |
| RF-019 | Consentimento explícito | Registro de consentimento do cliente para tratamento de dados pessoais. Revogação via endpoint. | LGPD (TD-001) |

## Requisitos Não-Funcionais

Classificação por taxonomia:

- **Produto (DEUS)**: Dependabilidade, Eficiência, Usabilidade, Segurança
- **Organizacionais (DOA)**: Desenvolvimento, Operacionais, Ambientais
- **Externos (LER)**: Legais, Éticos, Reguladores

| RNF | Categoria | Categoria RNF (Taxonomia) | Descrição | MoSCoW |
|---|---|---|---|---|
| RNF-001 | Desempenho | Eficiência (Produto) | Endpoints de leitura respondem em < 500ms (p95) com até 1000 registros. | Must |
| RNF-002 | Segurança | Segurança (Produto) | Autenticação JWT HS256 com tokens de 15 min. Senhas com 12+ caracteres, rejeição de top-10000 comuns, lockout após 5 falhas. | Must |
| RNF-003 | Segurança | Segurança (Produto) | Rate limiting: 5/min login, 10/min consulta pública, 60/min global (por IP). | Should |
| RNF-003a | Segurança | Segurança (Produto) | Consulta pública (`/acompanhamento`) retorna resposta genérica quando combinação placa+documento não existe, para dificultar enumeração. | Should |
| RNF-004 | Segurança | Segurança (Produto) | Headers: X-Content-Type-Options, X-Frame-Options, HSTS, Cache-Control, X-Request-ID. | Should |
| RNF-005 | Segurança | Segurança (Produto) | CORS com whitelist configurável. `allow_origins=["*"]` proibido. | Should |
| RNF-006 | Segurança | Segurança (Produto) | Mass assignment prevenido com Pydantic `extra="forbid"`. | Must |
| RNF-007 | Segurança | Segurança (Produto) | Swagger UI desabilitado em produção (`ENVIRONMENT=production` → 404). | Must |
| RNF-008 | Privacidade | Legais (Externos) | CPF/CNPJ mascarado em respostas de listagem. PII removido de logs via processador structlog. | Must |
| RNF-009 | Qualidade | Desenvolvimento (Organizacionais) | Cobertura de testes: 90%+ nos domínios principais (Ordem de Serviço e Estoque), 80%+ nos demais domínios, 65%+ em infraestrutura/interfaces. | Must |
| RNF-010 | Qualidade | Desenvolvimento (Organizacionais) | Scanning de segurança: SonarQube (SAST/qualidade), OWASP ZAP (DAST), bandit (SAST Python), pip-audit (dependências), gitleaks (segredos), trivy (imagem Docker). | Should |
| RNF-011 | Infraestrutura | Operacionais (Organizacionais) | Dockerfile multi-stage + docker-compose.yml. Migrações automáticas no startup (Alembic). | Must |
| RNF-012 | API | Usabilidade (Produto) | RESTful, documentada via Swagger/OpenAPI. Paginação offset-based (padrão 20, máximo 100). | Must |
| RNF-013 | Observabilidade | Operacionais (Organizacionais) | Logging estruturado (structlog JSON). Request ID propagado. Transições de status e reservas de estoque logadas em INFO. | Could |
| RNF-014 | Segurança | Desenvolvimento (Organizacionais) | Análise estática de segurança (bandit) deve passar sem findings de severidade alta no CI. | Should |
| RNF-015 | Segurança | Desenvolvimento (Organizacionais) | Dependências auditadas mensalmente via pip-audit. Zero vulnerabilidades críticas em produção. | Should |
| RNF-016 | Segurança | Operacionais (Organizacionais) | SBOM (Software Bill of Materials) gerado via CycloneDX a cada release. [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md). | Could |

## Regras de Negócio

| RN | Descrição | Contexto |
|---|---|---|
| RN-001 | Transições de status da OS seguem máquina de estados com 7 status base e 9 transições base (8 status e 12 transições com RF-016). Transição inválida levanta `TransicaoStatusInvalidaException` (409). Ver [RFC-001 §4](../arquitetura/rfc/rfc-001-design-do-sistema.md) para diagrama. | Ordem de Serviço |
| RN-002 | Cancelamento possível a partir de Recebida, EmDiagnostico, AguardandoAprovacao e EmExecucao. Bloqueado em estados terminais (Entregue, Cancelada) e em Finalizada (que só transita para Entregue). Motivo obrigatório em EmExecucao; opcional nos demais. | Ordem de Serviço |
| RN-003 | Cancelamento em EmExecucao libera estoque reservado. Nos demais status, sem efeitos colaterais de estoque. | Ordem de Serviço / Estoque |
| RN-004 | Estoque reservado no momento da aprovação do orçamento (AguardandoAprovacao → EmExecucao), não antes. Reserva tudo-ou-nada. | Estoque |
| RN-005 | Um cliente por CPF/CNPJ (unique). Tentativa de duplicata retorna 409. | Cliente |
| RN-006 | Placa é única entre todos os clientes. Duplicata retorna 409. | Cliente + Veículo |
| RN-007 | Itens da OS só podem ser adicionados/removidos nos status Recebida ou EmDiagnostico. | Ordem de Serviço |
| RN-008 | Orçamento requer pelo menos 1 item para ser gerado. | Ordem de Serviço |
| RN-009 | Cliente com OS ativas (Recebida, EmDiagnostico, AguardandoAprovacao ou EmExecucao) não pode ser excluído. Soft delete quando todas as OS estão finalizadas/entregues/canceladas. | Cliente |
| RN-010 | Serviço referenciado por ItemDaOrdem (incluindo OS históricas) não pode ser excluído. Pode ser desativado (soft delete). | Catálogo |
| RN-011 | ItemEstoque com quantidade > 0 ou referenciado por OS ativas não pode ser excluído. | Estoque |
| RN-012 | Bloqueio pessimista de estoque via `SELECT FOR UPDATE NOWAIT`. Locks adquiridos em ordem crescente de `item_id` para prevenir deadlocks. | Estoque |
| RN-013 | Orçamento é objeto de valor imutável. Se itens forem alterados antes da geração do orçamento, o próximo `gerar_orcamento()` produz um novo orçamento. Orçamentos anteriores mantidos como histórico (RF-017). Ver RN-016 para restrição pós-geração. | Ordem de Serviço |
| RN-014 | "Envio do orçamento ao cliente" = disponibilização via API para consulta e aprovação. Sem push notification/email no MVP. | Ordem de Serviço |
| RN-015 | Orçamentos complementares (serviços adicionais descobertos durante execução) transitam via status AguardandoAprovacaoComplementar (ver RF-016 e diagrama de estados). Estoque do complementar é reservado na aprovação. | Ordem de Serviço |
| RN-016 | Uma vez gerado o orçamento, itens não podem ser alterados. Para modificar itens, a OS deve ser cancelada e uma nova OS criada. | Ordem de Serviço |
| RN-017 | Para alterar quantidade de um item da OS, remover e adicionar novamente com a nova quantidade (não há endpoint de atualização de item). | Ordem de Serviço |

## Inventário de Endpoints API

Base: `/api/v1/`

### Autenticação

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/autenticacao/login` | Login com credenciais, retorna JWT + refresh token | Não |
| POST | `/autenticacao/registrar` | Registrar novo usuário (admin) | Admin |
| POST | `/autenticacao/refresh` | Renovar token via refresh token (RF-013) | Não |
| POST | `/autenticacao/logout` | Revogar token corrente (RF-012) | Admin |

### Clientes

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/clientes` | Cadastrar cliente | Admin |
| GET | `/clientes` | Listar clientes (paginado) | Admin |
| GET | `/clientes/{id}` | Detalhar cliente | Admin |
| PUT | `/clientes/{id}` | Atualizar cliente | Admin |
| DELETE | `/clientes/{id}` | Desativar cliente (soft delete, RN-009) | Admin |
| POST | `/clientes/{id}/veiculos` | Adicionar veículo ao cliente | Admin |
| GET | `/clientes/{id}/veiculos` | Listar veículos do cliente | Admin |
| DELETE | `/clientes/{id}/veiculos/{vid}` | Remover veículo (rejeitado se OS ativa) | Admin |

### Catálogo de Serviços

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/servicos` | Cadastrar serviço oferecido | Admin |
| GET | `/servicos` | Listar serviços (paginado) | Admin |
| GET | `/servicos/{id}` | Detalhar serviço | Admin |
| PUT | `/servicos/{id}` | Atualizar serviço | Admin |
| DELETE | `/servicos/{id}` | Desativar serviço (soft delete, RN-010) | Admin |

### Estoque

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/estoque` | Cadastrar item de estoque | Admin |
| GET | `/estoque` | Listar itens (paginado) | Admin |
| GET | `/estoque/{id}` | Detalhar item | Admin |
| PUT | `/estoque/{id}` | Atualizar item (nome, preço) | Admin |
| PATCH | `/estoque/{id}/quantidade` | Ajustar quantidade | Admin |
| DELETE | `/estoque/{id}` | Desativar item (soft delete, RN-011) | Admin |

### Ordens de Serviço

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/ordens-de-servico` | Criar OS (status: Recebida) | Admin |
| GET | `/ordens-de-servico` | Listar OS (paginado) | Admin |
| GET | `/ordens-de-servico/{id}` | Detalhar OS | Admin |
| POST | `/ordens-de-servico/{id}/itens` | Adicionar item (RN-007) | Admin |
| DELETE | `/ordens-de-servico/{id}/itens/{iid}` | Remover item (RN-007) | Admin |
| POST | `/ordens-de-servico/{id}/diagnostico` | Iniciar diagnóstico | Admin |
| POST | `/ordens-de-servico/{id}/orcamento` | Gerar orçamento (RN-008) | Admin |
| POST | `/ordens-de-servico/{id}/aprovacao` | Aprovar orçamento (RN-004) | Admin |
| POST | `/ordens-de-servico/{id}/finalizacao` | Finalizar serviço | Admin |
| POST | `/ordens-de-servico/{id}/entrega` | Registrar entrega | Admin |
| POST | `/ordens-de-servico/{id}/cancelamento` | Cancelar OS (RN-002, RN-003) | Admin |
| GET | `/ordens-de-servico/metricas` | Tempo médio de execução | Admin |

### Consulta Pública

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| GET | `/acompanhamento` | Consultar status por placa + documento | Não |

### Clientes — LGPD

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| GET | `/clientes/{id}/dados-pessoais` | Acesso aos dados pessoais (LGPD Art. 18, RF-015) | Admin |
| GET | `/clientes/{id}/dados-pessoais/exportar` | Portabilidade JSON (LGPD Art. 18, RF-015) | Admin |
| DELETE | `/clientes/{id}/dados-pessoais` | Anonimização (LGPD Art. 18, RF-015) | Admin |
| POST | `/clientes/{id}/consentimento` | Registrar consentimento (RF-019) | Admin |
| DELETE | `/clientes/{id}/consentimento` | Revogar consentimento (RF-019) | Admin |

### Ordens de Serviço — Orçamento Complementar

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | `/ordens-de-servico/{id}/orcamento-complementar` | Gerar orçamento complementar em EmExecucao (RF-016) | Admin |
| POST | `/ordens-de-servico/{id}/aprovacao-complementar` | Aprovar orçamento complementar (RF-016) | Admin |
| POST | `/ordens-de-servico/{id}/rejeicao-complementar` | Rejeitar orçamento complementar, retorna a EmExecucao (RF-016) | Admin |

### Saúde

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| GET | `/saude` | Health check | Não |

### Paginação

Todos os endpoints de listagem suportam paginação offset-based:
- `offset`: inteiro >= 0 (padrão: 0)
- `limit`: inteiro >= 1, <= 100 (padrão: 20)
- Resposta: `{"items": [...], "total": N}`

## Tabela de Rastreabilidade

| RF | Seção do Tech Challenge | Contexto Delimitado | Status no Fluxo |
|---|---|---|---|
| RF-001 | Gestão administrativa → CRUD de clientes | Cliente + Veículo | — |
| RF-002 | Fluxos principais → Cadastro de veículo | Cliente + Veículo | — |
| RF-003 | Fluxos principais → Criação da OS | Ordem de Serviço | Recebida |
| RF-004 | Fluxos principais → Orçamento gerado automaticamente | Ordem de Serviço | EmDiagnostico → AguardandoAprovacao |
| RF-005 | Acompanhamento da OS → Status da OS | Ordem de Serviço | Todos |
| RF-006 | Gestão administrativa → CRUD de peças e insumos | Estoque | — |
| RF-007 | Acompanhamento da OS → Consulta por parte do cliente | Ordem de Serviço / Cliente | — |
| RF-008 | Gestão administrativa → Tempo médio de execução | Ordem de Serviço | Finalizada |
| RF-009 | Segurança → Autenticação JWT | Autenticação | — |
| RF-010 | Gestão administrativa → CRUD de serviços | Catálogo de Serviços | — |
| RF-011 | LGPD Art. 46 → Encriptação PII | Cliente + Veículo | — |
| RF-012 | Segurança → Revogação JWT | Autenticação | — |
| RF-013 | Segurança → Refresh tokens | Autenticação | — |
| RF-014 | Segurança → RBAC diferenciado | Autenticação | — |
| RF-015 | LGPD Art. 18 → Direitos do titular | Cliente + Veículo / Cross-contexto | — |
| RF-016 | Orçamento complementar durante execução | Ordem de Serviço | EmExecucao |
| RF-017 | Histórico de orçamentos | Ordem de Serviço | — |
| RF-018 | Transactional outbox → Eventos de domínio | Cross-contexto | — |
| RF-019 | LGPD → Consentimento explícito | Cliente + Veículo | — |

Ver [Matriz de Rastreabilidade](matriz-rastreabilidade.md) — histórias de usuário, critérios de teste e ADRs vinculados.

## Premissas

1. "Alteração automática dos status" significa que o status muda como resultado direto de ações na API, não automação em background.
2. O tech challenge define 6 status; `Cancelada` é adição justificada para cobrir rejeição de orçamento e abandono ([ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md)).
3. Ver RN-014 e RN-015 para premissas sobre orçamentos.
