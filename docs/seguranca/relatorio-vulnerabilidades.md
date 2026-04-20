# Relatorio de Vulnerabilidades

> **Versao**: 1.0 -- verificacao bandit executada em 16/04/2026; pip-audit pendente (rodar via `uv run --with pip-audit pip-audit`). SonarQube, OWASP ZAP, gitleaks e trivy pendentes de execucao.

## Escopo

Analise de seguranca do MVP back-end do sistema de oficina mecanica (Fase 1).

## Metodologia

Referencia: OWASP API Security Top 10 (2023).

Ferramentas utilizadas:
- **SonarQube** -- Analise estatica de codigo e qualidade (SAST, code smells, cobertura)
- **OWASP ZAP** -- Teste dinamico de seguranca de aplicacoes (DAST/pentest automatizado)
- **bandit** -- Analise estatica de seguranca Python (SAST)
- **pip-audit** -- Auditoria de dependencias vulneraveis
- **gitleaks** -- Deteccao de segredos no historico Git
- **trivy** -- Scan de vulnerabilidades na imagem Docker

## Principios de Security By Design

Referencia: Dev-Seguro Aula 01.

### Avaliacao de ameacas por bounded context

Ativos e ameacas por bounded context:

| Bounded Context | Ativos Protegidos | Ameacas Principais |
|---|---|---|
| Autenticacao | Credenciais, tokens JWT | Forca bruta, roubo de token, algorithm confusion |
| Cliente+Veiculo | PII (CPF, CNPJ, dados pessoais) | Vazamento de dados, acesso nao autorizado |
| Catalogo de Servicos | Precos, descricoes de servicos | Modificacao nao autorizada de precos |
| Estoque | Quantidades, reservas de pecas | Race conditions, manipulacao de estoque |
| Ordem de Servico | Dados operacionais, orcamentos | Transicoes nao autorizadas, manipulacao de valores |

Detalhamento por contexto no [Plano de Seguranca](plano-seguranca.md).

### Minimizacao da superficie de ataque

Endpoints expostos por papel (enum `Papel` em `src/autenticacao/dominio/papel.py`):

- **Admin**: acesso completo -- gestao de usuarios, CRUD de catalogo, aprovacao de orcamento, ajuste de estoque, operacoes sensiveis.
- **Atendente**: recepcao -- CRUD de clientes/veiculos, criacao de OS, consulta de catalogo e de estoque.
- **Mecanico**: operacoes tecnicas -- diagnostico, execucao e finalizacao de OS, consulta e movimentacao de estoque, consulta de catalogo.
- **Publico (nao autenticado)**: apenas endpoints de autenticacao (`POST /autenticacao/login`, `POST /autenticacao/refresh`) e consulta publica (`GET /acompanhamento`).

Cada endpoint declara os papeis autorizados via `Depends(exigir_papel(...))`.

Endpoints de documentacao Swagger sao desabilitados em producao (RNF-007).

### Principio do menor privilegio

- **RBAC diferenciado por papel** (ADR-004): tres papeis -- Admin, Mecanico, Atendente -- com permissoes granulares declaradas por endpoint via `exigir_papel(...)`
- **Usuarios de banco de dados**: conexao com permissoes minimas (SELECT, INSERT, UPDATE nos schemas necessarios; sem DROP, TRUNCATE ou acesso a schemas de outros contextos)
- **Segredo JWT**: acessivel apenas pelo modulo de autenticacao, validacao de comprimento minimo no startup

### Validacao e sanitizacao de dados

- **Pydantic models** com `extra="forbid"`: rejeita campos nao declarados no schema, prevenindo mass assignment
- **SQLAlchemy ORM**: todas as consultas usam queries parametrizadas via ORM, eliminando SQL injection
- **Value Objects do dominio**: CPF, CNPJ, Dinheiro e outros tipos validam formato e regras de negocio na construcao
- **SQLAlchemy Core controlado**: unica query via SQLAlchemy Core (nao ORM) e `anonimizar_dados()` no repositorio de Cliente, que usa `sqlalchemy.update()` para contornar listeners ORM durante anonimizacao LGPD. Nao ha SQL string manual no codigo. Demais queries via ORM parametrizado.

### Criptografia

- **Dados em repouso (PII)**: cifragem simetrica Fernet (AES-128-CBC + HMAC-SHA256) de CPF/CNPJ em repouso via `EncryptionService` (chave em `ENCRYPTION_KEY`); hash deterministico HMAC-SHA256 (`documento_hash`) como indice de busca sem expor o valor original; `field(repr=False)` em DTOs para prevenir vazamento em logs/tracebacks; anonimizacao irreversivel via SQLAlchemy Core com tombstone (RF-011, RF-015).
- **Dados em transito**: TLS obrigatorio para todas as conexoes em producao
- **Tokens JWT**: assinatura HS256 com enforcement explicito do algoritmo na validacao
- **Senhas**: hashing via bcrypt com salt automatico (pwdlib)

## Mapeamento OWASP Top 10 (2021)

Referencia: Dev-Seguro Aula 05.

| # | Vulnerabilidade OWASP | Mitigacao no Projeto | Referencia |
|---|---|---|---|
| A01 | Broken Access Control | RBAC com tres papeis (Admin/Mecanico/Atendente); autorizacao granular por endpoint via dependencias FastAPI; tokens JWT com claim `papel` | ADR-004 |
| A02 | Cryptographic Failures | Cifragem Fernet de PII em repouso + hash deterministico HMAC-SHA256 como indice + anonimizacao irreversivel (RF-011, RF-015); JWT HS256 com enforcement de algoritmo; hashing bcrypt via pwdlib; TLS em transito | RF-011, RF-015, ADR-004 |
| A03 | Injection | SQLAlchemy ORM com queries parametrizadas; Pydantic com `extra="forbid"`; unico uso de SQLAlchemy Core (`sqlalchemy.update()`) para anonimizacao LGPD, sem SQL string manual | ADR-006 |
| A04 | Insecure Design | Arquitetura DDD + Onion impoe fronteiras entre camadas (ADR-003); modelo de ameacas por bounded context; Value Objects validam invariantes | ADR-003, ADR-007 |
| A05 | Security Misconfiguration | Security headers configurados (RNF-004); Swagger desabilitado em producao (RNF-007); CORS com whitelist explicita (RNF-005); variaveis sensiveis via env vars | RNF-004, RNF-005, RNF-007 |
| A06 | Vulnerable and Outdated Components | pip-audit para auditoria de dependencias (RNF-010); SBOM via CycloneDX planejado (ADR-012); apenas licencas permissivas | ADR-011, ADR-012 |
| A07 | Identification and Authentication Failures | JWT com revogacao via tabela `tokens_revogados` (RF-012); refresh tokens com rotacao (RF-013); rate limiting por IP (RNF-003); bcrypt via pwdlib | RF-012, RF-013, RNF-003 |
| A08 | Software and Data Integrity Failures | pip-audit no pipeline CI; gitleaks para deteccao de segredos; verificacao de licencas de dependencias (ADR-012) | ADR-011, ADR-012 |
| A09 | Security Logging and Monitoring Failures | structlog com formato JSON (RNF-013); propagacao de request ID; logging de eventos de seguranca (login, logout, falhas de autenticacao, alteracoes de permissao) | RNF-013 |
| A10 | Server-Side Request Forgery (SSRF) | O MVP nao possui funcionalidade de fetch de URLs externas; risco minimo no escopo atual | -- |

## Achados

| # | Severidade | Descricao | CVSS | Status | Mitigacao |
|---|---|---|---|---|---|
| 1 | Baixa | CPF/CNPJ armazenado em texto plano | 3.1 | Mitigado | PII protegido com cifragem simetrica Fernet via `EncryptionService` + hash deterministico HMAC-SHA256 (`documento_hash`) como indice; `field(repr=False)` em DTOs; anonimizacao via SQLAlchemy Core (RF-011, RF-015). |
| 2 | Informativo | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusao) | -- | Implementado | Endpoints `GET /clientes/{id}/dados-pessoais`, `GET .../exportar` e `DELETE .../dados-pessoais` com anonimizacao irreversivel (RF-015). |
| 3 | Informativo | Sem mecanismo de consentimento explicito | -- | Implementado | Endpoints `POST /clientes/{id}/consentimento` e `DELETE .../consentimento` com entidade `ConsentimentoCliente` (RF-019). |
| 4 | Informativo | JWT ainda sem revogacao e sem refresh tokens implementados | 2.0 | Implementado | Tabela `tokens_revogados` com JTI, logout via `POST /autenticacao/logout`, refresh com rotacao via `POST /autenticacao/refresh` (RF-012, RF-013). |

## Seguranca da Cadeia de Suprimentos

Referencia: Dev-Seguro Aula 03.

### Dependencias diretas e licenciamento

| Dependencia | Versao | Licenca | Uso no Projeto |
|---|---|---|---|
| FastAPI | 0.115+ | MIT | Framework web principal |
| SQLAlchemy | 2.0+ | MIT | ORM e mapeamento imperativo |
| Pydantic | 2.0+ | MIT | Validacao de dados e schemas |
| pyjwt | 2.9+ | MIT | Geracao e validacao de JWT |
| pwdlib | 0.2+ | MIT | Hashing de senhas (bcrypt) |
| alembic | 1.13+ | MIT | Migracoes de banco de dados |
| uvicorn | 0.30+ | BSD | Servidor ASGI |
| structlog | 24.0+ | MIT/Apache 2.0 | Logging estruturado |
| brutils | 2.1+ | MIT | Validacao de documentos (CPF, CNPJ) |

Licencas permissivas em todas as dependencias diretas (MIT, BSD, Apache 2.0). Nenhuma GPL.

### Ferramentas de auditoria

- **pip-audit**: execucao no pipeline CI para detectar vulnerabilidades conhecidas (CVEs) em dependencias diretas e transitivas
- **CycloneDX**: geracao de SBOM planejada para cada release, permitindo rastreabilidade da cadeia de suprimentos
- **gitleaks**: prevencao de vazamento de segredos (API keys, senhas) no historico Git

### Riscos mitigados

- **Dependencias comprometidas** (caso UA-Parser-JS): pip-audit detecta versoes maliciosas conhecidas; SBOM permite auditoria retroativa
- **Licencas incompativeis**: politica de apenas licencas permissivas (ADR-012) previne risco legal de licencas copyleft (GPL)
- **Vulnerabilidades transitivas**: pip-audit verifica toda a arvore de dependencias, nao apenas dependencias diretas

## Conformidade LGPD

| Aspecto | Status MVP | Plano de Evolucao |
|---|---|---|
| Mascaramento de dados sensiveis em respostas | Implementado | CPF/CNPJ mascarado via `mascarado()` nos schemas; `field(repr=False)` em DTOs |
| Remocao de PII em logs | Implementado | `field(repr=False)` em todos os DTOs com PII (nome, documento, contato) |
| Armazenamento de CPF/CNPJ | Mitigado | Cifrado com Fernet via `EncryptionService`; `documento_hash` (HMAC-SHA256) como indice deterministico de busca |
| Direito de acesso (Art. 18, I) | Implementado | `GET /clientes/{id}/dados-pessoais` |
| Portabilidade (Art. 18, V) | Implementado | `GET /clientes/{id}/dados-pessoais/exportar` retorna JSON exportavel |
| Exclusao (Art. 18, VI) | Implementado | `DELETE /clientes/{id}/dados-pessoais` anonimiza via SQLAlchemy Core com tombstone |
| Consentimento | Implementado | `POST/DELETE /clientes/{id}/consentimento` com entidade ConsentimentoCliente (RF-019) |

## Resumo dos Scans Automatizados

Data do scan bandit: 12/04/2026. pip-audit, SonarQube, OWASP ZAP, gitleaks e trivy pendentes de execucao.

| Severidade | Bandit | pip-audit | Parcial (apenas Bandit) |
|---|---|---|---|
| HIGH | 0 | TODO | 0 |
| MEDIUM | 1 | TODO | 1 |
| LOW | 0 | TODO | 0 |

Avaliacao parcial de risco: baseada exclusivamente em bandit (SAST Python). pip-audit (CVEs em dependencias), SonarQube (qualidade/seguranca), OWASP ZAP (DAST), gitleaks (segredos) e trivy (CVEs de imagem) estao pendentes; risco global nao foi avaliado. Dentro do escopo do bandit, nenhuma vulnerabilidade alta foi encontrada e o unico achado medio e um binding a `0.0.0.0` no modo de desenvolvimento, sem impacto em producao.

## Analise Estatica (bandit)

Scan executado em 12/04/2026 com bandit 1.9.4 sobre 5.210 linhas de codigo.

| # | Arquivo | Linha | ID | Severidade | Confianca | Descricao | Status |
|---|---|---|---|---|---|---|---|
| 1 | src/main.py | 93 | B104 | MEDIUM | MEDIUM | Binding a `0.0.0.0` (todas as interfaces) | ACEITO |

**Detalhamento**:

- **B104 (hardcoded_bind_all_interfaces)**: O trecho `uvicorn.run("src.main:app", host="0.0.0.0", ...)` vincula o servidor a todas as interfaces de rede. Risco aceito pois: (a) ocorre apenas no bloco `if __name__ == "__main__"` usado em desenvolvimento local; (b) em producao, o Docker Compose gerencia o binding via configuracao do container; (c) a linha ja possui anotacao `# noqa: S104`. CWE-605.

Achados inline acima. Relatorio pode ser regenerado via `bandit -r src/ -f json -o docs/seguranca/bandit-report.json`.

## Auditoria de Dependencias (pip-audit)

**TODO**: executar antes da entrega. Rodar em ambiente efemero (sem poluir o `.venv` gerenciado por `uv`): `uv run --with pip-audit pip-audit --format json --output docs/seguranca/pip-audit-report.json`. Sem `uv`, o equivalente e `pip install pip-audit && pip-audit --format json --output docs/seguranca/pip-audit-report.json`.

Relatorio completo: `docs/seguranca/pip-audit-report.json`.

## Analise Estatica e Qualidade (SonarQube)

**TODO**: executar antes da entrega. Configuracao conforme ADR-011.

## Teste Dinamico de Seguranca (OWASP ZAP)

**TODO**: executar antes da entrega. Configuracao conforme ADR-011.

## Deteccao de Segredos (gitleaks)

**TODO**: executar antes da entrega. Configuracao conforme ADR-011.

## Scan de Imagem Docker (trivy)

**TODO**: executar antes da entrega. Configuracao conforme ADR-011.

## Recomendacoes para Producao

1. Adicionar WAF com rate limiting por usuario autenticado
2. Migrar segredo JWT para KMS (mitigado no MVP via validacao de comprimento no startup)
3. Adicionar CSP headers (TD-003)
4. Evoluir consentimento com granularidade por finalidade de tratamento (RF-019 implementado com modelo basico)

## Referencias

- [Tech Debt](../tech-debt.md) -- Divida tecnica
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) -- Autenticacao JWT
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) -- Pipeline de Seguranca e Analise Estatica
- [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) -- Licenciamento de Software e SBOM
- [Plano de Seguranca](plano-seguranca.md) -- Plano de Seguranca do MVP
- [Requisitos](../requisitos/requisitos.md) -- RF-011, RF-012, RF-013, RF-015, RF-019
