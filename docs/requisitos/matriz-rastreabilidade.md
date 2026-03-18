# Matriz de Rastreabilidade — Requisitos Funcionais

> **Status**: DRAFT — documento em elaboracao, sujeito a revisao pela equipe PytStop.

Esta matriz estende a [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) com historias de usuario, criterios de teste e ADRs vinculados. Baseada na disciplina Software Architecture — Aula 3.

## Matriz

| RF | Descricao | Historias de Usuario | Criterio de Teste | ADR Vinculado |
|---|---|---|---|---|
| RF-001 | Cadastro de cliente por CPF/CNPJ | US-001 | CPF/CNPJ validado algoritmicamente na criacao; duplicata retorna 409; dados mascarados em listagem | [ADR-010](../arquitetura/adr/010-validacao-documentos-brutils.md) |
| RF-002 | Vinculacao de veiculo a cliente | US-002 | Veiculo criado via endpoint do cliente; placa unica entre todos os clientes; formatos antigo e Mercosul aceitos | [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-003 | Criacao de OS com itens | US-003, US-004 | Cliente e veiculo devem existir; OS criada com status Recebida e zero itens; itens adicionados/removidos em Recebida ou EmDiagnostico; cada item referencia servico do catalogo | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md), [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-004 | Geracao automatica de orcamento | US-005 | Orcamento calculado dos itens da OS; objeto de valor imutavel em JSONB; requer >= 1 item; transiciona de EmDiagnostico para AguardandoAprovacao | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md) |
| RF-005 | Maquina de estados da OS (7+1 status) | US-006, US-007, US-011, US-012, US-014 | 7 status base com 9 transicoes; RF-016 adiciona 8o status com +3 transicoes; transicoes invalidas retornam 409; cancelamento em EmExecucao libera estoque | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md), [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-006 | Gestao de estoque (pecas e insumos) | US-008 | CRUD com controle de quantidade; reserva via `SELECT FOR UPDATE NOWAIT`; tudo-ou-nada; locks em ordem crescente de `item_id` | [ADR-008](../arquitetura/adr/008-bloqueio-pessimista-estoque.md) |
| RF-007 | Consulta publica de acompanhamento | US-013 | Consulta por placa + CPF/CNPJ sem autenticacao; retorna status atual e servicos com documento mascarado; multiplas OS retorna a mais recente | — |
| RF-008 | Tempo medio de execucao por servico | US-009 | Endpoint de metricas; media ponderada por tempo de execucao das OS finalizadas; OS sem itens excluida da agregacao | — |
| RF-009 | Autenticacao JWT | Requisito de plataforma — sem US associada | Login retorna token JWT HS256 (15 min); endpoints administrativos protegidos; papel no payload; enforcement explicito de algoritmo no decode | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-010 | CRUD de servicos oferecidos | US-010 | Cadastro, listagem, atualizacao e desativacao; servico referenciado por OS historicas nao pode ser excluido (soft delete via flag `ativo`) | [ADR-007](../arquitetura/adr/007-organizacao-contextos-delimitados.md) |
| RF-011 | Encriptacao de PII (CPF/CNPJ) | Requisito de plataforma — sem US associada | CPF/CNPJ armazenado com encriptacao; decriptacao sob demanda para consultas autorizadas | — |
| RF-012 | Revogacao de JWT | Requisito de plataforma — sem US associada | Tabela de blacklist com JTI; token revogado antes do `exp` e rejeitado; logout invalida o token corrente | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-013 | Refresh tokens | Requisito de plataforma — sem US associada | Endpoint de renovacao via refresh token com rotacao; refresh token com TTL configuravel | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-014 | RBAC com Enum Papel | Requisito de plataforma — sem US associada | Papeis Admin e Mecanico com permissoes diferenciadas; Mecanico nao cadastra clientes nem gerencia estoque | [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) |
| RF-015 | Endpoints LGPD Art. 18 | Requisito de plataforma — sem US associada | Endpoints para acesso, portabilidade (export JSON) e exclusao (anonimizacao) dos dados pessoais; operacao cross-contexto | — |
| RF-016 | Orcamento complementar | Requisito de plataforma — sem US associada | Transicao EmExecucao → AguardandoAprovacaoComplementar → EmExecucao para servicos adicionais durante execucao | [ADR-003](../arquitetura/adr/003-arquitetura-ddd-onion.md) |
| RF-017 | Historico de orcamentos | Requisito de plataforma — sem US associada | Orcamentos anteriores mantidos como array JSONB com timestamp; consulta do historico via endpoint da OS | — |
| RF-018 | Transactional outbox | Requisito de plataforma — sem US associada | Eventos de dominio persistidos em tabela `outbox` na mesma transacao; background task despacha eventos | — |
| RF-019 | Consentimento explicito | Requisito de plataforma — sem US associada | Registro de consentimento do cliente para tratamento de dados pessoais; revogacao via endpoint | — |

## Verificacoes de Integridade

- **Cobertura**: todos os 19 RFs de [requisitos.md](requisitos.md) estao presentes na matriz
- **Referencias validas**: todos os ADRs referenciados existem no diretorio `docs/arquitetura/adr/`
- **Criterios de teste**: todos os RFs possuem criterios de aceitacao verificaveis

## Referencia Cruzada

A [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) mapeia RF → Secao do Tech Challenge → Contexto Delimitado → Status no Fluxo.
