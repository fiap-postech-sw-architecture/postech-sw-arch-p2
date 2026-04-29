# Apêndice A — Funcionalidades Extras Implementadas

> Documento complementar ao [Documento de Entrega — Fase 1](documento-entrega-fase-1.md). Descreve as features que foram implementadas **além** do escopo mínimo do desafio FIAP, com a motivação por trás de cada decisão (ancorada em commits/PRs do histórico).

## Critério para "extra"

Comparação direta com [docs/requisitos/desafio-tech-fase-1.md](../requisitos/desafio-tech-fase-1.md). Tudo que o desafio não exige explicitamente entra como extra. Exclui-se aqui o que a FIAP listou como obrigatório (CRUDs, fluxo de OS com 6 status, JWT básico, validação de CPF/CNPJ/placa, Docker, Swagger, README, cobertura ≥80%, relatório de vulnerabilidades).

## A.1 Segurança e LGPD (5 features)

| Feature | RF | Onde vive | Origem | Motivação |
|---|---|---|---|---|
| Encriptação de PII (Fernet) + hash HMAC-SHA256 como índice | RF-011 | `src/compartilhado/infraestrutura/encryption_service.py`, `src/cliente_veiculo/infraestrutura/mapping.py` | PR #65 (commit `b4a0bd2`, 2026-04-16) | LGPD não é exigida pelo desafio. O achado #1 do relatório de vulnerabilidades classificou CPF/CNPJ em texto plano como Baixa (CVSS 3.1); a equipe escolheu cifragem simétrica em repouso + hash determinístico para busca sem expor o documento original. |
| Endpoints LGPD Art. 18 (acesso, portabilidade, exclusão) | RF-015 | `src/cliente_veiculo/aplicacao/lgpd_use_cases.py`; rotas `/clientes/{id}/dados-pessoais[/exportar]` | PR #65 | Achado #2 do relatório (Informativo). Endpoints implementam direitos do titular previstos em lei. A anonimização irreversível usa SQLAlchemy Core com tombstone para bypassar listeners de criptografia. |
| Consentimento explícito | RF-019 | `src/cliente_veiculo/dominio/consentimento.py`; rotas `/clientes/{id}/consentimento` | PR #65 | Achado #3 (Informativo). Modelagem com entidade `ConsentimentoCliente` e revogação por evento de domínio. |
| Mascaramento de PII em respostas e logs | — | `mascarado()` nos schemas de listagem; `field(repr=False)` em DTOs com PII | parte de PR #65 + ajustes ao longo do projeto | Defesa em profundidade: mesmo com cifragem em repouso, evitar vazamento por logs estruturados ou tracebacks. |
| Tombstone determinístico em anonimização | RF-015 | `src/cliente_veiculo/infraestrutura/repository.py:anonimizar_dados()` | parte de PR #65 (correção em commit dedicado) | Bug descoberto durante testes: ORM listeners re-cifravam o tombstone. A solução foi usar SQLAlchemy Core (`sqlalchemy.update()`) para escapar dos listeners. |

## A.2 Hardening de Autenticação (3 features)

| Feature | RF | Onde vive | Origem | Motivação |
|---|---|---|---|---|
| Revogação de JWT (blacklist por JTI) | RF-012 | `src/autenticacao/dominio/token_revogado.py`; rota `POST /autenticacao/logout` | PR #64 (commit `e028e63`, 2026-04-16) | Desafio exigia "JWT auth"; o achado #4 do relatório (Informativo, CVSS 2.0) flagou ausência de revogação. A equipe adicionou tabela `tokens_revogados` para invalidação antes do `exp`. |
| Refresh tokens com rotação | RF-013 | `src/autenticacao/aplicacao/refresh_use_case.py`; rota `POST /autenticacao/refresh` | PR #64 | Mesma origem de RF-012. Rotação previne reuso de refresh; TTL configurável; ADR-004. |
| RBAC com Enum `Papel` (admin/mecanico/atendente) + hierarquia | RF-014 | `src/autenticacao/dominio/papel.py`; `exigir_papel(...)` em todos os routers | PR #64 + PR #75 (commit `a406756`, 2026-04-20) | Desafio só pedia auth; a equipe adicionou autorização granular por endpoint, conforme ADR-004. A hierarquia (PR #75) permite herança de permissões. |

## A.3 Extensão do Fluxo de OS (2 features)

| Feature | RF | Onde vive | Origem | Motivação |
|---|---|---|---|---|
| Orçamento complementar (8º status `AGUARDANDO_APROVACAO_COMPLEMENTAR`) | RF-016 | `src/ordem_servico/dominio/status.py`; use cases `Gerar/Aprovar/Rejeitar OrcamentoComplementar` | PR #62 (commit `1ff1b6c`, 2026-04-15) | Desafio definiu 6 status; durante o refinamento via Domain Storytelling (entrevistas com Reginaldo/Leandro) emergiu a necessidade de re-orçamento mid-execution sem cancelar a OS. |
| Histórico de orçamentos (JSONB array) | RF-017 | `OrdemDeServico.orcamentos_anteriores`; coluna `orcamentos_json` | PR #62 | Auditoria: cada novo orçamento empilha o anterior, preservando trilha completa. |

## A.4 Arquitetura (3 features)

| Feature | Onde vive | Origem | Motivação |
|---|---|---|---|
| DDD + Onion Architecture (não monolito em camadas simples) | Todo o `src/` em 5 contextos delimitados | ADR-003 (2026-03-11), commit `7296d0d` | Desafio diz: *"é possível criar um Monolito utilizando arquitetura em camadas"*. A equipe foi além para garantir desacoplamento de framework e evolução para microsserviços nas fases seguintes. |
| Mapeamento imperativo SQLAlchemy (`registry.map_imperatively()`) | `src/*/infraestrutura/mapping.py` | ADR-006 (2026-03-20) | Mantém entidades como classes Python puras; o domínio não importa SQLAlchemy. |
| Bloqueio pessimista (`SELECT FOR UPDATE NOWAIT`) com locks ordenados | `src/estoque/infraestrutura/repository.py` | ADR-008 | Evita race condition na reserva atômica de estoque entre múltiplas OS aprovadas em paralelo. NOWAIT (fail-fast) + ordem crescente de `item_id` previne deadlocks. |

## A.5 Qualidade e Testes (3 features)

| Feature | Onde vive | Origem | Motivação |
|---|---|---|---|
| BDD com pytest-bdd + Gherkin em PT | `tests/e2e/features/`, `tests/e2e/steps/` | ADR-013 | Desafio só pedia "testes unitários e integração". O BDD funciona como documentação viva alinhada à Linguagem Ubíqua (PT). |
| Domain Storytelling | `docs/arquitetura/domain-storytelling/` (5 entrevistas + diagramas egon.io) | PR #19 (commit `4e3f3e4`, 2026-03-13) | Desafio pediu Event Storming; a equipe adicionou Domain Storytelling para captura de regras implícitas via entrevistas simuladas com 5 personas (Seu Carlos, Dona Marta, Reginaldo, Leandro, Fábio). |
| Cobertura 97.75% global, 100% domínio em todos os contextos | `pyproject.toml` config + tests | ao longo do projeto | A meta era 80% nos críticos; superada significativamente para reduzir risco de regressão. |

## A.6 Pipeline e DX (3 features)

| Feature | Onde vive | Origem | Motivação |
|---|---|---|---|
| Pipeline de segurança em 3 camadas: ruff/mypy + bandit (camadas 1-2 automatizadas em CI) + pip-audit/gitleaks/trivy/SonarQube (projetados em ADR-011, automação pendente nas issues #103–#108) | `.github/workflows/ci.yml`, `pyproject.toml`, `docs/arquitetura/adr/011-pipeline-seguranca-analise-estatica.md` | ADR-011 | Desafio pediu "relatório de vulnerabilidades"; a equipe desenhou pipeline em camadas (RNF-010/014/015) e automatizou as duas primeiras; o restante está em backlog rastreado por issues. |
| SBOM via CycloneDX + política de licenças permissivas (projetado, automação pendente na issue #108) | `docs/arquitetura/adr/012-licenciamento-software-sbom.md` | ADR-012 | Cadeia de suprimentos; conformidade de licença (apenas MIT/BSD/Apache). |
| UI de simulação NiceGUI (dev-only, fora de empacotamento) | `ui/` | PR #81 (commit `fba330f`, 2026-04-27) | Não exigida pelo desafio. Sandbox para teste manual da API: 7 páginas, fluxo de auth com refresh, painel request/response, seed coerente, visualização da máquina de estados da OS. Não está em `pyproject.toml` `setuptools.packages.find` (não empacotada). |

## Total

**19 funcionalidades extras** distribuídas em:

- 5 em Segurança/LGPD
- 3 em Auth Hardening
- 2 em Extensão de OS
- 3 em Arquitetura
- 3 em Qualidade
- 3 em Pipeline/DX

## Referência rápida de PRs

| PR | Data | Features cobertas |
|---|---|---|
| [#19](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/19) | 2026-03-13 | Domain Storytelling |
| [#62](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/62) | 2026-04-15 | RF-016 (orçamento complementar), RF-017 (histórico) |
| [#64](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/64) | 2026-04-16 | RF-012, RF-013, RF-014 (revogação, refresh, RBAC) |
| [#65](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/65) | 2026-04-16 | RF-011, RF-015, RF-019 (LGPD completo) |
| [#75](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/75) | 2026-04-20 | Hierarquia RBAC |
| [#81](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p1/pull/81) | 2026-04-27 | NiceGUI UI (dev-only) |
