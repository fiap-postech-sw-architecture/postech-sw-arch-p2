# Plano de Seguranca

> **Versao**: 1.0 -- Fase 1 MVP.

## 1. Objetivo

Medidas de seguranca do MVP (Fase 1): modelo de ameacas, controles de acesso, resposta a incidentes e conformidade LGPD.

## 2. Modelo de Ameacas por Bounded Context

Mapeamento de ativos, ameacas e mitigacoes por bounded context.

### 2.1 Autenticacao (contexto generico)

| Aspecto | Descricao |
|---|---|
| **Ativos protegidos** | Credenciais de usuarios (senhas), tokens JWT (access e refresh), sessoes |
| **Ameacas principais** | Forca bruta em login; roubo de token (XSS, MITM); algorithm confusion no JWT; reuso de refresh token comprometido |
| **Mitigacoes** | Rate limiting por IP (RNF-003); bcrypt para hashing de senhas; JWT HS256 com enforcement explicito de algoritmo (ADR-004); revogacao via tabela `tokens_revogados` com JTI (RF-012); refresh tokens com rotacao e invalidacao do anterior (RF-013); TLS obrigatorio em producao |

### 2.2 Cliente + Veiculo

| Aspecto | Descricao |
|---|---|
| **Ativos protegidos** | PII de clientes (CPF, CNPJ, nome, endereco, telefone); dados de veiculos (placa, chassi) |
| **Ameacas principais** | Vazamento de dados pessoais (data breach); acesso nao autorizado a dados de outros clientes; violacao da LGPD |
| **Mitigacoes** | Cifragem simetrica Fernet de CPF/CNPJ em repouso via `EncryptionService` (chave `ENCRYPTION_KEY`); hash deterministico HMAC-SHA256 (`documento_hash`) como indice de busca (RF-011); RBAC com autorizacao por endpoint (ADR-004); mascaramento de dados sensiveis em listagens; endpoints LGPD Art. 18 (RF-015); remocao de PII em logs via processador structlog |

### 2.3 Catalogo de Servicos

| Aspecto | Descricao |
|---|---|
| **Ativos protegidos** | Precos de servicos, descricoes, categorias |
| **Ameacas principais** | Modificacao nao autorizada de precos; insercao de servicos fraudulentos |
| **Mitigacoes** | RBAC restringindo CRUD de servicos ao papel Admin (RF-014); logging estruturado de alteracoes de preco (RNF-013); Pydantic com `extra="forbid"` prevenindo mass assignment |

### 2.4 Estoque

| Aspecto | Descricao |
|---|---|
| **Ativos protegidos** | Quantidades de pecas, reservas vinculadas a OS, dados de fornecedores |
| **Ameacas principais** | Race conditions em reserva concorrente; manipulacao de quantidades; acesso nao autorizado a dados de custo |
| **Mitigacoes** | Bloqueio pessimista (SELECT FOR UPDATE) para operacoes de reserva (ADR-008); RBAC com gestao de estoque restrita ao Admin; Value Object `Quantidade` com invariante de nao-negatividade; transacoes atomicas para reserva/liberacao |

### 2.5 Ordem de Servico (contexto core)

| Aspecto | Descricao |
|---|---|
| **Ativos protegidos** | Dados operacionais (diagnosticos, orcamentos, pecas utilizadas), valores financeiros |
| **Ameacas principais** | Transicoes de estado nao autorizadas (ex: pular aprovacao de orcamento); manipulacao de valores de orcamento; acesso a OS de outros mecanicos |
| **Mitigacoes** | Maquina de estados no Aggregate Root com validacao de transicoes permitidas; RBAC com papeis diferenciados (Admin, Mecanico e Atendente) aplicado por endpoint via `exigir_papel(...)`; Value Object `Dinheiro` com validacao de precisao; logging estruturado de transicoes de estado em INFO (RNF-013) |

## 3. Controles de Acesso

### 3.1 Papeis e permissoes (RBAC)

RBAC conforme ADR-004. O enum `Papel` (`src/autenticacao/dominio/papel.py`) define tres valores: `admin`, `mecanico` e `atendente`. Cada endpoint declara os papeis autorizados via `Depends(exigir_papel(...))` (`src/autenticacao/interfaces/middleware.py`); permissoes derivam da composicao real dos routers.

| Operacao | Admin | Mecanico | Atendente |
|---|---|---|---|
| Gestao de usuarios | Sim | Nao | Nao |
| CRUD de clientes e veiculos | Sim | Nao | Sim |
| CRUD de catalogo de servicos | Sim | Nao | Nao |
| Consulta de catalogo | Sim | Sim | Sim |
| Gestao de estoque (entrada, ajuste) | Sim | Nao | Nao |
| Consulta/movimentacao de estoque | Sim | Sim | Nao |
| Criacao de OS | Sim | Nao | Sim |
| Diagnostico e execucao de OS | Sim | Sim | Nao |
| Aprovacao de orcamento | Sim | Nao | Nao |
| Consulta de OS | Sim | Sim | Sim |

### 3.2 Implementacao tecnica

- Claim `papel` (lowercase) no payload JWT identifica o papel do usuario autenticado
- Dependencias FastAPI (`Depends`) verificam papel em cada endpoint protegido
- Tokens com TTL de 15 minutos; refresh tokens com rotacao
- Revogacao via tabela `tokens_revogados` com verificacao em cada request

## 4. Plano de Resposta a Incidentes (simplificado)

Plano simplificado para o MVP. Em producao, expandir com runbooks, escalacao e comunicacao a autoridades.

### 4.1 Deteccao

- Monitoramento de logs estruturados (structlog JSON) para eventos de seguranca
- Alertas para: multiplas falhas de autenticacao do mesmo IP, tentativas de acesso a endpoints nao autorizados, erros 500 recorrentes
- Revisao periodica de logs de auditoria

### 4.2 Contencao

- Revogacao imediata de tokens JWT comprometidos via tabela `tokens_revogados`
- Bloqueio temporario de IP em caso de forca bruta (rate limiting)
- Isolamento do servico afetado (restart do container Docker)

### 4.3 Erradicacao

- Identificacao da causa raiz via analise de logs e request IDs
- Correcao da vulnerabilidade explorada
- Atualizacao de dependencias se a causa for CVE conhecida
- Rotacao de segredos (JWT secret, credenciais de banco) se comprometidos

### 4.4 Recuperacao

- Restore do banco de dados a partir de backup se houve manipulacao de dados
- Re-deploy da aplicacao com a correcao aplicada
- Verificacao de integridade dos dados via queries de consistencia
- Monitoramento intensificado nas 48 horas seguintes

### 4.5 Licoes aprendidas

- Documentacao do incidente com timeline, causa raiz e acoes corretivas
- Atualizacao deste plano de seguranca e do relatorio de vulnerabilidades
- Criacao de testes de regressao para a vulnerabilidade explorada

## 5. Conformidade LGPD

Artigos aplicaveis da LGPD (Lei 13.709/2018) e status no MVP.

| Artigo | Disposicao | Status no MVP | Implementacao |
|---|---|---|---|
| Art. 6 | Principios (finalidade, adequacao, necessidade, etc.) | Parcial | Coleta limitada aos dados necessarios para o servico; acesso restrito por RBAC |
| Art. 7 | Bases legais para tratamento | Parcial | Base legal: execucao de contrato (prestacao de servico mecanico) |
| Art. 11 | Tratamento de dados sensiveis | Conforme | CPF/CNPJ protegidos via cifragem simetrica Fernet em repouso (`EncryptionService`) + hash deterministico HMAC-SHA256 (`documento_hash`) como indice + anonimizacao irreversivel (RF-011, RF-015); nao ha coleta de dados sensiveis alem de documentos |
| Art. 18 | Direitos do titular | Implementado | Endpoints dados-pessoais, exportar e anonimizar implementados (RF-015); consentimento via RF-019 |
| Art. 46 | Medidas de seguranca | Conforme | Cifragem simetrica Fernet (AES-128-CBC + HMAC-SHA256) de CPF/CNPJ em repouso + hash deterministico (HMAC-SHA256) como indice de busca (`EncryptionService`, chave via `ENCRYPTION_KEY`); bcrypt em senhas; TLS em transito; RBAC; logging; pipeline de seguranca (ADR-011) |
| Art. 48 | Comunicacao de incidentes | Planejado | Plano de resposta a incidentes documentado (secao 4 deste documento) |

### 5.1 Dados pessoais tratados

| Dado | Classificacao | Armazenamento | Retencao |
|---|---|---|---|
| CPF | Dado pessoal | Cifrado com Fernet (AES-128-CBC + HMAC-SHA256) via `EncryptionService`; `documento_hash` (HMAC-SHA256) como indice deterministico de busca | Enquanto cliente ativo; anonimizado na exclusao |
| CNPJ | Dado pessoal (PJ) | Cifrado com Fernet (AES-128-CBC + HMAC-SHA256) via `EncryptionService`; `documento_hash` (HMAC-SHA256) como indice deterministico de busca | Enquanto cliente ativo; anonimizado na exclusao |
| Nome | Dado pessoal | Texto plano | Enquanto cliente ativo; anonimizado na exclusao |
| Telefone | Dado pessoal | Texto plano | Enquanto cliente ativo; removido na exclusao |
| Endereco | Dado pessoal | Texto plano | Enquanto cliente ativo; removido na exclusao |
| Placa do veiculo | Dado pessoal (vinculado) | Texto plano | Enquanto veiculo ativo |

## 6. Padroes de Referencia

### 6.1 CIS Benchmark

Referencia para configuracao segura do ambiente:
- PostgreSQL: configuracao de `pg_hba.conf` com autenticacao md5/scram, SSL habilitado
- Docker: imagem base minima (python:3.12-slim), usuario nao-root no container, sem capabilities extras
- Rede: exposicao apenas da porta do servico (8000), banco acessivel apenas via rede interna Docker

### 6.2 ISO 27001/27002

Controles aplicaveis ao MVP:
- **A.9 Controle de acesso**: RBAC com papeis Admin, Mecanico e Atendente, autenticacao JWT (ADR-004)
- **A.10 Criptografia**: cifragem simetrica Fernet (AES-128-CBC + HMAC-SHA256) de PII (`EncryptionService.encrypt`); hash deterministico HMAC-SHA256 (`documento_hash`) como indice de busca sem exposicao do valor original; bcrypt para senhas; TLS em transito
- **A.12 Seguranca nas operacoes**: logging estruturado, pipeline de seguranca no CI (ADR-011)
- **A.14 Aquisicao e desenvolvimento**: analise estatica (bandit), testes de seguranca, revisao de codigo

### 6.3 OWASP API Security Top 10

Mapeamento documentado no [Relatorio de Vulnerabilidades](relatorio-vulnerabilidades.md), secao "Mapeamento OWASP Top 10 (2021)".

## 7. Referencias

- [Relatorio de Vulnerabilidades](relatorio-vulnerabilidades.md) -- Achados, mapeamento OWASP, conformidade LGPD detalhada
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) -- Autenticacao JWT e RBAC
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) -- Pipeline de Seguranca e Analise Estatica
- [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) -- Licenciamento de Software e SBOM
- [Requisitos](../requisitos/requisitos.md) -- RF-011, RF-012, RF-013, RF-014, RF-015, RNF-003, RNF-004, RNF-005, RNF-007, RNF-010, RNF-013
