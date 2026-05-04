# Relatório de Vulnerabilidades

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)

> **Versão**: 2.1 — bateria de scans automatizados executada em 29/04/2026 (bandit, pip-audit, gitleaks, trivy fs+image); SonarQube executado e fechado em [#107](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/107); OWASP ZAP baseline executado em 02/05/2026 — 0 FAIL / 2 WARN aceitos (fechado em [#108](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/108)).

## Escopo

Análise de segurança do MVP back-end do sistema de oficina mecânica (Fase 1).

## Metodologia

Referência: OWASP API Security Top 10 (2023).

Ferramentas utilizadas:
- **SonarQube** -- Análise estática de código e qualidade (SAST, code smells, cobertura)
- **OWASP ZAP** -- Teste dinâmico de segurança de aplicações (DAST/pentest automatizado)
- **bandit** -- Análise estática de segurança Python (SAST)
- **pip-audit** -- Auditoria de dependências vulneráveis
- **gitleaks** -- Detecção de segredos no histórico Git
- **trivy** -- Scan de vulnerabilidades na imagem Docker

## Princípios de Security By Design

Referência: Dev-Seguro Aula 01.

### Avaliação de ameaças por bounded context

Ativos e ameaças por bounded context:

| Bounded Context | Ativos Protegidos | Ameacas Principais |
|---|---|---|
| Autenticação | Credenciais, tokens JWT | Força bruta, roubo de token, algorithm confusion |
| Cliente+Veiculo | PII (CPF, CNPJ, dados pessoais) | Vazamento de dados, acesso não autorizado |
| Catalogo de Servicos | Preços, descrições de serviços | Modificação não autorizada de preços |
| Estoque | Quantidades, reservas de peças | Race conditions, manipulação de estoque |
| Ordem de Servico | Dados operacionais, orçamentos | Transições não autorizadas, manipulação de valores |

Detalhamento por contexto no [Plano de Segurança](plano-seguranca.md).

### Minimização da superfície de ataque

Endpoints expostos por papel (enum `Papel` em `src/autenticacao/dominio/papel.py`):

- **Admin**: acesso completo -- gestão de usuários, CRUD de catálogo, aprovação de orçamento, ajuste de estoque, operações sensíveis.
- **Atendente**: recepção -- CRUD de clientes/veículos, criação de OS, consulta de catálogo e de estoque.
- **Mecanico**: operações técnicas -- diagnóstico, execução e finalização de OS, consulta e movimentação de estoque, consulta de catálogo.
- **Público (não autenticado)**: apenas endpoints de autenticação (`POST /autenticacao/login`, `POST /autenticacao/refresh`) e consulta pública (`GET /acompanhamento`).

Cada endpoint declara os papeis autorizados via `Depends(exigir_papel(...))`.

Endpoints de documentação Swagger são desabilitados em produção (RNF-007).

### Princípio do menor privilégio

- **RBAC diferenciado por papel** (ADR-004): três papéis -- Admin, Mecanico, Atendente -- com permissões granulares declaradas por endpoint via `exigir_papel(...)`
- **Usuários de banco de dados**: conexão com permissões mínimas (SELECT, INSERT, UPDATE nos schemas necessários; sem DROP, TRUNCATE ou acesso a schemas de outros contextos)
- **Segredo JWT**: acessível apenas pelo módulo de autenticação, validação de comprimento mínimo no startup

### Validação e sanitização de dados

- **Pydantic models** com `extra="forbid"`: rejeita campos não declarados no schema, prevenindo mass assignment
- **SQLAlchemy ORM**: todas as consultas usam queries parametrizadas via ORM, eliminando SQL injection
- **Value Objects do domínio**: CPF, CNPJ, Dinheiro e outros tipos validam formato e regras de negócio na construção
- **SQLAlchemy Core controlado**: única query via SQLAlchemy Core (não ORM) é `anonimizar_dados()` no repositório de Cliente, que usa `sqlalchemy.update()` para contornar listeners ORM durante anonimização LGPD. Não há SQL string manual no código. Demais queries via ORM parametrizado.

### Criptografia

- **Dados em repouso (PII)**: cifragem simétrica Fernet (AES-128-CBC + HMAC-SHA256) de CPF/CNPJ em repouso via `EncryptionService` (chave em `ENCRYPTION_KEY`); hash determinístico HMAC-SHA256 (`documento_hash`) como índice de busca sem expor o valor original; `field(repr=False)` em DTOs para prevenir vazamento em logs/tracebacks; anonimização irreversível via SQLAlchemy Core com tombstone (RF-011, RF-015).
- **Dados em trânsito**: TLS obrigatório para todas as conexões em produção
- **Tokens JWT**: assinatura HS256 com enforcement explícito do algoritmo na validação
- **Senhas**: hashing via bcrypt com salt automático (pwdlib)

## Mapeamento OWASP Top 10 (2021)

Referência: Dev-Seguro Aula 05.

| # | Vulnerabilidade OWASP | Mitigação no Projeto | Referência |
|---|---|---|---|
| A01 | Broken Access Control | RBAC com três papéis (Admin/Mecanico/Atendente); autorização granular por endpoint via dependências FastAPI; tokens JWT com claim `papel` | ADR-004 |
| A02 | Cryptographic Failures | Cifragem Fernet de PII em repouso + hash determinístico HMAC-SHA256 como índice + anonimização irreversível (RF-011, RF-015); JWT HS256 com enforcement de algoritmo; hashing bcrypt via pwdlib; TLS em trânsito | RF-011, RF-015, ADR-004 |
| A03 | Injection | SQLAlchemy ORM com queries parametrizadas; Pydantic com `extra="forbid"`; único uso de SQLAlchemy Core (`sqlalchemy.update()`) para anonimização LGPD, sem SQL string manual | ADR-006 |
| A04 | Insecure Design | Arquitetura DDD + Onion impõe fronteiras entre camadas (ADR-003); modelo de ameaças por bounded context; Value Objects validam invariantes | ADR-003, ADR-007 |
| A05 | Security Misconfiguration | Security headers configurados (RNF-004); Swagger desabilitado em produção (RNF-007); CORS com whitelist explícita (RNF-005); variáveis sensíveis via env vars | RNF-004, RNF-005, RNF-007 |
| A06 | Vulnerable and Outdated Components | pip-audit para auditoria de dependências (RNF-010); SBOM via CycloneDX planejado (ADR-012); apenas licenças permissivas | ADR-011, ADR-012 |
| A07 | Identification and Authentication Failures | JWT com revogação via tabela `tokens_revogados` (RF-012); refresh tokens com rotação (RF-013); rate limiting por IP (RNF-003); bcrypt via pwdlib | RF-012, RF-013, RNF-003 |
| A08 | Software and Data Integrity Failures | pip-audit no pipeline CI; gitleaks para detecção de segredos; verificação de licenças de dependências (ADR-012) | ADR-011, ADR-012 |
| A09 | Security Logging and Monitoring Failures | structlog com formato JSON (RNF-013); propagação de request ID; logging de eventos de segurança (login, logout, falhas de autenticação, alterações de permissão) | RNF-013 |
| A10 | Server-Side Request Forgery (SSRF) | O MVP não possui funcionalidade de fetch de URLs externas; risco mínimo no escopo atual | -- |

## Achados

| # | Severidade | Descrição | CVSS | Status | Mitigação |
|---|---|---|---|---|---|
| 1 | Baixa | CPF/CNPJ armazenado em texto plano | 3.1 | Mitigado | PII protegido com cifragem simétrica Fernet via `EncryptionService` + hash determinístico HMAC-SHA256 (`documento_hash`) como índice; `field(repr=False)` em DTOs; anonimização via SQLAlchemy Core (RF-011, RF-015). |
| 2 | Informativo | Sem endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | -- | Implementado | Endpoints `GET /clientes/{id}/dados-pessoais`, `GET .../exportar` e `DELETE .../dados-pessoais` com anonimização irreversível (RF-015). |
| 3 | Informativo | Sem mecanismo de consentimento explicito | -- | Implementado | Endpoints `POST /clientes/{id}/consentimento` e `DELETE .../consentimento` com entidade `ConsentimentoCliente` (RF-019). |
| 4 | Informativo | JWT ainda sem revogação e sem refresh tokens implementados | 2.0 | Implementado | Tabela `tokens_revogados` com JTI, logout via `POST /autenticacao/logout`, refresh com rotação via `POST /autenticacao/refresh` (RF-012, RF-013). |

## Segurança da Cadeia de Suprimentos

Referência: Dev-Seguro Aula 03.

### Dependências diretas e licenciamento

| Dependência | Versão | Licença | Uso no Projeto |
|---|---|---|---|
| FastAPI | 0.115+ | MIT | Framework web principal |
| SQLAlchemy | 2.0+ | MIT | ORM e mapeamento imperativo |
| Pydantic | 2.0+ | MIT | Validação de dados e schemas |
| pyjwt | 2.9+ | MIT | Geração e validação de JWT |
| pwdlib | 0.2+ | MIT | Hashing de senhas (bcrypt) |
| alembic | 1.13+ | MIT | Migrações de banco de dados |
| uvicorn | 0.30+ | BSD | Servidor ASGI |
| structlog | 24.0+ | MIT/Apache 2.0 | Logging estruturado |
| brutils | 2.1+ | MIT | Validação de documentos (CPF, CNPJ) |

Licenças permissivas em todas as dependências diretas (MIT, BSD, Apache 2.0). Nenhuma GPL.

### Ferramentas de auditoria

- **pip-audit**: execução no pipeline CI para detectar vulnerabilidades conhecidas (CVEs) em dependências diretas e transitivas
- **CycloneDX**: geração de SBOM planejada para cada release, permitindo rastreabilidade da cadeia de suprimentos
- **gitleaks**: prevenção de vazamento de segredos (API keys, senhas) no histórico Git

### Riscos mitigados

- **Dependências comprometidas** (caso UA-Parser-JS): pip-audit detecta versões maliciosas conhecidas; SBOM permite auditoria retroativa
- **Licenças incompatíveis**: política de apenas licenças permissivas (ADR-012) previne risco legal de licenças copyleft (GPL)
- **Vulnerabilidades transitivas**: pip-audit verifica toda a árvore de dependências, não apenas dependências diretas

## Conformidade LGPD

| Aspecto | Status MVP | Plano de Evolução |
|---|---|---|
| Mascaramento de dados sensíveis em respostas | Implementado | CPF/CNPJ mascarado via `mascarado()` nos schemas; `field(repr=False)` em DTOs |
| Remoção de PII em logs | Implementado | `field(repr=False)` em todos os DTOs com PII (nome, documento, contato) |
| Armazenamento de CPF/CNPJ | Mitigado | Cifrado com Fernet via `EncryptionService`; `documento_hash` (HMAC-SHA256) como índice determinístico de busca |
| Direito de acesso (Art. 18, I) | Implementado | `GET /clientes/{id}/dados-pessoais` |
| Portabilidade (Art. 18, V) | Implementado | `GET /clientes/{id}/dados-pessoais/exportar` retorna JSON exportavel |
| Exclusão (Art. 18, VI) | Implementado | `DELETE /clientes/{id}/dados-pessoais` anonimiza via SQLAlchemy Core com tombstone |
| Consentimento | Implementado | `POST/DELETE /clientes/{id}/consentimento` com entidade ConsentimentoCliente (RF-019) |

## Resumo dos Scans Automatizados

Bateria executada em 29/04/2026 (bandit, pip-audit, gitleaks, trivy fs+image), SonarQube fechado em [#107](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/107) e em 02/05/2026 (OWASP ZAP baseline fechado em [#108](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/108) + Bandit reexecutado após mitigação do B104) — ver seção "Análise Estática e Qualidade (SonarQube)" abaixo para detalhes.

| Severidade | Bandit | pip-audit | gitleaks (wt) | gitleaks (hist) | trivy fs | trivy image | ZAP |
|---|---|---|---|---|---|---|---|
| HIGH/CRITICAL | 0 | 0 | 0 | 0 | 3 | 6 | 0 |
| MEDIUM | 0 | -- | -- | -- | (filtro HIGH+) | (filtro HIGH+) | -- |
| WARN | -- | -- | -- | -- | -- | -- | 2 |
| LOW | 0 | -- | -- | -- | (filtro HIGH+) | (filtro HIGH+) | -- |

Avaliação consolidada do risco automatizado:

- **Bandit (SAST Python)**: 0 HIGH / 0 MEDIUM / 0 LOW em `src/`. O B104 foi mitigado: `python src/main.py` usa `127.0.0.1` por padrão e o bind em todas as interfaces fica explícito apenas no entrypoint do container.
- **pip-audit (CVE em dependências diretas e transitivas)**: 98 deps auditadas, 0 vulnerabilidades.
- **gitleaks (segredos no working tree e em todo o histórico Git)**: 0 leaks após `.gitleaks.toml` documentar 3 falsos positivos (template DEV-ONLY, runtime do NiceGUI, fixtures de senha de teste).
- **trivy fs (CVE em deps Python via uv.lock)**: 3 HIGH em `nicegui 2.24.2` -- todas com fix em majors 3.x; aceitos como dívida ([#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/112)) porque `ui/` é dev-only e não roda em produção.
- **trivy image (CVE em pacotes OS da imagem `pytstop:audit`)**: 6 HIGH (`ncurses` e `systemd`) sem fix upstream; aceitos como dívida ([#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/113)) porque os pacotes não são usados pelo runtime FastAPI/uvicorn da app.
- **OWASP ZAP (DAST baseline)**: 0 FAIL / 2 WARN aceitos / 65 PASS. Cobertura de 49 URLs via OpenAPI spec. WARNs são falsos positivos esperados para API REST (detalhados na seção abaixo). Caso A.

## Análise Estática (bandit)

Scan reexecutado em 02/05/2026 com bandit 1.9.4 sobre `src/`.

| # | Arquivo | Linha | ID | Severidade | Confiança | Descrição | Status |
|---|---|---|---|---|---|---|---|
| -- | -- | -- | -- | -- | -- | Nenhum achado | LIMPO |

**Detalhamento**:

- **B104 (hardcoded_bind_all_interfaces)**: mitigado em `src/main.py`. A execução direta usa `UVICORN_HOST` com default `127.0.0.1`; em Docker, o bind `0.0.0.0` continua no `entrypoint.sh`, onde é necessário para expor a porta do container.

Sem regressão em relação ao baseline de 16/04 e sem riscos aceitos remanescentes no Bandit. Relatório JSON em `docs/seguranca/bandit-report.json`; regenerar com `uv run bandit -r src/ -f json -o docs/seguranca/bandit-report.json`.

## Auditoria de Dependências (pip-audit)

Scan executado em 29/04/2026 via `uv run --with pip-audit pip-audit --format json --output docs/seguranca/pip-audit-report.json` (ambiente efemero, sem poluir o `.venv`).

**Resultado**: 98 dependências auditadas; **0 vulnerabilidades conhecidas**. O próprio pacote `pytstop` foi pulado (`Dependency not found on PyPI`) porque é um projeto local não publicado.

Relatório JSON em `docs/seguranca/pip-audit-report.json`. Reprodução:

```bash
uv run --with pip-audit pip-audit --format json --output docs/seguranca/pip-audit-report.json
```

## Análise Estática e Qualidade (SonarQube)

Executado e fechado em [#107](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/107). Configuração conforme ADR-011.

## Teste Dinâmico de Segurança (OWASP ZAP)

Scan executado em 02/05/2026 com `zaproxy/zap-stable` (modo baseline passivo) contra `http://localhost:8000/openapi.json` com stack completa rodando via `docker compose up -d` (PostgreSQL + app + seed de admin).

**Resultado**: 65 PASS / 0 FAIL / 2 WARN. Caso A.

Relatórios em `docs/seguranca/zap-baseline-report.json` e `docs/seguranca/zap-baseline-report.html`.

Reprodução:

```bash
docker run --rm --network host \
  -v "$(pwd)/docs/seguranca:/zap/wrk:rw" \
  -t zaproxy/zap-stable zap-baseline.py \
  -t http://localhost:8000/openapi.json \
  -J zap-baseline-report.json \
  -r zap-baseline-report.html \
  -I
```

### Warnings (aceitos)

| ID | Regra | Endpoints | Análise |
|---|---|---|---|
| 10049 | Non-Storable Content | `/api/v1/acompanhamento`, `/api/v1/saude`, `/robots.txt` | Respostas dinâmicas de API REST não devem ser cacheadas; comportamento correto. Falso positivo. |
| 90004 | Cross-Origin-Resource-Policy Header Missing | `/api/v1/saude`, `/openapi.json` | Header de isolamento de recursos opcional. Baixo risco para API backend sem contexto de browser embed. Aceito. |

Aviso do spider (`404` em `http://localhost:8000/`) é esperado -- a API não expõe rota raiz.

## Detecção de Segredos (gitleaks)

Scan executado em 29/04/2026 com gitleaks 8.30.1 -- working tree (sem `--no-git`) e histórico completo (`--log-opts="--all"`, 493 commits cobertos).

**Resultado**: 0 leaks no working tree e 0 no histórico após aplicar `.gitleaks.toml` allowlist documentado.

A allowlist cobre três falsos positivos legítimos (Caso D do workflow A/B/C/D):

1. `.env.dev` -- copia local DEV-ONLY do template, gitignorada (nao chega no repo).
2. `.env.dev.example` -- template commitado com `ENCRYPTION_KEY` DEV-ONLY (o proprio comentario do arquivo declara: "Valor abaixo e DEV-ONLY: basta ser estavel entre restarts; nunca use em prod").
3. `.nicegui/storage-user-*.json` -- runtime storage do NiceGUI (gitignored).
4. `tests/unitarios/scripts/test_seed_admin.py` -- fixtures de senha (`"S3nh4-Bem-Forte"`) usadas pelos testes do seeder de admin para validar regras de complexidade; nao sao credenciais reais.

Reproducao:

```bash
gitleaks detect --source . --no-git --config .gitleaks.toml \
  --report-format json --report-path docs/seguranca/gitleaks-wt-report.json --redact

gitleaks detect --source . --log-opts="--all" --config .gitleaks.toml \
  --report-format json --report-path docs/seguranca/gitleaks-history-report.json --redact
```

Relatórios: `docs/seguranca/gitleaks-wt-report.json` e `docs/seguranca/gitleaks-history-report.json`.

## Scan de Imagem Docker (trivy)

Scans executados em 29/04/2026 com trivy 0.69.3, filtrando por `--severity HIGH,CRITICAL`. Imagem auditada: `pytstop:audit` (build do `Dockerfile` runtime stage `python:3.12-slim`, Debian 13.4 trixie).

### trivy fs (deps Python via uv.lock)

**Resultado**: 3 HIGH em `nicegui 2.24.2`, todas com fix em majors 3.x:

| CVE | Pacote | Versão | Fix | Tipo |
|---|---|---|---|---|
| CVE-2025-66645 | nicegui | 2.24.2 | 3.4.0 | Path traversal em `app.add_media_files()` (read) |
| CVE-2026-21873 | nicegui | 2.24.2 | 3.5.0 | Zero-click XSS em `ui.sub_pages` |
| CVE-2026-25732 | nicegui | 2.24.2 | 3.7.0 | Path traversal em `FileUpload.name` (write) |

**Risco aceito** ([#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/112)): o `ui/` é dev-only (sandbox de teste manual, ver [#109](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/109) e [PR #81](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/81)); não roda em produção e não está empacotado pelo `pyproject.toml`. O upgrade nicegui 2->3 introduz breaking changes -- avaliação programada para Fase 2.

### trivy image (pacotes OS da imagem `pytstop:audit`)

**Resultado**: 6 HIGH sem fix upstream (Debian 13.4 trixie):

| CVE | Severity | Pacotes | Fix | Tipo |
|---|---|---|---|---|
| CVE-2025-69720 | HIGH | libncursesw6, libtinfo6, ncurses-base, ncurses-bin (6.5+20250216-2) | n/a | ncurses: buffer overflow, possível RCE |
| CVE-2026-29111 | HIGH | libsystemd0, libudev1 (257.9-1~deb13u1) | n/a | systemd: RCE/DoS via IPC |

**Risco aceito** ([#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/113)): ncurses não é usado pelo runtime FastAPI/uvicorn da app (puxado por dep transitiva da imagem base) e systemd não roda dentro do container (entrypoint é `uvicorn` direto). Avaliação de mitigação (distroless, alpine, bump da base) programada para Fase 2.

Reproducao:

```bash
docker build -t pytstop:audit .
trivy fs --severity HIGH,CRITICAL --format json \
  --output docs/seguranca/trivy-fs-report.json .
trivy image --severity HIGH,CRITICAL --format json \
  --output docs/seguranca/trivy-image-report.json pytstop:audit
```

Relatórios: `docs/seguranca/trivy-fs-report.json` e `docs/seguranca/trivy-image-report.json`.

## Recomendações para Produção

1. Adicionar WAF com rate limiting por usuário autenticado
2. Migrar segredo JWT para KMS (mitigado no MVP via validação de comprimento no startup)
3. Adicionar CSP headers (TD-003)
4. Evoluir consentimento com granularidade por finalidade de tratamento (RF-019 implementado com modelo básico)

## Referências

- [Tech Debt](../tech-debt.md) — Dívida técnica
- [ADR-004](../arquitetura/adr/004-autenticacao-jwt.md) — Autenticação JWT
- [ADR-011](../arquitetura/adr/011-pipeline-seguranca-analise-estatica.md) — Pipeline de Segurança e Análise Estática
- [ADR-012](../arquitetura/adr/012-licenciamento-software-sbom.md) — Licenciamento de Software e SBOM
- [Plano de Segurança](plano-seguranca.md) — Plano de Segurança do MVP
- [Requisitos](../requisitos/requisitos.md) — RF-011, RF-012, RF-013, RF-015, RF-019

> [↑ Raiz do projeto](../../README.md) · [↑ Segurança](README.md)
