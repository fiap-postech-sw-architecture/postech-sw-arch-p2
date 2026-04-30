# full-test — Harness E2E concorrente

Suite de testes end-to-end que exercita uma **instancia viva** do PyTStop
(via `docker compose up`) com multiplos usuarios simulados em paralelo. Cobre
45 endpoints da API e valida invariantes de consistencia a cada mutacao.

Suite PARALELA ao `tests/` principal: nao compartilha fixtures, conftest, nem
imports. Rodar via `make full-test` (local) ou workflow `full-test-ci`
(GitHub Actions).

## Quick start

```bash
# Subir stack + rodar tudo (inclui sleeps reais — leva minutos)
make full-test

# Subir stack + rodar so o plano CI (sem sleeps)
make full-test-ci

# Individual:
make full-test-up        # docker compose up + health-wait
make full-test-seed      # seeds idempotentes
make full-test-run       # pytest plano full
make full-test-teardown  # docker compose down + limpa reports
```

## Modos de execucao

Dois modos, separados por pytest markers:

| Modo | Comando | Inclui `slowest`? | Tempo tipico | Uso |
|---|---|---|---|---|
| `full` | `make full-test-run` | Sim | 3-5 min | Local, validacao antes de PR |
| `ci`   | `make full-test-ci` ou `pytest -m "not slowest"` | Nao | 30-60s | GitHub Actions (workflow nightly) |

### Markers

- `@pytest.mark.slowest` — journey com sleeps obrigatorios >= 1s (apenas `ClienteFluxoCompletoJourney`)
- `@pytest.mark.slow` — journey contra instancia viva, sem sleep (roda em CI)

**Default e conservador:** `pytest` sem flag roda TUDO (slowest incluso). CI precisa opt-out explicito com `-m "not slowest"`.

## Journeys (cenarios cobertos)

| # | Journey | Papel | Cobertura |
|---|---|---|---|
| 6  | `ClienteFluxoCompletoJourney`       | cliente (admin executa) | Happy path OS + `/acompanhamento` publico apos cada transicao (slowest) |
| 7  | `ClienteFluxosAlternativosJourney`  | cliente | Cancelamento em cada estado + complementar aprovado/rejeitado + 409s |
| 8  | `AtendenteJourney`                  | ATENDENTE | Cadastro cliente/veiculo + LGPD + consentimentos |
| 9  | `MecanicoJourney`                   | MECANICO | Itens + diagnostico + orcamento + RBAC negativo (403 em aprovar) |
| 10 | `AdminConcurrencyJourney`           | ADMIN   | Estoque concorrente — N threads ajustam qty do mesmo item |
| 11 | `MetricasFixtureJourney`            | ADMIN   | Valida `tempo_medio_execucao_minutos` com timestamps injetados no DB |
| 12 | `RbacMatrixJourney`                 | todos   | Matriz 45 x 4 = 180 celulas (endpoint x papel -> status esperado) |

### Requisitos explicitos cobertos

1. **Cliente consulta status SEM login** — `ClienteFluxoCompletoJourney` chama `GET /api/v1/acompanhamento` apos cada transicao da OS. `RbacMatrixJourney` tambem confirma que o endpoint responde sem token (200/404) e que o 404 tem shape constante.
2. **Media de tempo de execucao** — `MetricasFixtureJourney` e owner no modo `ci` (injeta timestamps no DB para agregacao determinista). No modo `full`, `ClienteFluxoCompletoJourney` gera dados reais via sleeps 2-5s.

## Variaveis de ambiente

Criadas por `full-test/.env.example`; os targets do Makefile criam
`full-test/.env` automaticamente antes da primeira execucao.

| Variavel | Default | Descricao |
|---|---|---|
| `FULL_TEST_BASE_URL` | `http://localhost:8000` | URL base da API |
| `FULL_TEST_DATABASE_URL` | `postgresql://pytstop:pytstop@localhost:5432/pytstop` | Usado apenas por seeders (bypass da API) |
| `FULL_TEST_ADMIN_EMAIL` | `full-test-admin@pytstop.local` | Admin semeado pelo `scripts/seed_admin.py` do app |
| `FULL_TEST_ADMIN_PASSWORD` | `ChangeMeStrong123!` | Precisa >= 12 chars |
| `FULL_TEST_N_CLIENTES` | `4` | N de `ClienteFluxoCompletoJourney` (multiplicado por 2 no plano_full) |
| `FULL_TEST_N_OPERADORES` | `2` | N de `AtendenteJourney` e `MecanicoJourney` |
| `FULL_TEST_N_ADMINS` | `1` | N de `AdminConcurrencyJourney` |
| `FULL_TEST_HTTP_TIMEOUT` | `30` | Timeout HTTP (segundos) |
| `FULL_TEST_SEED` | `20260422` | Seed do random (None = clock) |
| `FULL_TEST_RESET_ANTES_DE_SEED` | `1` | Se `0`, pula o reset (util em CI com DB fresco) |

## Troubleshooting

**"Connection refused" no healthwait**
-> `docker compose up -d` terminou antes do app subir. Aumentar `--timeout`: `uv run python -m full_test healthwait --timeout 180`. Ou conferir: `docker compose logs app`.

**"FULL_TEST_DATABASE_URL obrigatoria"**
-> Faltou copiar `full-test/.env.example` pra `full-test/.env`. A CLI carrega `.env` relativo ao pacote, nao ao cwd.

**"email is not valid: reserved name"**
-> Dominio `.local` / `.test` / `.example` sao reservados por RFC e pydantic EmailStr rejeita. Usar `.dev` nos admin/mecanico/atendente seeds.

**"CPF invalido" ao fazer GET /clientes/** (erro 500 em volta da reconstrucao do VO)
-> Indicativo de `ENCRYPTION_KEY` ausente ou divergente: o app gera chave efemera sem `ENCRYPTION_KEY`, e ciphertexts antigos perdem decifracao apos restart do container. Gerar uma chave estavel e adicionar no `.env.dev`:
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

**"Token revogado" em varias journeys**
-> Token admin compartilhado foi revogado por alguma journey. Confirmar que:
- Journeys admin (`ClienteFluxoCompleto`, `ClienteFluxosAlternativos`, `AdminConcurrency`, `MetricasFixture`) NAO chamam `logout` em teardown.
- `RbacMatrixJourney` usa `_login_descartavel` pra celula `/autenticacao/logout`.

**Testes da journey cliente-fluxo-completo estouram timeout em CI**
-> Sao `@pytest.mark.slowest`. CI DEVE rodar com `-m "not slowest"` — conferir workflow.

**"tempo_medio_execucao_minutos veio None"**
-> `MetricasFixtureJourney` rodou mas nenhuma ordem chegou em FINALIZADA. Verificar o log estruturado `full-test/reports/<timestamp>-ci.json` — buscar `passo=fabricar-ordem-*` com `sucesso=false`.

**"429 Rate limit" no inicio da suite**
-> `SystemClient` tem retry-on-429 com backoff exponencial (cap 70s, 8 retries). Se ainda estourar: reduzir `FULL_TEST_N_CLIENTES`, ou o rate limit da API e mais restritivo que o documentado. `/acompanhamento` (publico) tem limite 10/min por IP — afeta `ClienteFluxoCompletoJourney`.

**"AVISO: lost-update detectado" em AdminConcurrencyJourney** (NAO falha a journey)
-> Sinal de design de API. `PATCH /quantidade` aceita valor absoluto. Mesmo com `SELECT FOR UPDATE` no server, threads que fazem leitura-modificacao-escrita em paralelo podem sobrepor (read stale + write overwrite). A journey loga o achado como aviso sem falhar; para garantia forte seria necessario endpoint de delta ou optimistic concurrency (ETag/If-Match).

**Matriz RBAC falha em endpoint novo**
-> A matriz e escrita a mao em `full_test/journeys/rbac_matrix.py`. Se um endpoint foi adicionado ao app, adicionar a entrada correspondente. Se uma permissao mudou intencionalmente, atualizar o status esperado.

## Integracao CI

Workflow `.github/workflows/full-test-ci.yml`:

- Trigger: `workflow_dispatch` (manual) + cron diario 04:00 UTC
- Job `ci-plan`: sobe docker compose, roda `pytest -m "not slowest"`, faz upload do JSON de relatorio (retention 14 dias)
- NAO e bloqueante em PRs por default. Depois de estabilizar por alguns ciclos, considerar mover para `on: [pull_request]`

## Estrutura

- `full_test/client/`       — facade tipada sobre os 45 endpoints
- `full_test/seeders/`      — seeders idempotentes (DB + API)
- `full_test/journeys/`     — 7 classes de journey (steps 6-12)
- `full_test/orchestrator/` — plano de execucao + ThreadPoolExecutor
- `full_test/support/`      — ConsistencyChecker, StepLogger, health, documentos
- `tests/`                  — entrypoint pytest + testes unitarios
- `reports/`                — JSON de saida por execucao (gitignored)
