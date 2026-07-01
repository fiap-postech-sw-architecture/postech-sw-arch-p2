# Plano de Segurança

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)

> **Versão**: 1.0 — Fase 1 MVP.

## 1. Objetivo

Medidas de segurança do MVP (Fase 1): modelo de ameaças, controles de acesso, resposta a incidentes e conformidade LGPD.

## 2. Modelo de Ameaças por Bounded Context

Mapeamento de ativos, ameaças e mitigações por bounded context.

### 2.1 Autenticação (contexto genérico)

| Aspecto | Descrição |
|---|---|
| **Ativos protegidos** | Credenciais de usuários (senhas), tokens JWT (access e refresh), sessões |
| **Ameaças principais** | Força bruta em login; roubo de token (XSS, MITM); algorithm confusion no JWT; reuso de refresh token comprometido |
| **Mitigações** | Rate limiting por IP (RNF-003); bcrypt para hashing de senhas; JWT HS256 com enforcement explícito de algoritmo (ADR-004); revogação via tabela `tokens_revogados` com JTI (RF-012); refresh tokens com rotação e invalidação do anterior (RF-013); TLS obrigatório em produção |

> **Fase 2:** o rate limiter passou a usar **storage compartilhado (Redis)** ([ADR-023](../arquitetura/adr/fase2/023-rate-limiter-storage-compartilhado.md)), tornando o limite por IP global e correto sob HPA, com a ressalva de que a chave é o IP do *peer* imediato: atrás de proxy/ingress sem `X-Forwarded-For` confiável, o tráfego externo colapsa num único bucket ([TD-023](../tech-debt/README.md)). A análise de segurança no CI passou a rodar como **gates reais** ([#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/75)): **pip-audit** (CVE em deps de runtime), **gitleaks** (segredos) e **trivy** (CVE na imagem) em [`security.yml`](../../.github/workflows/security.yml); **bandit** em [`ci.yml`](../../.github/workflows/ci.yml) (escopo `src ui relay scripts`); e o **DAST OWASP ZAP baseline** em [`full-test-ci`](../../.github/workflows/full-test-ci.yml) contra a stack de pé (gate por `.zap/rules.tsv`). O **CodeQL** (SAST) roda no CI pelo **default setup** do GitHub code scanning (jobs `Analyze (python)`/`Analyze (javascript-typescript)`), configurado no repositório — não por um workflow versionado, que como *advanced setup* conflitaria com o default setup ativo. Paridade local via `make codeql-quality`. Antes destes gates os scanners eram execução manual de fechamento — paridade local também via `make dast` ([TD-010](../tech-debt/README.md), [TD-011](../tech-debt/README.md), [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md)).

### 2.2 Cliente + Veiculo

| Aspecto | Descrição |
|---|---|
| **Ativos protegidos** | PII de clientes (CPF, CNPJ, nome, endereço, telefone); dados de veículos (placa, chassi) |
| **Ameaças principais** | Vazamento de dados pessoais (data breach); acesso não autorizado a dados de outros clientes; violação da LGPD |
| **Mitigações** | Cifragem simétrica Fernet de CPF/CNPJ em repouso via `EncryptionService` (chave `ENCRYPTION_KEY`); hash determinístico HMAC-SHA256 (`documento_hash`) como índice de busca (RF-011); RBAC com autorização por endpoint (ADR-004); mascaramento de dados sensíveis em listagens; endpoints LGPD Art. 18 (RF-015); remoção de PII em logs via processador structlog |

### 2.3 Catálogo de Serviços

| Aspecto | Descrição |
|---|---|
| **Ativos protegidos** | Preços de serviços, descrições, categorias |
| **Ameaças principais** | Modificação não autorizada de preços; inserção de serviços fraudulentos |
| **Mitigações** | RBAC restringindo CRUD de serviços ao papel Admin (RF-014); logging estruturado de alterações de preço (RNF-013); Pydantic com `extra="forbid"` prevenindo mass assignment |

### 2.4 Estoque

| Aspecto | Descrição |
|---|---|
| **Ativos protegidos** | Quantidades de peças, reservas vinculadas a OS, dados de fornecedores |
| **Ameaças principais** | Race conditions em reserva concorrente; manipulação de quantidades; acesso não autorizado a dados de custo |
| **Mitigações** | Bloqueio pessimista (SELECT FOR UPDATE) para operações de reserva (ADR-008); RBAC com gestão de estoque restrita ao Admin; Value Object `Quantidade` com invariante de não-negatividade; transações atômicas para reserva/liberação |

### 2.5 Ordem de Serviço (contexto core)

| Aspecto | Descrição |
|---|---|
| **Ativos protegidos** | Dados operacionais (diagnósticos, orçamentos, peças utilizadas), valores financeiros |
| **Ameaças principais** | Transições de estado não autorizadas (ex: pular aprovação de orçamento); manipulação de valores de orçamento; acesso a OS de outros mecânicos |
| **Mitigações** | Máquina de estados no Aggregate Root com validação de transições permitidas; RBAC com papéis diferenciados (Admin, Mecânico e Atendente) aplicado por endpoint via `exigir_papel(...)`; Value Object `Dinheiro` com validação de precisão; logging estruturado de transições de estado em INFO (RNF-013) |

## 3. Controles de Acesso

### 3.1 Papéis e permissões (RBAC)

RBAC conforme ADR-004. O enum `Papel` (`src/autenticacao/dominio/papel.py`) define três valores: `admin`, `mecanico` e `atendente`. Cada endpoint declara os papéis autorizados via `Depends(exigir_papel(...))` (`src/autenticacao/interfaces/middleware.py`); permissões derivam da composição real dos routers.

| Operação | Admin | Mecânico | Atendente |
|---|---|---|---|
| Gestão de usuários | Sim | Não | Não |
| CRUD de clientes e veículos | Sim | Não | Sim |
| CRUD de catálogo de serviços | Sim | Não | Não |
| Consulta de catálogo | Sim | Sim | Sim |
| Gestão de estoque (entrada, ajuste) | Sim | Não | Não |
| Consulta/movimentação de estoque | Sim | Sim | Não |
| Criação de OS | Sim | Não | Sim |
| Diagnóstico e execução de OS | Sim | Sim | Não |
| Aprovação de orçamento | Sim | Não | Não |
| Consulta de OS | Sim | Sim | Sim |

### 3.2 Implementação técnica

- Claim `papel` (lowercase) no payload JWT identifica o papel do usuário autenticado
- Dependências FastAPI (`Depends`) verificam papel em cada endpoint protegido
- Tokens com TTL de 15 minutos; refresh tokens com rotação
- Revogação via tabela `tokens_revogados` com verificação em cada request

## 4. Plano de Resposta a Incidentes (simplificado)

Plano simplificado para o MVP. Em produção, expandir com runbooks, escalação e comunicação a autoridades.

### 4.1 Detecção

- Monitoramento de logs estruturados (structlog JSON) para eventos de segurança
- Alertas para: múltiplas falhas de autenticação do mesmo IP, tentativas de acesso a endpoints não autorizados, erros 500 recorrentes
- Revisão periódica de logs de auditoria

### 4.2 Contenção

- Revogação imediata de tokens JWT comprometidos via tabela `tokens_revogados`
- Bloqueio temporário de IP em caso de força bruta (rate limiting)
- Isolamento do serviço afetado (restart do container Docker)

### 4.3 Erradicação

- Identificação da causa raiz via análise de logs e request IDs
- Correção da vulnerabilidade explorada
- Atualização de dependências se a causa for CVE conhecida
- Rotação de segredos (JWT secret, credenciais de banco) se comprometidos

### 4.4 Recuperacao

- Restore do banco de dados a partir de backup se houve manipulação de dados
- Re-deploy da aplicação com a correção aplicada
- Verificação de integridade dos dados via queries de consistência
- Monitoramento intensificado nas 48 horas seguintes

### 4.5 Lições aprendidas

- Documentação do incidente com timeline, causa raiz e ações corretivas
- Atualização deste plano de segurança e do relatório de vulnerabilidades
- Criação de testes de regressão para a vulnerabilidade explorada

## 5. Conformidade LGPD

Artigos aplicaveis da LGPD (Lei 13.709/2018) e status no MVP.

| Artigo | Disposição | Status no MVP | Implementação |
|---|---|---|---|
| Art. 6 | Princípios (finalidade, adequação, necessidade, etc.) | Parcial | Coleta limitada aos dados necessários para o serviço; acesso restrito por RBAC |
| Art. 7 | Bases legais para tratamento | Parcial | Base legal: execução de contrato (prestação de serviço mecânico) |
| Art. 11 | Tratamento de dados sensíveis | Conforme | CPF/CNPJ protegidos via cifragem simétrica Fernet em repouso (`EncryptionService`) + hash determinístico HMAC-SHA256 (`documento_hash`) como índice + anonimização irreversível (RF-011, RF-015); não há coleta de dados sensíveis além de documentos |
| Art. 18 | Direitos do titular | Implementado | Endpoints dados-pessoais, exportar e anonimizar implementados (RF-015); consentimento via RF-019 |
| Art. 46 | Medidas de segurança | Conforme | Cifragem simétrica Fernet (AES-128-CBC + HMAC-SHA256) de CPF/CNPJ em repouso + hash determinístico (HMAC-SHA256) como índice de busca (`EncryptionService`, chave via `ENCRYPTION_KEY`); bcrypt em senhas; TLS em trânsito; RBAC; logging; pipeline de segurança (ADR-011) |
| Art. 48 | Comunicação de incidentes | Planejado | Plano de resposta a incidentes documentado (seção 4 deste documento) |

### 5.1 Dados pessoais tratados

| Dado | Classificação | Armazenamento | Retenção |
|---|---|---|---|
| CPF | Dado pessoal | Cifrado com Fernet (AES-128-CBC + HMAC-SHA256) via `EncryptionService`; `documento_hash` (HMAC-SHA256) como índice determinístico de busca | Enquanto cliente ativo; anonimizado na exclusão |
| CNPJ | Dado pessoal (PJ) | Cifrado com Fernet (AES-128-CBC + HMAC-SHA256) via `EncryptionService`; `documento_hash` (HMAC-SHA256) como índice determinístico de busca | Enquanto cliente ativo; anonimizado na exclusão |
| Nome | Dado pessoal | Texto plano | Enquanto cliente ativo; anonimizado na exclusão |
| Telefone | Dado pessoal | Texto plano | Enquanto cliente ativo; removido na exclusão |
| Endereço | Dado pessoal | Texto plano | Enquanto cliente ativo; removido na exclusão |
| Placa do veículo | Dado pessoal (vinculado) | Texto plano | Enquanto veículo ativo |

## 6. Padroes de Referencia

### 6.1 CIS Benchmark

Referência para configuração segura do ambiente:
- PostgreSQL: configuração de `pg_hba.conf` com autenticação md5/scram, SSL habilitado
- Docker: imagem base mínima (python:3.12-slim), usuário não-root no container, sem capabilities extras
- Rede: exposição apenas da porta do serviço (8000), banco acessível apenas via rede interna Docker

### 6.2 ISO 27001/27002

Controles aplicáveis ao MVP:
- **A.9 Controle de acesso**: RBAC com papéis Admin, Mecânico e Atendente, autenticação JWT (ADR-004)
- **A.10 Criptografia**: cifragem simétrica Fernet (AES-128-CBC + HMAC-SHA256) de PII (`EncryptionService.encrypt`); hash determinístico HMAC-SHA256 (`documento_hash`) como índice de busca sem exposição do valor original; bcrypt para senhas; TLS em trânsito
- **A.12 Segurança nas operações**: logging estruturado, pipeline de segurança no CI (ADR-011)
- **A.14 Aquisição e desenvolvimento**: análise estática (bandit), testes de segurança, revisão de código

### 6.3 OWASP API Security Top 10

Mapeamento documentado no [Relatorio de Vulnerabilidades](relatorio-vulnerabilidades.md), seção "Mapeamento OWASP Top 10 (2021)".

## 7. Referências

- [Relatorio de Vulnerabilidades](relatorio-vulnerabilidades.md) — Achados, mapeamento OWASP, conformidade LGPD detalhada
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) — Autenticacao JWT e RBAC
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) — Pipeline de Segurança e Análise Estática
- [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) — Licenciamento de Software e SBOM
- [Requisitos](../requisitos/requisitos.md) — RF-011, RF-012, RF-013, RF-014, RF-015, RNF-003, RNF-004, RNF-005, RNF-007, RNF-010, RNF-013

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)
