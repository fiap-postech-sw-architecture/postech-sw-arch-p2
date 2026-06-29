# Matriz de Rastreabilidade — Requisitos Funcionais

> [↑ Raiz do projeto](../../README.md) · [↑ Requisitos](README.md)

> **Versão**: 1.1 — Junho/2026 (estende com os requisitos da fase 2: RF-020–024, RNF-017–024, RN-018–020).

Esta matriz estende a [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) com histórias de usuário, critérios de teste e ADRs vinculados. As seções "Fase 2" mapeiam cada requisito novo ao PR que o entregou, com a rastreabilidade detalhada em [gap-analysis-fase-2.md](fase2/gap-analysis-fase-2.md) e [entrega-fase-2.md §5](../entrega/fase2/entrega-fase-2.md#5-rastreabilidade-requisito--evidência).

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
| RF-018 | Transactional outbox | Requisito de plataforma — sem US associada | Eventos de domínio persistidos em tabela `outbox` na mesma transação; processo relay (`python -m relay`) despacha eventos (claim-then-deliver, LISTEN/NOTIFY) | — |
| RF-019 | Consentimento explícito | Requisito de plataforma — sem US associada | Registro de consentimento do cliente para tratamento de dados pessoais; revogação via endpoint | — |

### Fase 2 (RF-020 a RF-024)

Requisitos introduzidos pelo [desafio da fase 2](fase2/desafio-tech-fase-2.md); rastreabilidade detalhada (PR → evidência → bloco do vídeo) em [gap-analysis-fase-2.md §3](fase2/gap-analysis-fase-2.md#3-requisitos-novos-detalhados) e [entrega-fase-2.md §5](../entrega/fase2/entrega-fase-2.md#5-rastreabilidade-requisito--evidência).

| RF | Descrição | PR | Critério de Teste | ADR Vinculado |
|---|---|---|---|---|
| RF-020 | Abertura de OS com cliente, veículo, serviços e peças, retornando id único | [#15](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/15) | `POST /ordens-de-servico/` com itens cria OS + itens na mesma transação e responde 201 com `id`; payload sem itens segue válido (compat. fase 1); e2e `tests/integracao/test_api_e2e.py::TestCriacaoOsComItens` | [ADR-015](../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) |
| RF-021 | Consulta de status no vocabulário do challenge | [#14](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/14) | Rótulos `situacao` mapeados na apresentação sem renomear valores persistidos; expostos nos 3 schemas de resposta e no OpenAPI; `tests/unitarios/ordem_servico/test_presenters.py` | [ADR-015](../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) |
| RF-022 | Endpoint externo de aprovação/recusa de orçamento | [#16](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/16) | `POST /publico/ordens-de-servico/{id}/decisao-orcamento` com token próprio (não JWT admin) aprova/recusa em `AGUARDANDO_APROVACAO`; estado inválido → 409/422; teste negativo unit + e2e | [ADR-021](../arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md) |
| RF-023 | Listagem ordenada por prioridade de status, sem encerradas (exclusão lógica) | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Ordenação SQL por `CASE` de prioridade + `criado_em ASC` + desempate por `id`; exclusão lógica de `FINALIZADA`/`ENTREGUE`; `incluir_encerradas` para visão completa; teste-guarda em `tests/unitarios/ordem_servico/test_repository_os.py` | [ADR-021](../arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md) |
| RF-024 | Notificação de atualização de status por e-mail | [#17](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/17), [#56](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/56) | Transição grava `IntegrationEvent` na outbox na mesma transação; relay entrega o e-mail (claim-then-deliver, `FOR UPDATE SKIP LOCKED`, idempotência via `processed_events`, backoff/DLQ); falha de envio não bloqueia a transição; `tests/unitarios/ordem_servico/test_notificacoes.py` | [ADR-018](../arquitetura/adr/fase2/018-notificacao-email.md), [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md) |

Decisões de arquitetura sem RF/RNF formal mas implementadas na fase 2: **Transactional Outbox** (RF-018, [ADR-022](../arquitetura/adr/fase2/022-transactional-outbox-relay.md)), **observabilidade** — traces ([ADR-020](../arquitetura/adr/fase2/020-observabilidade-opentelemetry.md)) e métricas do relay ([ADR-024](../arquitetura/adr/fase2/024-metricas-prometheus.md)).

## Requisitos Não-Funcionais (Rastreabilidade)

| RNF | Descrição | ADR Vinculado | Disciplina |
|---|---|---|---|
| RNF-001 a RNF-013 | Requisitos de produto, organizacionais e externos | Ver [requisitos.md](requisitos.md) | DDD, SW-Arch |
| RNF-014 | Análise estática de segurança (bandit) sem achados de severidade alta no CI | [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) | Dev-Seguro (Aulas 04–05) |
| RNF-015 | Dependências auditadas mensalmente (pip-audit); zero vulnerabilidades críticas | [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Dev-Seguro (Aula 03) |
| RNF-016 | SBOM gerado via CycloneDX a cada release | [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) | Dev-Seguro (Aula 03) |

### Fase 2 (RNF-017 a RNF-024)

Rastreabilidade detalhada (PR → evidência → bloco do vídeo) em [gap-analysis-fase-2.md §3](fase2/gap-analysis-fase-2.md#3-requisitos-novos-detalhados) e [entrega-fase-2.md §5](../entrega/fase2/entrega-fase-2.md#5-rastreabilidade-requisito--evidência).

| RNF | Descrição | PR | ADR Vinculado | Disciplina |
|---|---|---|---|---|
| RNF-017 | Clean Architecture formalizada e verificada (import-linter) | [#12](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/12) | [ADR-015](../arquitetura/adr/fase2/015-arquitetura-alvo-fase-2.md) | Arquitetura de SW |
| RNF-018 | Testes dos fluxos críticos mantidos na evolução (gate 95%) | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13)–[#17](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/17) (transversal) | [ADR-005](../arquitetura/adr/005-estrategia-testes.md) | Qualidade de SW |
| RNF-019 | Dockerfile e docker-compose revisados (healthcheck do app) | [#18](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/18) | — | Containers (K8s) |
| RNF-020 | Manifests K8s: Deployment, Service, ConfigMap, Secret, HPA | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19) | [ADR-016](../arquitetura/adr/fase2/016-plataforma-kubernetes.md) | Containers (K8s) |
| RNF-021 | IaC: Terraform provisiona cluster e banco, documentado | [#20](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/20) | [ADR-016](../arquitetura/adr/fase2/016-plataforma-kubernetes.md), [ADR-017](../arquitetura/adr/fase2/017-provisionamento-banco.md) | IaC |
| RNF-022 | CI/CD: build, testes, imagem, deploy de banco e app, manifests | [#21](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/21) | [ADR-019](../arquitetura/adr/fase2/019-pipeline-cicd-deploy.md) | CI/CD |
| RNF-023 | HPA-readiness: probes e resources no Deployment | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19) | [ADR-016](../arquitetura/adr/fase2/016-plataforma-kubernetes.md) | Containers (K8s) |
| RNF-024 | Statelessness para escala horizontal (rate limiter Redis + pool dimensionado) | [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/19), [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/62), [#67](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/67) | [ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md) | Containers (K8s) |

## Regras de Negócio (Rastreabilidade)

Regras introduzidas na fase 2 ([gap-analysis-fase-2.md](fase2/gap-analysis-fase-2.md)); ratificadas no [ADR-021](../arquitetura/adr/fase2/021-aprovacao-externa-orcamento.md).

| RN | Regra | PR | Critério de Teste |
|---|---|---|---|
| RN-018 | Prioridade Em execução > Aguardando aprovação > Em diagnóstico > Recebida; mais antigas primeiro, desempate por id | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | `CASE` de prioridade + `criado_em ASC, id` em `src/ordem_servico/infraestrutura/repository.py` |
| RN-019 | Exclusão lógica de `FINALIZADA`/`ENTREGUE` (nenhum delete físico) | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Filtro `notin_(_ESTADOS_ENCERRADOS)`; `incluir_encerradas=true` prova que as linhas permanecem |
| RN-020 | Status extras: complementar ordena com Aguardando aprovação; `CANCELADA` excluída como encerrada | [#13](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/pull/13) | Teste-guarda de totalidade dos 8 estados em `tests/unitarios/ordem_servico/test_repository_os.py` |

## Verificações de Integridade

- **Cobertura RF**: os 19 RFs da fase 1 ([requisitos.md](requisitos.md)) mais os 5 RFs da fase 2 (RF-020–024) estão presentes na matriz
- **Cobertura RNF**: RNF-014 a RNF-016 (fase 1, ADRs 011–012) e RNF-017 a RNF-024 (fase 2, ADRs 015–023) rastreados
- **Cobertura RN**: RN-018 a RN-020 (fase 2) rastreadas com PR e critério de teste
- **Referências válidas**: todos os ADRs referenciados existem no diretório `docs/arquitetura/adr/` (fase 1 na raiz, fase 2 em `adr/fase2/`)
- **Critérios de teste**: todos os RFs/RNs possuem critérios de aceitação verificáveis

## Referência Cruzada

A [tabela de rastreabilidade em requisitos.md](requisitos.md#tabela-de-rastreabilidade) mapeia RF → Seção do Tech Challenge → Contexto Delimitado → Status no Fluxo.

> [↑ Raiz do projeto](../../README.md) · [↑ Requisitos](README.md)
