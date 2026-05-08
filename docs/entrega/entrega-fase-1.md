# Documento de Entrega — Tech Challenge Fase 1

> [↑ Raiz do projeto](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1) · [↑ Entrega](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/tree/main/docs/entrega)

> **Versão**: 1.0 — Maio/2026.

Documento de entrega da Fase 1 do Tech Challenge da Pós-Graduação em Arquitetura de Software (FIAP). O conteúdo cobre os itens exigidos pelo enunciado da fase: identificação do grupo, link do repositório, link da documentação, link do vídeo e relatório de análise de vulnerabilidades.

---

## 1. Identificação do Grupo

| Campo | Valor |
|---|---|
| Nome do grupo | PytStop |
| Turma | 15SOAT — Pós-Graduação em Arquitetura de Software (FIAP) |

### Participantes

| Nome | Discord |
|---|---|
| João Amaral | jbamaral |
| Allan Aurélio | all66_ |
| Carlos Silva | carlossilva156 |
| Guilherme Sousa | romen0 |
| Nicolas Gerbi | sethiiz_gerbi |

## 2. Link do Repositório

Repositório privado no GitHub, com `soat-architecture` adicionado como colaborador conforme exigido pelo enunciado.

| Recurso | URL |
|---|---|
| Repositório | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1 |
| README (instruções de uso e execução) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/README.md |
| Dockerfile | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/Dockerfile |
| docker-compose.yml | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docker-compose.yml |

## 3. Link do Vídeo

Vídeo de até 15 minutos demonstrando os pontos exigidos pela fase.

| Recurso | URL |
|---|---|
| Vídeo de demonstração | https://drive.google.com/file/d/1-oXKWb4FcGxZtX2Pee7A6r2QWt4od8HD/view?usp=drive_link |

## 4. Link da Documentação

Toda a documentação versionada está no próprio repositório, na pasta `docs/`. A tabela abaixo lista o índice geral e os artefatos exigidos pela fase: documentação DDD (Event Storming, Domain Storytelling, Linguagem Ubíqua, Mapa de Contextos e Modelo de Domínio).

### 4.1 Índice geral da documentação

| Recurso | URL |
|---|---|
| Pasta `docs/` (índice) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/tree/main/docs |

### 4.2 Documentação DDD (obrigatória pela fase)

| Artefato | URL |
|---|---|
| Workshop de Event Storming | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/arquitetura/event-storming/workshop-event-storming.md |
| Event Storming — Fluxo 1: Ciclo de Vida da OS | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/arquitetura/event-storming/fluxo-1-ciclo-os.md |
| Event Storming — Fluxo 2: Gestão de Peças e Insumos | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/arquitetura/event-storming/fluxo-2-gestao-estoque.md |
| Domain Storytelling — Diagramas e entrevistas | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/tree/main/docs/arquitetura/domain-storytelling |
| Linguagem Ubíqua (Glossário) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/requisitos/glossario.md |
| Mapa de Contextos | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/arquitetura/mapa-contextos.md |
| Modelo de Domínio | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/arquitetura/modelo-dominio.md |
| Miro — Event Storming | https://miro.com/app/board/uXjVGqQ_lk4=/ |
| Miro — Domain Storytelling | https://miro.com/app/board/uXjVGqQ_lk4=/ |

## 5. Relatório de Análise de Vulnerabilidades

Análise de segurança do MVP back-end conforme **OWASP API Security Top 10 (2023)**. A bateria automatizada foi executada em 29/04/2026 (bandit, pip-audit, gitleaks, trivy fs+image, SonarQube) e em 02/05/2026 (OWASP ZAP baseline).

### 5.1 Ferramentas utilizadas

| Ferramenta | Tipo | Cobertura |
|---|---|---|
| SonarQube | SAST + qualidade | Código-fonte, code smells, cobertura |
| OWASP ZAP | DAST baseline | API rodando localmente, 49 URLs via OpenAPI |
| bandit | SAST Python | `src/` |
| pip-audit | SCA — CVEs | 98 dependências (diretas + transitivas) |
| gitleaks | Detecção de segredos | Working tree e histórico (493 commits) |
| trivy | SCA — filesystem e imagem Docker | `uv.lock` e imagem `pytstop:audit` |

### 5.2 Resultado consolidado

| Severidade | Bandit | pip-audit | gitleaks (wt) | gitleaks (hist) | trivy fs | trivy image | OWASP ZAP |
|---|---|---|---|---|---|---|---|
| HIGH/CRITICAL | 0 | 0 | 0 | 0 | 3 \* | 6 \* | 0 |
| WARN | — | — | — | — | — | — | 2 \*\* |

\* Riscos aceitos como dívida técnica:

- 3 HIGH em `nicegui 2.24.2` — sandbox dev-only, não roda em produção e não está empacotada pelo `pyproject.toml`. Issue [#112](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/112).
- 6 HIGH em pacotes de SO (`ncurses`, `systemd`) sem fix upstream e não usados pelo runtime FastAPI/uvicorn. Issue [#113](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/issues/113).

\*\* Os 2 WARNs do ZAP são falsos positivos esperados em API REST: cabeçalho `Cache-Control` em respostas dinâmicas e `Cross-Origin-Resource-Policy` opcional para backend sem contexto de browser embed.

### 5.3 Achados específicos do MVP

Achados levantados na revisão inicial do projeto e respectivas mitigações implementadas no código.

| # | Severidade | Achado | Status | Mitigação |
|---|---|---|---|---|
| 1 | Baixa | CPF/CNPJ armazenados em texto plano | Mitigado | Cifragem simétrica Fernet (AES-128-CBC + HMAC-SHA256) via `EncryptionService`; índice determinístico `documento_hash` (HMAC-SHA256) para busca; anonimização irreversível com tombstone (RF-011, RF-015). |
| 2 | Informativo | Ausência de endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | Implementado | `GET /clientes/{id}/dados-pessoais`, `GET .../exportar` e `DELETE .../dados-pessoais` com anonimização irreversível. |
| 3 | Informativo | Ausência de mecanismo de consentimento explícito | Implementado | `POST /clientes/{id}/consentimento` e `DELETE .../consentimento` com a entidade `ConsentimentoCliente` (RF-019). |
| 4 | Informativo | JWT sem revogação e sem refresh tokens | Implementado | Tabela `tokens_revogados` com JTI, logout via `POST /autenticacao/logout`, refresh com rotação via `POST /autenticacao/refresh` (RF-012, RF-013). |

### 5.4 Conformidade OWASP Top 10 (2021)

Os dez tópicos do OWASP Top 10 foram mapeados com mitigações aplicadas no MVP — RBAC com três papéis e autorização granular por endpoint (A01); cifragem Fernet de PII em repouso, JWT HS256 com enforcement de algoritmo e bcrypt de senhas (A02); SQLAlchemy ORM com queries parametrizadas e Pydantic com `extra="forbid"` (A03); arquitetura DDD + Onion com fronteiras explícitas entre camadas (A04); security headers, Swagger desabilitado em produção e CORS com whitelist (A05); pip-audit e SBOM via CycloneDX (A06, A08); rotação de refresh tokens e rate limiting por IP (A07); structlog em JSON com `request_id` (A09); sem fetch externo no escopo atual (A10). Detalhes na seção correspondente do relatório completo.

### 5.5 Conclusão

Os scans automatizados não acusam vulnerabilidades exploráveis no código de produção. Todos os HIGHs detectados estão restritos a componentes _dev-only_ (sandbox de UI) ou pacotes de SO não exercidos pelo runtime, e foram aceitos como dívida técnica com issues abertas e plano de evolução para a Fase 2. Os achados qualitativos da revisão inicial (PII em texto plano, requisitos de LGPD e revogação de JWT) foram mitigados no MVP via cifragem, endpoints de Art. 18, consentimento explícito e tabela de tokens revogados.

### 5.6 Documentos completos

| Documento | URL |
|---|---|
| Relatório de Vulnerabilidades (completo) | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/seguranca/relatorio-vulnerabilidades.md |
| Plano de Segurança | https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/blob/main/docs/seguranca/plano-seguranca.md |

---

> [↑ Raiz do projeto](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1) · [↑ Entrega](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/tree/main/docs/entrega)
