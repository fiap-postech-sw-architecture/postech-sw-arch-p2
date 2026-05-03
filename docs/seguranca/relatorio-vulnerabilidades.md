# Relatorio de Vulnerabilidades

> **Versao**: 2.1 -- bateria de scans automatizados executada em 29/04/2026 (bandit, pip-audit, gitleaks, trivy fs+image); SonarQube executado e fechado em [#107](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/107); OWASP ZAP baseline executado em 02/05/2026 -- 0 FAIL / 2 WARN aceitos (fechado em [#108](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/108)).

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

Bateria executada em 29/04/2026 (bandit, pip-audit, gitleaks, trivy fs+image) e em 02/05/2026 (OWASP ZAP baseline + Bandit reexecutado apos mitigacao do B104). SonarQube ainda pendente, rastreado em [#107](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/107) -- ver secao "Analise Estatica e Qualidade (SonarQube)" abaixo.

| Severidade | Bandit | pip-audit | gitleaks (wt) | gitleaks (hist) | trivy fs | trivy image | ZAP |
|---|---|---|---|---|---|---|---|
| HIGH/CRITICAL | 0 | 0 | 0 | 0 | 3 | 6 | 0 |
| MEDIUM | 0 | -- | -- | -- | (filtro HIGH+) | (filtro HIGH+) | -- |
| WARN | -- | -- | -- | -- | -- | -- | 2 |
| LOW | 0 | -- | -- | -- | (filtro HIGH+) | (filtro HIGH+) | -- |

Avaliacao consolidada do risco automatizado:

- **Bandit (SAST Python)**: 0 HIGH / 0 MEDIUM / 0 LOW em `src/`. O B104 foi mitigado: `python src/main.py` usa `127.0.0.1` por padrao e o bind em todas as interfaces fica explicito apenas no entrypoint do container.
- **pip-audit (CVE em dependencias diretas e transitivas)**: 98 deps auditadas, 0 vulnerabilidades.
- **gitleaks (segredos no working tree e em todo o historico Git)**: 0 leaks apos `.gitleaks.toml` documentar 3 falsos positivos (template DEV-ONLY, runtime do NiceGUI, fixtures de senha de teste).
- **trivy fs (CVE em deps Python via uv.lock)**: 3 HIGH em `nicegui 2.24.2` -- todas com fix em majors 3.x; aceitos como divida ([#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/112)) porque `ui/` e dev-only e nao roda em producao.
- **trivy image (CVE em pacotes OS da imagem `pytstop:audit`)**: 6 HIGH (`ncurses` e `systemd`) sem fix upstream; aceitos como divida ([#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/113)) porque os pacotes nao sao usados pelo runtime FastAPI/uvicorn da app.
- **OWASP ZAP (DAST baseline)**: 0 FAIL / 2 WARN aceitos / 65 PASS. Cobertura de 49 URLs via OpenAPI spec. WARNs sao falsos positivos esperados para API REST (detalhados na secao abaixo). Caso A.

## Analise Estatica (bandit)

Scan reexecutado em 02/05/2026 com bandit 1.9.4 sobre `src/`.

| # | Arquivo | Linha | ID | Severidade | Confianca | Descricao | Status |
|---|---|---|---|---|---|---|---|
| -- | -- | -- | -- | -- | -- | Nenhum achado | LIMPO |

**Detalhamento**:

- **B104 (hardcoded_bind_all_interfaces)**: mitigado em `src/main.py`. A execucao direta usa `UVICORN_HOST` com default `127.0.0.1`; em Docker, o bind `0.0.0.0` continua no `entrypoint.sh`, onde e necessario para expor a porta do container.

Sem regressao em relacao ao baseline de 16/04 e sem riscos aceitos remanescentes no Bandit. Relatorio JSON em `docs/seguranca/bandit-report.json`; regenerar com `uv run bandit -r src/ -f json -o docs/seguranca/bandit-report.json`.

## Auditoria de Dependencias (pip-audit)

Scan executado em 29/04/2026 via `uv run --with pip-audit pip-audit --format json --output docs/seguranca/pip-audit-report.json` (ambiente efemero, sem poluir o `.venv`).

**Resultado**: 98 dependencias auditadas; **0 vulnerabilidades conhecidas**. O proprio pacote `pytstop` foi pulado (`Dependency not found on PyPI`) porque e um projeto local nao publicado.

Relatorio JSON em `docs/seguranca/pip-audit-report.json`. Reproducao:

```bash
uv run --with pip-audit pip-audit --format json --output docs/seguranca/pip-audit-report.json
```

## Analise Estatica e Qualidade (SonarQube)

**TODO**: executar antes da entrega. Configuracao conforme ADR-011.

## Teste Dinamico de Seguranca (OWASP ZAP)

Scan executado em 02/05/2026 com `zaproxy/zap-stable` (modo baseline passivo) contra `http://localhost:8000/openapi.json` com stack completa rodando via `docker compose up -d` (PostgreSQL + app + seed de admin).

**Resultado**: 65 PASS / 0 FAIL / 2 WARN. Caso A.

Relatorios em `docs/seguranca/zap-baseline-report.json` e `docs/seguranca/zap-baseline-report.html`.

Reproducao:

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

| ID | Regra | Endpoints | Analise |
|---|---|---|---|
| 10049 | Non-Storable Content | `/api/v1/acompanhamento`, `/api/v1/saude`, `/robots.txt` | Respostas dinamicas de API REST nao devem ser cacheadas; comportamento correto. Falso positivo. |
| 90004 | Cross-Origin-Resource-Policy Header Missing | `/api/v1/saude`, `/openapi.json` | Header de isolamento de recursos opcional. Baixo risco para API backend sem contexto de browser embed. Aceito. |

Aviso do spider (`404` em `http://localhost:8000/`) e esperado -- a API nao expoe rota raiz.

## Deteccao de Segredos (gitleaks)

Scan executado em 29/04/2026 com gitleaks 8.30.1 -- working tree (sem `--no-git`) e historico completo (`--log-opts="--all"`, 493 commits cobertos).

**Resultado**: 0 leaks no working tree e 0 no historico apos aplicar `.gitleaks.toml` allowlist documentado.

A allowlist cobre tres falsos positivos legitimos (Caso D do workflow A/B/C/D):

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

Relatorios: `docs/seguranca/gitleaks-wt-report.json` e `docs/seguranca/gitleaks-history-report.json`.

## Scan de Imagem Docker (trivy)

Scans executados em 29/04/2026 com trivy 0.69.3, filtrando por `--severity HIGH,CRITICAL`. Imagem auditada: `pytstop:audit` (build do `Dockerfile` runtime stage `python:3.12-slim`, debian 13.4 trixie).

### trivy fs (deps Python via uv.lock)

**Resultado**: 3 HIGH em `nicegui 2.24.2`, todas com fix em majors 3.x:

| CVE | Pacote | Versao | Fix | Tipo |
|---|---|---|---|---|
| CVE-2025-66645 | nicegui | 2.24.2 | 3.4.0 | Path traversal em `app.add_media_files()` (read) |
| CVE-2026-21873 | nicegui | 2.24.2 | 3.5.0 | Zero-click XSS em `ui.sub_pages` |
| CVE-2026-25732 | nicegui | 2.24.2 | 3.7.0 | Path traversal em `FileUpload.name` (write) |

**Risco aceito** ([#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/112)): o `ui/` e dev-only (sandbox de teste manual, ver [#109](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/109) e [PR #81](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/81)); nao roda em producao e nao esta empacotado pelo `pyproject.toml`. O upgrade nicegui 2->3 introduz breaking changes -- avaliacao programada para Fase 2.

### trivy image (pacotes OS da imagem `pytstop:audit`)

**Resultado**: 6 HIGH sem fix upstream (debian 13.4 trixie):

| CVE | Severity | Pacotes | Fix | Tipo |
|---|---|---|---|---|
| CVE-2025-69720 | HIGH | libncursesw6, libtinfo6, ncurses-base, ncurses-bin (6.5+20250216-2) | n/a | ncurses: buffer overflow, possivel RCE |
| CVE-2026-29111 | HIGH | libsystemd0, libudev1 (257.9-1~deb13u1) | n/a | systemd: RCE/DoS via IPC |

**Risco aceito** ([#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/113)): ncurses nao e usado pelo runtime FastAPI/uvicorn da app (puxado por dep transitiva da imagem base) e systemd nao roda dentro do container (entrypoint e `uvicorn` direto). Avaliacao de mitigacao (distroless, alpine, bump da base) programada para Fase 2.

Reproducao:

```bash
docker build -t pytstop:audit .
trivy fs --severity HIGH,CRITICAL --format json \
  --output docs/seguranca/trivy-fs-report.json .
trivy image --severity HIGH,CRITICAL --format json \
  --output docs/seguranca/trivy-image-report.json pytstop:audit
```

Relatorios: `docs/seguranca/trivy-fs-report.json` e `docs/seguranca/trivy-image-report.json`.

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
