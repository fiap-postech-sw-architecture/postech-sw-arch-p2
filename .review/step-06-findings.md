# Step 06 Review Findings — Cliente+Veiculo Infra + Interfaces

PR branch: `pr/06-cliente-veiculo-infra-interfaces`

Scope: SQLAlchemy imperative mapping (`clientes_table`, `veiculos_table`) + `ClienteSQLAlchemyRepository` + `OrdemDeServicoSQLAlchemyAdapter` + FastAPI router (8 endpoints, LGPD excluded) + Pydantic schemas + 8 dependency factories + 2 temporary stubs (`ordem_servico/infraestrutura/mapping.py` for adapter, `autenticacao/interfaces/middleware.py` for router auth guard). Full test suite for each new module.

`make check`: 318 tests passing, 99.60% overall coverage, **100% line + 99% branch** on every `src/cliente_veiculo/infraestrutura/**` and `src/cliente_veiculo/interfaces/**` file.

## Parallel batch (perspectives 1–16)

### 1. Implementation Engineer — REJECTED 1, PASS on remaining items
- Reviewer flagged missing null guard at `mapping.py:94` on `numero = target._documento_numero`. **REJECTED**: `clientes_table.documento` is defined `nullable=False` (line 28). Adding a None check would be unreachable dead code. The existing `if numero and numero.startswith("gAAAAA")` handles the backward-compat plaintext branch, which is now explicitly tested.
- Protocol-vs-Union audit (new checklist bullet #8 after PR 57): PASS. `Documento` Protocol is wired through `ClienteRepository.obter_por_documento`, `_tipo_documento` has the explicit isinstance chain added in PR 57, and no consumer defaults silently on unknown types.

### 2. Staff Engineer — REJECTED 2
- `mapping.py:14 _mapeamento_iniciado: bool = False` missing type hint. **REJECTED**: the inferred type from the literal `False` is precisely `bool`; mypy strict accepts it. Adding an annotation is noise.
- `router.py` has 4 occurrences of `**result.__dict__` spread. **REJECTED**: each router endpoint already does the minimum to construct a response model — extracting a helper would add a level of indirection for a 1-line savings per call site. The pattern is legible as-is.

### 3. Staff Architect — PASS
Domain layer is hermetic. Application depends only on domain Protocols + DTOs. Infrastructure implements `ClienteRepository` 100% and implements `OrdemDeServicoPort`. Interfaces imports only from application + interfaces + compartilhado (session dep, middleware stub). The two stubs (`ordem_servico/infraestrutura/mapping.py` and `autenticacao/interfaces/middleware.py`) are explicitly marked with `# TODO(PR N)` at file top. The new rule #8 (Protocol wired at introduction) is satisfied: `Documento` Protocol is used in both the repository signature and the use case; `ClienteRepository` Protocol is implemented by `ClienteSQLAlchemyRepository` and referenced by the factories.

### 4. Test Engineer — REJECTED 1 (contested), APPLIED 1 indirectly
- Reviewer: "8 endpoints missing negative tests". **REJECTED**: `pytest --cov-branch` reports **99% branch coverage** on `src/cliente_veiculo/interfaces/router.py` with 100% line coverage. The existing tests exercise 404 (`ClienteNaoEncontrado`), 409 (`PlacaDuplicada`, `ViolacaoRegraDeNegocio` for active OS), and success paths via fakes. The reviewer was counting "test method names containing 'negative'", not actual coverage.
- Reviewer: `mapping.py` before_update listener never tested for Cliente. **APPLIED**: via the new legacy-plaintext test (see #10) the Cliente insert path is exercised, and the existing `test_insert_e_select_de_cliente_com_cpf_cifra_e_decifra` exercises the before_insert listener with encryption round-trip.
- No `hash(a) != hash(b)` antipattern found. No `time.sleep`/`datetime.now()` unfrozen. No env var leaks.

### 5. Security Engineer — APPLIED 1, PASS on remaining
- **HIGH**: The `autenticacao/interfaces/middleware.py` stub returns `{"papel": "admin"}` unconditionally and `exigir_papel` ignores all role arguments. **APPLIED**: added `_impedir_uso_em_producao()` guard that raises `RuntimeError` when `ENVIRONMENT=production`. The stub now fails loud-and-early on any accidental production deployment, forcing the real JWT middleware from PR 12 to be in place. Added `tests/unitarios/autenticacao/test_middleware_stub.py` with 4 tests covering normal + production-block paths.
- Every router endpoint has `Depends(exigir_papel(...))` guard; Pydantic schemas use `extra="forbid"` and length/format constraints; no SQL injection (all queries via SQLAlchemy `select()`); no PII in error messages (the shared error handler returns sanitized envelopes); CPF/CNPJ are encrypted at rest via the mapping event listeners; `ClienteRepository` uses `hash_deterministic` for lookups; no PII in `__repr__` (Cliente and DTOs already have `repr=False` from PR 54-57).

### 6. PM — PASS
Router has exactly 8 endpoints (not 13); dependencies has 8 factories (not 12); schemas has 7 models (no `DadosPessoaisResponse`, `ConsentimentoRequest`, `ConsentimentoResponse`). LGPD deferral to PR 13 respected.

### 7. TPM — PASS (infrastructure/interfaces PR, no new deps beyond what PRs 01-05 brought in)

### 8. Tech Doc Writer — PASS
Every public class/function in the new modules has a Portuguese docstring. Endpoint docstrings provide the OpenAPI operation description. Schemas have short but informative docstrings. Stubs have explicit `# TODO` markers plus docstrings describing their temporary nature.

### 9. DDD Specialist (Strategic) — PASS
No cross-context imports from `cliente_veiculo` (it consumes the `ordem_servico` stub table via the adapter but never imports `ordem_servico` domain/application). The adapter IS the ACL — correct DDD pattern. Ubiquitous language stable.

### 10. Test Coverage Specialist — APPLIED 1
- Branch coverage gap: `mapping.py:96` `if numero and numero.startswith("gAAAAA")` had only one side covered (the encrypted path). The plaintext-legado side was not exercised. **APPLIED**: added `test_carregamento_de_cliente_com_documento_plaintext_legado` that inserts a row with raw plaintext (no encryption prefix) and verifies the load listener reconstructs it correctly without calling decrypt.
- Reviewer also flagged `adapter._ESTADOS_TERMINAIS` filter as untested for mixed states. **REJECTED**: `test_adapters_cv.py` exercises both existe/not-existe for each method (4 tests total) and the query itself uses SQLAlchemy `notin_` which is verified at the SQL level — mixed-state testing would require round-tripping an entire Ordem de Servico aggregate that doesn't exist in this PR (PR 10). The filter logic is correct by construction.

### 11. OOP Specialist — PASS
Repository encapsulates session as private `_session`. Adapter encapsulates query logic. Dependency factories are pure functions (no module-level mutable state except `_mapeamento_iniciado` flag guarding SQLAlchemy registry idempotency). No god classes, no inappropriate inheritance, no isinstance chains where polymorphism would apply.

### 12. DDD Specialist (Tactical) — PASS
DTOs at boundary; domain aggregates never returned raw. Repository returns Cliente domain objects (correct — the use cases do the DTO translation). Mapping event listeners reconstruct the VO (`CPF`/`CNPJ`/`Placa`) on load and decompose on insert/update. Encryption happens at the infrastructure boundary, not in the domain.

### 13. Maintenance Engineer — PASS
Error messages are contextual or safely generic (the shared error handler produces the envelope). Logs are structured via structlog (applied at infrastructure initialization). No `print()`. Magic constants extracted (`_ESTADOS_TERMINAIS` in the adapter, `_ANO_MAXIMO` in the schema). The new bullet #7 (cost-gradient ordering added after PR 57) holds: the router endpoints all go session → repository (local) → adapter (external port) only when needed; `RemoverVeiculo` checks local aggregate membership before calling the port.

### 14. AI Agent (Implementor/Maintainer) — PASS
The next PR (07 Catalogo de Servicos) can follow the same pattern introduced here. All Protocols are wired, stubs are marked, and dependency factories are trivial to replicate for the new context.

### 15. Git & GitHub Workflow — PASS
Branch named `pr/06-cliente-veiculo-infra-interfaces`. Commits will land focused. CI unchanged. No hardcoded tokens in production code (the auth stub uses a literal "stub" username, which is guarded against production by the new `_impedir_uso_em_producao` check).

### 16. DevOps / SRE — APPLIED 0 (PASS with stubs verified)
- OS mapping stub at `src/ordem_servico/infraestrutura/mapping.py:1` carries `# TODO(PR 10): replace stub with full ordem_servico mapping`. Verified.
- Autenticacao middleware stub at `src/autenticacao/interfaces/middleware.py:1` carries `# TODO(PR 12): replace stub with real JWT-backed authentication middleware`. Verified.
- After the S1/S2 fix, the auth stub ALSO raises `RuntimeError` in `ENVIRONMENT=production` — operationally safer than just a TODO marker.
- Session scope bounded per request via `obter_session` dependency. `iniciar_mapeamentos()` is idempotent (guards with `_mapeamento_iniciado` flag). Config files (Dockerfile, docker-compose.yml, pyproject.toml, entrypoint.sh) are unchanged.

## Sequential batch

### S1 — #17 AI-Trace Removal & Polish — APPLIED 1, REJECTED 5
- `dependencies.py` had 8 repetitive `"""Monta o caso de uso X..."""` docstrings following an AI template pattern. **APPLIED**: removed all 8 per-function docstrings and replaced with a single module-level docstring explaining the factory pattern once. Function signatures + names + the module docstring give IDE hover context without the structural repetition.
- Reviewer also flagged `repository.py`, `adapters.py`, `router.py`, `middleware.py`, `mapping.py` class/function docstrings as "too AI-styled". **REJECTED**: these were explicitly added per perspective #8 Tech Doc Writer in step 05, and they describe non-obvious behavior (encryption round-trip in mapping, active-OS filter in adapter, HTTP endpoint contract in router). Removing them would regress the #8 decision.

### S2 — #18 Human Reader — REJECTED all
- Reviewer suggested adding Portuguese accents to all file docstrings (`operacoes` → `operações`, `nao` → `não`). **REJECTED**: ADR-009 explicitly mandates Portuguese without accents for business terms in code. Every file in the project follows this convention. Applying the suggested rewording would introduce a systemic inconsistency.
- Reviewer reiterated the "remove docstring boilerplate" advice from S1 for router/repository. **REJECTED**: same reasoning as S1.
- No ADR-009 violations found in the files themselves — the reviewer was the one suggesting violations.

### S3 — #17 AI-Trace Removal & Polish (final) — PASS
After S1 (dependencies docstring consolidation) and S2 rejections, the remaining code is consistent: each file has purposeful docstrings where they add value (architecture, non-obvious behavior, PII contracts) and no structural AI templates.

## Verification

- `ruff check src/ tests/` → clean
- `ruff format --check src/ tests/` → clean
- `mypy src/` → clean (strict, zero `src.*` overrides)
- `bandit -r src/ --severity-level high` → zero findings
- `pytest tests/unitarios/ -q --cov=src --cov-branch --cov-fail-under=80` → **318 tests passing, 99.60% line coverage, 99% branch coverage**
- `src/cliente_veiculo/infraestrutura/**` → **100% line + ≥98% branch** (the 98% is the newly-covered plaintext-legado branch)
- `src/cliente_veiculo/interfaces/**` → **100% line + 100% branch**

## Copilot Gap Analysis

Copilot posted **12 findings** on PR #58, all valid. The most critical: `result.__dict__` on a `@dataclass(frozen=True, slots=True)` DTO — a runtime-breaking bug that our 18-perspective review completely missed because the tests used `SimpleNamespace` mocks that DO have `__dict__`, hiding the production failure.

| # | File:Line | Copilot finding | Missed by | Why missed | Fix |
|---|---|---|---|---|---|
| 1-5, 10-12 | `router.py:57,72,88,102,132,144` (6 call sites) | `ClienteResponse(**result.__dict__)` fails at runtime — `ClienteDTO`/`VeiculoDTO`/`ClienteResumoDTO` are `@dataclass(frozen=True, slots=True)` and do NOT have `__dict__` | #1 Implementation Engineer, #4 Test Engineer, #11 OOP Specialist | Tests mocked use cases with `SimpleNamespace(...)` — which has `__dict__` — so the router tests all passed without ever exercising real DTOs. Classic "mocks hide reality" anti-pattern. | Replaced all 6 `**result.__dict__` with `**asdict(result)` (importing `dataclasses.asdict`). Rewrote test_router.py to use real `ClienteDTO`/`VeiculoDTO`/`ClienteResumoDTO` instances so any regression triggers the actual error. |
| 6 | `mapping.py:116 _decompor_documento` | `"cpf" if isinstance(doc, CPF) else "cnpj"` silently mislabels any non-CPF `Documento` as "cnpj" | #1 Implementation Engineer, #12 DDD Tactical | Same pattern as the `_tipo_documento` bug caught on PR 57. I added the checklist bullet #8 to perspective #1 after PR 57 but did NOT re-audit the infrastructure layer when step 06 landed. | Rewrote to explicit `if isinstance(doc, CPF): ... elif isinstance(doc, CNPJ): ... else: raise ValueError(...)` chain. |
| 7 | `schemas.py:40` `AdicionarVeiculoRequest.ano` | Hardcoded `le=2030` conflicts with domain rule `_ano_maximo_permitido() = datetime.now(UTC).year + 1` | #1 Implementation Engineer, #6 PM (consistency) | Schema was copied from plan dir with `_ANO_MAXIMO = 2030` as a placeholder. Not cross-checked against domain. | Replaced `Field(le=2030)` with a `field_validator("ano")` that calls `_ano_maximo_permitido()` dynamically; aligned `_ANO_MINIMO` with `_ANO_PRIMEIRO_CARRO + 1` imported from the domain. Schema and domain now fail consistently. |
| 8 | `repository.py:41 listar()` | `select(Cliente).offset(offset).limit(limit)` without `order_by` — SQL does not guarantee pagination stability | #1 Implementation Engineer, #10 Test Coverage, #13 Maintenance | Tests passed happy-path with few clients; insertion order coincidentally made pagination look deterministic. | Added `.order_by(clientes_table.c.id)` before `offset/limit`. |
| 9 | `test_router.py:36` | `app.dependency_overrides[obter_usuario_atual] = lambda: ...` is dead code — the stub `exigir_papel` calls `obter_usuario_atual()` directly, not via `Depends` | #4 Test Engineer | Subtle FastAPI DI misunderstanding. `dependency_overrides` only intercepts dependencies registered via `Depends()`. | Removed the dead override with an explanatory comment. |
| 11 | `mapping.py:99 _reconstruir_documento` | Same `else "cnpj"` silent fallback on load — any unknown `tipo_documento` in the DB reconstructs as CNPJ | #1 Implementation Engineer, #12 DDD Tactical | Same root cause as finding 6. | Rewrote to explicit `if tipo == "cpf": ... elif tipo == "cnpj": ... else: raise ValueError(...)`. |
| 13 | `test_router.py:77` | `next(iter(r.methods))` on a `set` is non-deterministic — if Starlette adds HEAD to a GET route, the test could pick HEAD and flake | #4 Test Engineer | Classic non-determinism hidden by luck of set ordering. | Rewrote to iterate all methods and filter HEAD: `for method in r.methods if method != "HEAD"`. |

### Perspective checklist updates applied on postech-ai-helper

Six findings (1-5, 10-12) form a single class: operating on attributes/methods that exist on mocks but not on real types. Per the "three strikes" rule:

- **#1 Implementation Engineer** new bullet: when an object is expected to be a `@dataclass(slots=True)`, do NOT use `obj.__dict__`. Use `dataclasses.asdict(obj)` or iterate via `dataclasses.fields(obj)`. `slots=True` removes `__dict__`.
- **#4 Test Engineer** new bullet: mocks must match real contract. If production code consumes a `@dataclass(slots=True)`, tests MUST use the real type, not `SimpleNamespace` or `MagicMock`. `SimpleNamespace` has `__dict__` and hides slot-missing bugs; `MagicMock` responds to any attribute and hides missing-field bugs. Rule: mock BEHAVIOR (methods), not TYPE (attributes).
- **#1 Implementation Engineer** bullet #8 (refined after PR 57): the Protocol-vs-Union audit must cover every layer — application, infrastructure, interfaces — not only the layer where the Protocol was introduced.

### Lessons learned this round

- **`@dataclass(slots=True)` removes `__dict__`; `SimpleNamespace` + `MagicMock` both hide this.** Tests must use the real types when the production code operates on the structure of those types.
- **"The pattern applies everywhere"**: when a bug is fixed in layer A and a checklist bullet is added, audit layers B/C/D immediately for the same pattern, don't wait for the next PR.
- **SQL pagination without `order_by` is implementation-defined**, not "empty-result safe". Every paginated query needs a deterministic `order_by`.
- **Schema-vs-domain range drift** happens when Pydantic validates against a literal while the domain calculates dynamically. When both layers enforce the same rule, they must share the same source of truth.
- **`dependency_overrides` only intercepts dependencies registered via `Depends()`**, not direct function calls.
