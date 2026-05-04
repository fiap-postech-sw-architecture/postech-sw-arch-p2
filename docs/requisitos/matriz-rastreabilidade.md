# Matriz de Rastreabilidade — Requisitos Funcionais

> [↑ Raiz do projeto](../../README.md) · [↑ Requisitos](README.md)

> **Versão**: 1.0 — Fase 1 MVP.

Esta matriz estende a [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) com histórias de usuário, critérios de teste e ADRs vinculados.

## Matriz

| RF | Descrição | Histórias de Usuário | Critério de Teste | ADR Vinculado |
|---|---|---|---|---|
| RF-001 | Cadastro de cliente por CPF/CNPJ | US-001 | CPF/CNPJ validado algoritmicamente na criação; duplicata retorna 409; dados mascarados em listagem | [ADR-010](../arquitetura/adr/010-validacao-documentos-brutils.md) |
| RF-002 | Vinculação de veículo a cliente | US-002 | Veículo criado via endpoint do cliente; placa única entre todos os clientes; formatos antigo e Mercosul aceitos | [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-003 | Criação de OS com itens | US-003, US-004 | Cliente deve existir e veículo deve pertencer ao cliente informado; OS criada com status Recebida e zero itens; itens adicionados/removidos em Recebida ou EmDiagnostico; cada item referencia serviço do catálogo | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md), [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-004 | Geração automática de orçamento | US-005 | Orçamento calculado dos itens da OS; objeto de valor imutável em JSONB; requer >= 1 item; transiciona de EmDiagnostico para AguardandoAprovacao | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md) |
| RF-005 | Máquina de estados da OS (7+1 status) | US-006, US-007, US-011, US-012, US-014 | 7 status base com 9 transições; RF-016 adiciona 8o status com +3 transições; transições inválidas retornam 409; cancelamento em EmExecucao libera estoque | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md), [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-006 | Gestão de estoque (peças e insumos) | US-008 | CRUD com controle de quantidade; reserva via `SELECT FOR UPDATE NOWAIT`; tudo-ou-nada; locks em ordem crescente de `item_id` | [ADR-008](../arquitetura/adr/008-bloqueio-pessimista-estoque.md) |
| RF-007 | Consulta pública de acompanhamento | US-013 | Consulta por placa + CPF/CNPJ sem autenticação; retorna status atual e serviços com documento mascarado; múltiplas OS retorna a mais recente | — |
| RF-008 | Tempo médio de execução por serviço | US-009 | Endpoint de métricas; média ponderada por tempo de execução das OS finalizadas; OS sem itens excluída da agregação | — |
| RF-009 | Autenticação JWT | Requisito de plataforma — sem US associada | Login retorna token JWT HS256 (15 min); endpoints administrativos protegidos; papel no payload; enforcement explícito de algoritmo no decode | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-010 | CRUD de serviços oferecidos | US-010 | Cadastro, listagem, atualização e desativação; serviço referenciado por OS históricas não pode ser excluído (soft delete via flag `ativo`) | [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-011 | Encriptação de PII (CPF/CNPJ) | Requisito de plataforma — sem US associada | CPF/CNPJ armazenado com encriptação; decriptação sob demanda para consultas autorizadas | — |
| RF-012 | Revogação de JWT | Requisito de plataforma — sem US associada | Tabela de blacklist com JTI; token revogado antes do `exp` e rejeitado; logout invalida o token corrente | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-013 | Refresh tokens | Requisito de plataforma — sem US associada | Endpoint de renovação via refresh token com rotação; refresh token com TTL configurável | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-014 | RBAC com Enum Papel | Requisito de plataforma — sem US associada | Papéis Admin e Mecânico com permissões diferenciadas; Mecânico não cadastra clientes nem gerencia estoque | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-015 | Endpoints LGPD Art. 18 | Requisito de plataforma — sem US associada | Endpoints para acesso, portabilidade (export JSON) e exclusão (anonimização) dos dados pessoais; operação cross-contexto | — |
| RF-016 | Orçamento complementar | Requisito de plataforma — sem US associada | Transição EmExecucao → AguardandoAprovacaoComplementar → EmExecucao para serviços adicionais durante execução | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md) |
| RF-017 | Histórico de orçamentos | Requisito de plataforma — sem US associada | Orçamentos anteriores mantidos como array JSONB com timestamp; consulta do histórico via endpoint da OS | — |
| RF-018 | Transactional outbox | Requisito de plataforma — sem US associada | Eventos de domínio persistidos em tabela `outbox` na mesma transação; background task despacha eventos | — |
| RF-019 | Consentimento explícito | Requisito de plataforma — sem US associada | Registro de consentimento do cliente para tratamento de dados pessoais; revogação via endpoint | — |

## Requisitos Não-Funcionais (Rastreabilidade)

| RNF | Descrição | ADR Vinculado | Disciplina |
|---|---|---|---|
| RNF-001 a RNF-013 | Requisitos de produto, organizacionais e externos | Ver [requisitos.md](requisitos.md) | DDD, SW-Arch |
| RNF-014 | Análise estática de segurança (bandit) sem achados de severidade alta no CI | [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Dev-Seguro (Aulas 04–05) |
| RNF-015 | Dependências auditadas mensalmente (pip-audit); zero vulnerabilidades críticas | [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Dev-Seguro (Aula 03) |
| RNF-016 | SBOM gerado via CycloneDX a cada release | [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Dev-Seguro (Aula 03) |

## Verificações de Integridade

- **Cobertura**: todos os 19 RFs de [requisitos.md](requisitos.md) estão presentes na matriz
- **Cobertura RNF**: RNF-014 a RNF-016 rastreados com ADRs 011–012
- **Referências válidas**: todos os ADRs referenciados existem no diretório `docs/arquitetura/adr/`
- **Critérios de teste**: todos os RFs possuem critérios de aceitação verificáveis

## Referência Cruzada

A [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) mapeia RF → Seção do Tech Challenge → Contexto Delimitado → Status no Fluxo.

> [↑ Raiz do projeto](../../README.md) · [↑ Requisitos](README.md)
