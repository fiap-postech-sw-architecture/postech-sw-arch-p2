# Step 11 — Ordem de Servico Interfaces — Review Findings

PR branch: `pr/11-os-interfaces`
Baseline before review: 797 tests, 99.09% coverage (main.py at 73% due to lifespan not triggered by existing tests).
Final state after review: **800 tests, 99.81% coverage**, every target file under
`src/ordem_servico/interfaces/` at 100% line coverage, `src/main.py` at
100%, `src/compartilhado/interfaces/router_publico.py` at 100%.

The 16 parallel perspectives + 3 sequential polish (#17 → #18 → #17) ran against
the working-directory state on `pr/11-os-interfaces`.

## Files in scope

**New source (4 files, ~520 LOC):**
- `src/ordem_servico/interfaces/__init__.py`
- `src/ordem_servico/interfaces/router.py` — 15 endpoints
- `src/ordem_servico/interfaces/schemas.py` — 11 Pydantic schemas
- `src/ordem_servico/interfaces/dependencies.py` — 15 factory functions

**New tests (3 files):**
- `tests/unitarios/ordem_servico/test_router_os.py`
- `tests/unitarios/ordem_servico/test_schemas_os.py`
- `tests/unitarios/ordem_servico/test_dependencies_os.py`

**Modified:**
- `src/compartilhado/interfaces/router_publico.py` — add `/api/v1/acompanhamento`
  public endpoint with rate limit + lazy wiring to `ConsultarAcompanhamento`
- `src/main.py` — register 4 routers (cliente, catalogo, estoque, os) + lifespan
  mapping initialization for the same 4 contexts (latent bug fix: prior PRs
  never wired any context's router into the app)
- `tests/unitarios/test_main.py` — lifespan test now uses `with TestClient(...)`
  context manager (FastAPI requires it to trigger startup/shutdown)
- `tests/unitarios/compartilhado/test_router_publico.py` — 3 new acompanhamento
  tests (hit, miss 404, missing params 422)

## Latent bug fix (scope expansion justification)

`src/main.py` on `main` (post PR #62 merge) registered ONLY `router_publico`.
Every prior bounded-context router (cliente_veiculo from PR #58, catalogo from
PR #59, estoque from PR #60, ordem_servico from this PR) was never wired into
the FastAPI app. Additionally, none of the contexts' `iniciar_mapeamentos()`
functions were called from the lifespan. The real app running on production
would have crashed on first query.

PR #11 fixes this by registering all 4 routers (cliente, catalogo, estoque, os)
AND initializing all 4 mappings in the lifespan. Auth router registration is
correctly deferred to PR #12 per the spec. This scope expansion is justified
because the alternative — registering ONLY os_router while leaving 3 others
orphaned — would ship an even more broken main.py.

The `tests/unitarios/test_main.py::test_lifespan_configura_logging_e_mapeamentos`
fix (using `with TestClient(app) as client:`) is the mechanical consequence
of adding actual lifespan body — without the context manager, FastAPI doesn't
trigger the lifespan and the coverage stays at 73%.

## Parallel perspectives 1-16

### #1 Implementation Engineer

- **APPLIED**: `cancelar_ordem` endpoint discarded the DTO returned by
  `CancelarOrdem.executar` and annotated `-> None`. PR #62 Copilot caught the
  exact same pattern on the use case; now the router was doing it. Fixed:
  return `OrdemDeServicoResponse` via `_to_ordem_response(result)`.
- **REJECTED**: P1's concern about `/api/v1/acompanhamento` not normalizing
  placa/documento. Verified: normalization was already applied at the repository
  level in PR #62 fix (`_NAO_DIGITO.sub` + `upper().replace("-", "")`). The
  lazy import chain in `router_publico.py` passes through to the normalized
  repository correctly.
- Endpoint count verified: exactly 15. Status codes (201 on create, 200 on
  transitions, 200 on delete-with-body, 200 on reads) all correct.

### #2 Staff Engineer

- **APPLIED**: `**result.__dict__` splat across 11+ handlers extracted to
  `_to_ordem_response()` helper using `model_validate(dto)`. Every response
  schema now has `ConfigDict(from_attributes=True)`.
- **APPLIED**: `remover_item` also had `-> None` + discarded DTO. Fixed to
  return `OrdemDeServicoResponse` with status 200 (not 204) for consistency
  with every other mutating endpoint. This is a convention over REST strictness.
- **APPLIED**: `CancelarOrdemRequest.motivo` now has `max_length=500`
  (was unbounded — DoS + persistence footgun).
- **APPLIED**: `_ESTADOS_TERMINAIS`/`_ESTADOS_FINALIZADOS` in repository.py
  already use `Final[frozenset[str]]` from PR #62 — no action.
- **APPLIED**: `dependencies.py` had 18 `# type: ignore[arg-type]` noise from
  `-> object` return types on `_repo`/`_uow`. Replaced with concrete return
  types (`-> OrdemDeServicoSQLAlchemyRepository`, `-> SQLAlchemyUnitOfWork`)
  hoisted to module-level imports. Zero `# type: ignore` now in the file.
- **APPLIED**: Tag changed from `"Ordens de Servico"` (title case) to
  `"ordens-de-servico"` (lowercase kebab) to match the sibling contexts'
  tag convention.
- **REJECTED**: P2 F1 "admin-only for CriarOrdem" — applied literal spec
  checklist, which says CriarOrdem is admin-only. Fixed. (See #5.)
- **REJECTED**: P2 F9 local imports inside factories — intentional (break
  load-time import cycle).

### #3 Staff Architect

PASS — no findings. Layer boundaries clean: router imports only from
`aplicacao/dtos`, `interfaces/dependencies`, `interfaces/schemas`, and
`compartilhado/interfaces`. `dependencies.py` is the composition root and the
only file importing from `infraestrutura/`. Lazy imports preserve the module
graph. No circular imports.

### #4 Test Engineer

- **APPLIED (partial)**: added integration tests for `/api/v1/acompanhamento`
  (hit, miss returning 404, missing params returning 422) in
  `test_router_publico.py`. This closes the zero-coverage gap P10 flagged.
- **APPLIED**: `test_dependencies_os.py` now asserts `isinstance(uc,
  ConcreteUseCaseClass)` on all 15 factories (was `assert uc is not None`,
  which any truthy object would pass).
- **APPLIED**: `test_remover_item_direto` and `test_cancelar_ordem_direto`
  updated to provide valid `_ORDEM_NS` return values and assert the result,
  now that those endpoints return `OrdemDeServicoResponse`.
- **REJECTED (partial)**: P4 suggested migrating 12/15 router tests from
  direct function calls to full TestClient. Not done — would be a test
  rewrite beyond the scope of this PR. The 3 existing TestClient tests
  (test_criar_ordem, test_listar_ordens_vazio, test_listar_ordens_com_itens)
  provide baseline HTTP semantics coverage. Deferred to step 14 integration
  tests.
- **REJECTED**: P4 suggestion to add 15 × (404 + 422) negative tests via
  TestClient. That's 30 new tests for a single PR. Deferred to step 14.
- **FLAG**: auth guards are effectively untestable until PR #12 replaces
  the `exigir_papel` stub. Documented in the PR description.

### #5 Security Engineer — CRITICAL fixes

**Auth guard mismatches (6 total, all APPLIED)** — spec's focus checklist
defines role sets per endpoint; the initial implementation had 6 mismatches:

| Endpoint | Before | After (spec-aligned) |
|---|---|---|
| `POST /` criar_ordem | admin + atendente | **admin** |
| `GET /` listar_ordens | admin + atendente | **admin + atendente + mecanico** |
| `GET /metricas` | admin + atendente | **admin** |
| `GET /{id}` obter_ordem | admin + atendente | **admin + atendente + mecanico** |
| `POST /aprovacao-complementar` | admin | **admin + mecanico** |
| `POST /rejeicao-complementar` | admin + mecanico | **admin** |

All other endpoints were already correct.

**Oracle attack on `/api/v1/acompanhamento`** — CRITICAL finding: previous
implementation returned different response shapes for hit (3 keys: status,
criado_em, atualizado_em) vs miss (1 key: `{"status": "nao_encontrado"}`).
An attacker brute-forcing placa+documento combinations could distinguish
existing orders from non-existing ones by response shape alone. Rate limit
(10/min) mitigates but does not eliminate the oracle with distributed or
IPv6-rotating attacks. **Fix applied**: return `HTTPException(404)` on miss
— consistent HTTP status + empty body body, eliminating the shape difference.
Also use `AcompanhamentoResponse` schema consistently for the hit case.

**Other security items**:
- PII: `AcompanhamentoResponse` exposes only status + timestamps. No
  cliente_id, veiculo_id, itens, or orcamento leak. PASS.
- SQL injection: zero raw SQL in interfaces layer. PASS.
- Bandit: zero high-severity findings. PASS.
- `motivo` max_length: see #2 APPLIED.

### #6 PM

PASS — 15 endpoints verified against spec. Requirements coverage traced to
RF-003/004/005/006 (via EstoquePort)/007/008/016/017.

- **APPLIED** (partial, reported by P6): `MetricasResponse` was dropping the
  `tempo_medio_execucao_minutos` field because `**result.__dict__` silently
  ignored unknown DTO fields. Fixed: added `tempo_medio_execucao_minutos:
  float | None` field to `MetricasResponse` schema. Now the /metricas
  endpoint correctly exposes RF-008's headline metric.

### #7 TPM

- **APPLIED (PASS)**: scope expansion note — `main.py` fixes a latent bug
  from PRs #58/#59/#60 (routers never registered). Acceptable because
  alternative (register only os_router) is strictly worse.
- PASS on every other check (no pyproject.toml changes, no orphan TODOs,
  no commented code, no `print()`).

### #8 Tech Doc Writer

- **APPLIED (comprehensive)**:
  - Module docstrings added to all 5 source files (router, schemas,
    dependencies, router_publico, updated main.py comment).
  - Class docstrings added to all 11 Pydantic schemas.
  - Method docstrings on all 15 router endpoints explaining source state
    → target state → emitted event where applicable.
  - OpenAPI `summary=` on every endpoint decorator.
  - OpenAPI `responses={...}` documented on the public tracking endpoint
    (404 + 429 descriptions).
  - `Field(description="...")` on monetary fields, pagination fields, status
    field, and all request fields.
  - Factory docstrings on all 15 dependency functions naming the use case
    and the adapters wired.

### #9 DDD Strategic

PASS. Ubiquitous language matches glossary in URL paths, schema names,
operation names, and tags. No cross-context entity leakage — only public
UUIDs cross the HTTP boundary.

### #10 Test Coverage Specialist

- **APPLIED**: `router_publico.py` at 60% (lines 33-45 uncovered — the entire
  `acompanhamento` handler). Fixed by adding 3 tests in
  `test_router_publico.py` (hit, miss 404, missing params 422). Now at 100%.
- **REJECTED**: `main.py` line 101 (`if __name__ == "__main__":` block)
  uncoverable without subprocess. Left as-is.
- Final: all scope files at 100% line coverage. 99.81% overall.

### #11 OOP Specialist

PASS. Dependency factories are pure functions, schemas are plain data, router
handlers are thin, no global state, constructor DI throughout.

### #12 DDD Tactical

PASS. Pydantic schemas separate from application DTOs, no domain entities in
router, use case inputs are DTOs, outputs mapped via `model_validate` (now
using `from_attributes=True`), no `Dinheiro` or `StatusOrdem` enum leaking
through HTTP, all aggregate IDs are `UUID`.

### #13 Maintenance Engineer

- **APPLIED**: `motivo` max_length (same as #2).
- **APPLIED**: rate-limit rationale comment on `router_publico.py:26` —
  explains why 10/min and what the limiter mitigates.
- **REJECTED**: P13 concern about `obter_obter_ordem` stutter — renaming
  the use case is out of scope.
- Rest: PASS.

### #14 AI Agent

- **APPLIED**: tag casing fix (same as #2).
- **APPLIED**: lifespan order comment in `main.py` explaining the cascade
  rationale (cliente+veiculo first, then contexts that reference them).
- **FLAG (no code change)**: PR #12 auth insertion point is clear
  (`# Auth router sera registrado em PR 12`); `exigir_papel` stub contract
  is stable.
- **REJECTED**: splat-DTO fragility concern — addressed by #2 `_to_ordem_response`
  helper + `from_attributes=True` pattern.

### #15 Git & GitHub Workflow

PASS — branch hygiene clean, no commits yet (mid-execution), scope aligned.

### #16 DevOps / SRE

- PASS: lifespan idempotent (every `iniciar_*` has `_mapeamento_iniciado`
  guard), lifespan ordering correct (cliente → catalogo → estoque → os),
  `@limiter.limit("10/minute")` correctly applied, security headers middleware
  preserved, no new env var reads at module level.
- **NOTED (not blocking)**: rate limit is per-replica under multi-replica
  deploys. For stricter global enforcement, migrate to Redis/memcached
  backend. Flag for Infra board as follow-up.
- **NOTED**: `calcular_tempo_medio_execucao` (Postgres `extract('epoch', ...)`)
  still Postgres-specific — Step 14 will add Postgres integration tests.

## Sequential perspectives 17 → 18 → 17

### #17 AI-Trace Removal (first pass)
- **APPLIED**: `router.py:195` (`remover_item` docstring) used "Mantemos"
  first-person plural. Rewrote as "Retorna 200 + body por consistencia
  com os outros endpoints de mutacao (convencao do PR #62: toda mutacao
  devolve OrdemDeServicoResponse)."

### #18 Human Reader
PASS — lead-with-intent throughout, short sentences, lifecycle ordering
correct, test names narrative.

### #17 AI-Trace Removal (final pass)
PASS — the "Mantemos" fix carried forward.

## Final state

- **800 unit tests**, 99.81% coverage
- All `src/ordem_servico/interfaces/*` files at 100% line coverage
- `src/compartilhado/interfaces/router_publico.py` at 100%
- `src/main.py` at 100%
- `make check` green (ruff + ruff format + mypy strict + bandit + pytest)

## Notes for PR 12 (auth)

- `main.py:76` has the comment marking where to add the auth router
  registration (right after `os_router`).
- `exigir_papel` contract is stable: `Depends(exigir_papel("admin", ...))`
  returns `dict[str, object]`. PR 12 replaces the stub body with JWT
  validation without touching any of the 15 OS call sites.
- Auth router will need its own `iniciar_mapeamentos` call in the lifespan
  — add it AFTER `iniciar_os()` (autenticacao has no FK to OS tables).
- **Reminder**: after PR 12 lands, re-run the Perspective #5 auth guard
  matrix against this PR's 15 endpoints to verify the guards actually
  enforce the role sets (today they're effectively no-ops because the
  `exigir_papel` stub always returns admin).

## Copilot Gap Analysis

Copilot posted **4 findings** on PR #63. All were legitimate and led to
focused fixes in commits `f4269f0`, `e350283`, and `fb01d73`.

### Finding 1 — `src/compartilhado/interfaces/router_publico.py:36` (CRITICAL) — Limiter instance mismatch silently disables rate limit

**Copilot comment**: `router_publico.py` creates its own `Limiter()`
instance for the `@limiter.limit("10/minute")` decorator, but
`configurar_rate_limiting()` in `middleware.py` creates a DIFFERENT
`Limiter()` instance and sets it as `app.state.limiter`. SlowAPI's
`SlowAPIMiddleware` reads from `app.state.limiter`, so the decorator
and the middleware were looking at different counter stores. The
10/minute rate limit on the public acompanhamento endpoint was
silently never enforced.

**Missed by**:
- **#16 DevOps/SRE** — checklist item 5 (`@limiter.limit("10/minute")`
  applied correctly) only checked that the decorator was present, not
  that the `Limiter` instance was the same one registered on the app.
  The reviewer also noted the "per-replica semantics" of SlowAPI but
  missed the more fundamental "wrong instance" issue. SlowAPI's API
  design (decorator-on-module-level-limiter vs middleware-reads-app-state)
  is subtle enough that a literal-looking decorator check isn't
  sufficient.
- **#5 Security** — confirmed the decorator was there for the oracle
  fix context but did not trace the enforcement path end-to-end from
  decorator through middleware. The PR's rate-limiting mitigation
  claim (10/min to deter brute force) was taken at face value.

**Fix applied** (`f4269f0` + `e350283`): move `limiter` to a
module-level singleton in `middleware.py`. `configurar_rate_limiting()`
now only calls `app.state.limiter = limiter` (the same instance). The
router imports `limiter` from `middleware` instead of creating its own.

### Finding 2 — `src/compartilhado/interfaces/router_publico.py:79` — Handler bypasses factory pattern

**Copilot comment**: The `acompanhamento` handler instantiates
`OrdemDeServicoSQLAlchemyRepository` and `ConsultarAcompanhamento`
directly inside its body, bypassing the `obter_*` factory pattern used
by every other OS endpoint. This couples the public router to
infrastructure imports that should live in
`ordem_servico/interfaces/dependencies.py`.

**Missed by**:
- **#3 Staff Architect** — checklist item 3 (adapters isolate
  entities) verified that infrastructure imports were lazy, but the
  reviewer accepted the pattern where `router_publico.py` directly
  instantiated the repository because of the "layering direction
  constraint" (compartilhado can't module-level import from
  ordem_servico). The missed insight is that a factory in
  `ordem_servico/interfaces/dependencies.py` can be imported LAZILY
  from `router_publico.py` — same layering direction, but now the
  composition root owns the wiring.
- **#14 AI Agent** — checklist item 3 (factory contract stable)
  verified the existing 15 factories but did not observe that a 16th
  factory would align the public endpoint with the pattern.

**Fix applied** (`e350283`): added `obter_consultar_acompanhamento(session)`
factory to `src/ordem_servico/interfaces/dependencies.py`. The
`router_publico.py` handler lazy-imports it and calls
`uc = obter_consultar_acompanhamento(session); uc.executar(...)`.
Composition root consolidation: all OS wiring is now in one place.

### Finding 3 — `src/compartilhado/interfaces/router_publico.py:59` — Missing input validation on public endpoint

**Copilot comment**: `placa` and `documento` were accepted as bare
`str` with no length or format validation. On a public unauthenticated
endpoint, this allows arbitrarily large payloads — a DoS vector
(expensive normalization + queries) even though the repository
normalizes correctly. The HTTP contract was also ambiguous (no
constraint in the OpenAPI spec).

**Missed by**:
- **#5 Security** — checklist item 11 ("tracking endpoint lookup:
  placa+documento are public inputs") flagged the potential for
  enumeration attacks but did not propose input-validation bounds.
  The reviewer focused on the oracle shape (hit vs miss) and rate
  limiting but skipped the payload-size mitigation.
- **#1 Implementation Engineer** — checklist item 2 ("correct HTTP
  status codes") did not include input validation bounds. Pydantic
  validation at the path-param level is typically handled by the
  Pydantic schema, but for Query params it needs an explicit
  `Query(..., min_length=..., max_length=...)`.

**Fix applied** (`e350283`): add `Query(min_length=7, max_length=8)`
to `placa` and `Query(min_length=11, max_length=18)` to `documento`.
Matches the actual format range (placa Mercosul/antiga 7 chars, with
hyphen 8; CPF 11 digits, CNPJ 14 digits, both up to 18 with mask).
Invalid lengths return 422 at the FastAPI validation layer, before
the request reaches the handler body.

### Finding 4 — `src/ordem_servico/interfaces/dependencies.py:29` — Docstring claims local imports but file has module-level imports

**Copilot comment**: The module docstring (authored during the review
when the original step 11 implementation had all imports local) says
"Local imports inside each factory body (rather than module-level) are
intentional — they break a load-time import cycle". But after the
Perspective #2 fix (hoisted infrastructure imports to module level to
remove `# type: ignore[arg-type]` noise), the file now has
module-level imports of infrastructure AND local imports of use cases.
The docstring no longer accurately describes the implementation.

**Missed by**:
- **#8 Tech Doc Writer** — second pass after the #2 fix was not
  performed against the updated docstring. The reviewer added the
  docstring in the first fix round and then the subsequent fix of
  the `# type: ignore` issue made the docstring stale.
- **#17 AI-Trace Removal & Polish** — checklist did not specifically
  look for docstring/implementation mismatches after refactors within
  the same PR.

**Fix applied** (`fb01d73`): update the docstring to clearly
distinguish the two import styles: "Infrastructure classes are
imported at module level — this is the composition root and is
allowed to know about infra. Use-case imports stay LOCAL inside each
factory body because they would create a load-time import cycle."

## Perspective checklist reinforcements

The 4 findings cluster into **three missed patterns**. One pattern
(#1 — SlowAPI rate-limiting instance sharing) is too library-specific
for a generic checklist reinforcement. The other two are worth tracking:

1. **Docstring/implementation consistency after refactors within the
   same PR** (Finding 4) — when a fix in one perspective changes code,
   the next perspective should verify any docstring or comment in the
   touched area still accurately describes the behavior.

2. **Input validation bounds on public endpoints** (Finding 3) — any
   public (unauthenticated) endpoint with free-text inputs must have
   `min_length` / `max_length` bounds at the FastAPI validation layer,
   not just the business layer.

Neither pattern crosses the 3+ findings threshold for an immediate
`postech-ai-helper/ai/perspectives/NN-*.md` reinforcement commit. If
future PRs surface similar gaps, revisit.
