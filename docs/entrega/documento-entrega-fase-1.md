# Documento de Entrega — Fase 1

## FIAP Pos Tech — Software Architecture (15SOAT)

---

### Dados do Grupo

| Campo | Valor |
|---|---|
| Nome do grupo | PytStop |
| Turma | 15SOAT |

#### Membros

| Nome | Discord |
|---|---|
| João Amaral | jbamaral |
| Allan Aurélio | PLACEHOLDER |
| Carlos Silva | PLACEHOLDER |
| Guilherme Sousa | PLACEHOLDER |
| Nicolas Gerbi | PLACEHOLDER |

---

### Links

| Recurso | URL |
|---|---|
| Repositório | [github.com/jbamaral/postech-sw-arch-p1](https://github.com/jbamaral/postech-sw-arch-p1) |
| Documentação | `docs/` no repositório |
| Event Storming (Miro) | PLACEHOLDER |
| Domain Storytelling (Miro) | PLACEHOLDER |
| Vídeo de apresentação | PLACEHOLDER |

---

### Documentação DDD

#### Event Storming

Workshop simulado com 5 especialistas de domínio fictícios, seguindo a metodologia de Alberto Brandolini em 10 passos progressivos.

O workshop produziu:

- 22 eventos de domínio no brainstorming, 14 promovidos ao modelo formal
- 12 comandos mapeados com seus atores (Admin, Mecanico, Sistema)
- 6 hotspots (pontos de dor) e 3 eventos pivotais
- 5 politicas reactivas, 5 read models, 4 sistemas externos
- 4 agregados distribuídos em 5 contextos delimitados

Os 3 eventos pivotais que marcam mudança de fase:

| Evento Pivotal | Transição |
|---|---|
| OrdemRecebida | Recepcão para Diagnóstico |
| OrcamentoAprovado | Orçamento para Execução |
| OrdemFinalizada | Execução para Entrega |

Diagramas Mermaid disponíveis em `docs/arquitetura/event-storming/workshop-event-storming.md`.

#### Domain Storytelling

5 entrevistas simuladas com especialistas de domínio de uma oficina mecânica fictícia (Auto Mecânica São Carlos), cobrindo todos os papéis do negócio:

| Entrevista | Especialista | Foco |
|---|---|---|
| 1 | Seu Carlos (Dono) | Visão geral do fluxo, regras não escritas |
| 2 | Dona Marta (Recepcionista) | Recepção, cadastro, comunicação |
| 3 | Reginaldo (Mecânico) | Diagnóstico, execução técnica |
| 4 | Leandro (Orçamentista) | Orçamento, estoque, fornecedores |
| 5 | Fábio (Cliente) | Perspectiva do cliente, dores |

Das entrevistas foram extraídos termos de domínio, 9 entidades/agregados, 5 objetos de valor, 11 estados de OS, 5 papéis e 18 regras implícitas de negócio.

5 diagramas egon.io disponíveis em `docs/arquitetura/domain-storytelling/`.

#### Linguagem Ubíqua

Glossário completo com termos do domínio mapeados para identificadores no código, seguindo o modelo híbrido (ADR-009): termos de negócio em português sem acentos, sufixos técnicos em inglês.

| Termo do Domínio | Código | Contexto |
|---|---|---|
| Ordem de Serviço (OS) | `OrdemDeServico` | Agregado raiz — ciclo completo de atendimento |
| Status da Ordem | `StatusOrdem` | Enum com 8 estados (7 base + complementar) |
| Orçamento | `Orcamento` | Objeto de valor imutável (JSONB) |
| Item da OS | `ItemDaOrdem` | Entidade filha — serviço + peça opcional |
| Máquina de Status | `MaquinaDeStatus` | Colaborador stateless — valida transições |
| Cliente | `Cliente` | Agregado raiz — pessoa física ou jurídica |
| Veículo | `Veiculo` | Entidade filha do Cliente |
| CPF / CNPJ | `CPF`, `CNPJ` | Objetos de valor com validação algorítmica |
| Placa | `Placa` | Objeto de valor — única entre clientes |
| Serviço Oferecido | `ServicoOferecido` | Agregado raiz — catálogo de serviços |
| Peça / Insumo | `ItemEstoque` | Agregado raiz — bloqueio pessimista |
| Dinheiro | `Dinheiro` | VO compartilhado (Decimal, 2 casas, BRL) |
| Usuário | `Usuario` | Entidade do contexto Autenticação |
| Papel | `Papel` | Enum (Admin, Mecanico) |
| Unidade de Trabalho | `UnitOfWork` | Gerencia transações cross-contexto |

Glossário completo: `docs/requisitos/glossario.md`.

#### Mapa de Contextos

5 contextos delimitados com padrões de integração DDD:

| Contexto | Classificação | Agregados | Integração |
|---|---|---|---|
| Ordem de Serviço | Principal | `OrdemDeServico` | Consome de todos os demais |
| Cliente + Veículo | Suporte | `Cliente`, `Veiculo` | Customer-Supplier para OS |
| Catálogo de Serviços | Suporte | `ServicoOferecido` | OHS / Linguagem Publicada |
| Estoque | Principal | `ItemEstoque` | OHS / Linguagem Publicada |
| Autenticação | Genérico | `Usuario` | Middleware JWT (cross-cutting) |

Padrões de integração:

- **Customer-Supplier**: Cliente fornece dados para OS via `ClientePort`
- **Open Host Service (OHS)**: Catálogo e Estoque expõem serviços via `CatalogoPort` e `EstoquePort`
- **Consulta reversa**: Contextos Cliente e Estoque consultam OS ativas antes de permitir exclusão (portas `OrdemDeServicoPort`)
- **Comunicação**: toda in-process via portas e adaptadores, wiring de DI em `main.py`

Detalhes: `docs/arquitetura/mapa-contextos.md`.

#### Modelo de Domínio

Principais agregados e seus relacionamentos:

**OrdemDeServico** (agregado raiz): contém `ItemDaOrdem[]` como entidades filhas e `Orcamento` como objeto de valor. A `MaquinaDeStatus` é colaborador stateless que valida transições entre os 8 estados. A OS possui 12 transições válidas (9 base + 3 do orçamento complementar).

**Cliente** (agregado raiz): contém `Veiculo[]` como entidades filhas. Identificado por `CPF` ou `CNPJ` (objetos de valor com validação algorítmica). Veículo não tem ciclo de vida independente.

**ItemEstoque** (agregado raiz): peça ou insumo com controle de quantidade. Reserva atômica via `SELECT FOR UPDATE NOWAIT` com locks em ordem crescente de `item_id` para prevenção de deadlocks.

**ServicoOferecido** (agregado raiz): serviço disponível no catálogo com preço (`Dinheiro`). Soft delete para preservar referências de OS históricas.

**Usuario** (entidade): operador do sistema com `Papel` (Admin ou Mecanico).

Diagramas de classes: `docs/arquitetura/modelo-dominio.md`.

---

### Arquitetura

#### Visão Geral (RFC-001)

Monolito modular com DDD e Onion Architecture. Cada contexto delimitado é um módulo Python com 4 camadas:

```
contexto/
├── dominio/         # Entidades, VOs, eventos, exceções, portas
├── aplicacao/       # Casos de uso, portas cross-contexto, DTOs
├── infraestrutura/  # Repositórios SQLAlchemy, adaptadores
└── interfaces/      # Routers FastAPI, schemas Pydantic
```

Regra de dependência estrita: camadas internas nunca importam camadas externas. O domínio não conhece infraestrutura nem framework.

**Stack**: Python 3.12, FastAPI, SQLAlchemy 2.0 (imperative mapping), PostgreSQL 16, Alembic, pytest.

#### Decisões Arquiteturais

| ADR | Decisão |
|---|---|
| ADR-003 | DDD + Onion Architecture com 4 camadas por contexto |
| ADR-006 | Mapeamento imperativo do SQLAlchemy (`map_imperatively()`) para manter entidades como classes Python puras |
| ADR-008 | Bloqueio pessimista (`SELECT FOR UPDATE NOWAIT`) para reserva atômica de estoque com prevenção de deadlocks |
| ADR-009 | Modelo híbrido de linguagem: negócio em PT, padrões técnicos em EN |

#### Máquina de Estados da OS

8 status com 12 transições válidas:

```
Recebida → EmDiagnostico → AguardandoAprovacao → EmExecucao → Finalizada → Entregue
                                                      ↕
                                         AguardandoAprovacaoComplementar
Cancelamento possível a partir de: Recebida, EmDiagnostico, AguardandoAprovacao, EmExecucao
```

Cancelamento em EmExecucao libera estoque reservado. Estados terminais: Entregue e Cancelada.

#### Autenticação

JWT HS256 com tokens de 15 min, revogação via JTI, refresh tokens com rotação, RBAC com 2 papéis (Admin, Mecanico), rate limiting por endpoint.

Detalhes: `docs/arquitetura/rfc/rfc-001-design-do-sistema.md` e `docs/arquitetura/adr/`.

---

### Requisitos

#### Requisitos Funcionais (Must-Have)

| RF | Descrição |
|---|---|
| RF-001 | Cadastro de cliente por CPF/CNPJ com validação algorítmica |
| RF-002 | Vinculação de veículo a cliente (placa única) |
| RF-003 | Criação de OS com itens (referência a catálogo + estoque) |
| RF-004 | Geração automática de orçamento (JSONB imutável) |
| RF-005 | Máquina de estados da OS (7+1 status, 12 transições) |
| RF-006 | Gestão de estoque com reserva pessimista atômica |
| RF-007 | Consulta pública de acompanhamento (placa + documento) |
| RF-008 | Tempo médio de execução por serviço |
| RF-009 | Autenticação JWT com revogação e refresh tokens |
| RF-010 | CRUD de serviços oferecidos (soft delete) |

Requisitos adicionais (Should/Could): encriptação de PII (RF-011), endpoints LGPD Art. 18 (RF-015), orçamento complementar (RF-016), histórico de orçamentos (RF-017), transactional outbox (RF-018), consentimento (RF-019).

17 regras de negócio e 13 requisitos não-funcionais documentados.

Detalhes: `docs/requisitos/requisitos.md`.

#### Jornada da Solução

A solução digitaliza o ciclo da Ordem de Serviço com 3 objetivos:

1. **Eliminar papéis e planilhas** — 100% digital (resolve hotspots H1 a H4)
2. **Consulta pública de status** — cliente acompanha sem ligar (resolve H5)
3. **Estoque com reserva atômica** — evitar falta de peças durante execução (resolve H4)

| # | Etapa | Persona |
|---|---|---|
| 01 | Cadastrar cliente com CPF/CNPJ | Admin |
| 02 | Adicionar veículo ao cliente | Admin |
| 03 | Criar OS associando cliente e veículo | Admin |
| 04 | Iniciar diagnóstico | Mecânico |
| 05 | Adicionar itens à OS | Admin / Mecânico |
| 06 | Gerar orçamento | Admin |
| 07 | Aprovar orçamento (reserva estoque) | Admin |
| 08 | Executar serviços | Mecânico |
| 09 | Finalizar serviço | Mecânico |
| 10 | Registrar entrega | Admin |
| 11 | Consultar status (placa + documento) | Cliente |

Detalhes: `docs/requisitos/levantamento-de-requisitos.md`.

---

### Análise de Vulnerabilidades

#### Metodologia

Referência OWASP API Security Top 10 (2023). Ferramentas planejadas: SonarQube (SAST/qualidade), OWASP ZAP (DAST), bandit (SAST Python), pip-audit (dependências), gitleaks (segredos), trivy (imagem Docker).

#### Achados

| # | Severidade | Descrição | Status |
|---|---|---|---|
| 1 | Baixa | CPF/CNPJ em texto plano (CVSS 3.1) | Em remediação — encriptação via pgcrypto (RF-011) |
| 2 | Informativo | Sem endpoints LGPD Art. 18 | Em remediação (RF-015) |
| 3 | Informativo | Sem consentimento explícito | Risco aceito no MVP |
| 4 | Informativo | JWT sem revogação/refresh (CVSS 2.0) | Em remediação (RF-012, RF-013) |

#### Conformidade LGPD

| Aspecto | Status |
|---|---|
| Mascaramento de PII em respostas | Planejado |
| Remoção de PII em logs (structlog) | Planejado |
| Encriptação de CPF/CNPJ | Em remediação (RF-011) |
| Direitos do titular (Art. 18) | Em remediação (RF-015) |
| Consentimento | Planejado (RF-019) |

Recomendações para produção: WAF com rate limiting, migrar segredo JWT para KMS, CSP headers, mecanismo de consentimento.

Detalhes: `docs/seguranca/relatorio-vulnerabilidades.md`.

---

### Código

- Dockerfile multi-stage + `docker-compose.yml`
- APIs RESTful documentadas via Swagger/OpenAPI
- Testes automatizados: meta 90%+ nos domínios principais (OS, Estoque), 80%+ nos demais
- Migrações automáticas via Alembic no startup

---

### Referência de Documentos

| Documento | Caminho |
|---|---|
| Glossário (Linguagem Ubíqua) | `docs/requisitos/glossario.md` |
| Mapa de Contextos | `docs/arquitetura/mapa-contextos.md` |
| Modelo de Domínio | `docs/arquitetura/modelo-dominio.md` |
| Workshop Event Storming | `docs/arquitetura/event-storming/workshop-event-storming.md` |
| Especialistas de Domínio | `docs/arquitetura/domain-storytelling/especialistas-de-dominio.md` |
| Diagramas Domain Storytelling | `docs/arquitetura/domain-storytelling/` |
| RFC-001: Design do Sistema | `docs/arquitetura/rfc/rfc-001-design-do-sistema.md` |
| ADRs (000-011) | `docs/arquitetura/adr/` |
| Requisitos (RF, RNF, RN) | `docs/requisitos/requisitos.md` |
| Levantamento de Requisitos | `docs/requisitos/levantamento-de-requisitos.md` |
| PRD | `docs/requisitos/prd.md` |
| Relatório de Vulnerabilidades | `docs/seguranca/relatorio-vulnerabilidades.md` |
| Entrega Fase 1 (links) | `docs/entrega/entrega-fase-1.md` |

---

### Geração do PDF

```bash
pandoc docs/entrega/documento-entrega-fase-1.md -o documento-entrega-fase-1.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.5cm \
  -V mainfont="DejaVu Sans"
```
