# Step 03 Review Findings — Compartilhado Dinheiro + Interfaces

PR branch: `pr/03-compartilhado-interfaces`
Scope: Dinheiro VO, EncryptionService, PII-scrubbing structlog, security/CORS/rate-limit middleware, error handler, session dependency, stub public router, wired `src/main.py`, 9 test files.

`make check` result: 140 tests passing, 98.81% overall coverage (100% on every `src/compartilhado/` file; 86% on `src/main.py` — the 4 missing lines are the `if __name__ == "__main__"` uvicorn bootstrap).

## Parallel batch (perspectives 1–16)

### 1. Implementation Engineer — PASS
Verified Protocol contravariance (TracebackType | None), `__enter__` concrete return, no silent exception swallowing, input validation in Dinheiro, resource cleanup in `obter_session`, justified `# type: ignore` on slowapi handler and dynamic factory call.

### 2. Staff Engineer — APPLIED 1
- `logging.py:34` — `_logger: Any` missing inline justification. **APPLIED**: added `# structlog passes the bound logger here; we do not inspect it`.

### 3. Staff Architect — PASS
Domain layer clean (dinheiro.py imports only from value_object); application layer absent except the UoW Protocol from step 02; infrastructure implements without touching interfaces; `main.py` as composition root. No circular imports.

### 4. Test Engineer — APPLIED 2
- `test_error_handler.py:30-41` — parametrize cases without named IDs. **APPLIED**: converted to `pytest.param(..., id="...")` and extracted `_CASOS_EXCECAO` to keep lines under 88 chars.
- `test_dependencies.py:33` — `assert_called_once()` without argument verification. **APPLIED**: tightened to `mock_factory.assert_called_once_with()` and `mock_session.close.assert_called_once_with()`.

### 5. Security Engineer — APPLIED 1, REJECTED 1, DEFERRED 1
- **CRITICAL** `encryption.py:22-24` — ENCRYPTION_KEY auto-generated when missing, breaks multi-replica. **APPLIED**: added `logging.warning` when key is auto-generated, expanded docstring documenting the dev-only contract. Hard fail-fast deferred to hardening step (step 12/13) because current dev/test flow relies on auto-generation.
- **HIGH** `middleware.py:39` — CORS accept-all risk if misconfigured with `*`. **REJECTED**: current `configurar_cors` does not support `*`; empty list is safe; documented in the new docstring.
- **MEDIUM** Rate limiter default applied globally, no per-endpoint `@limiter.limit`. **DEFERRED**: the default 60/min applies to every route automatically via SlowAPIMiddleware. Per-endpoint tuning (5/min login, 10/min public) is in step 12 (autenticacao) and step 11 (public tracking).

### 6. PM — PASS
Every file traces to RF/RNF: encryption (RF-011), logging scrub (RNF-008), security headers (RNF-004), CORS (RNF-005), rate limit (RNF-003), health endpoint (RF-saude). No scope creep; `/acompanhamento` stubbed and explicitly deferred to PR #11.

### 7. TPM — PASS
No new dependencies added this step (structlog, slowapi, cryptography already in step 01). No orphan TODOs. No breaking changes. No unmerged upstream dependencies.

### 8. Tech Doc Writer — APPLIED (all 11 items)
Every public class/function flagged as missing a docstring received one, in Portuguese per ADR-009: `Dinheiro`, `EncryptionService` (plus `instance`, `encrypt`, `decrypt`), `scrub_pii`, `configurar_logging`, `registrar_error_handlers`, `SecurityHeadersMiddleware`, `configurar_cors`, `configurar_rate_limiting`, `configurar_session_factory`, `obter_session`, `saude`, `lifespan`, `criar_app`.

### 9. DDD Specialist (Strategic) — REJECTED 2
- **Shared kernel contamination** — `compartilhado/dominio/exceptions.py` includes context-specific exceptions (EstoqueInsuficiente, TransicaoStatusInvalida, FalhaAutenticacao, FalhaAutorizacao). **REJECTED**: these are part of the `DomainException` hierarchy the central error handler maps to HTTP status codes. Central HTTP error mapping is a deliberate architectural choice for a single-deployment monolith; splitting per context would force either a duplicated mapping or event-based translation that adds more complexity than it saves at this scale. Decision recorded here; revisit if we ever split contexts into separate services.
- **Direct imports instead of event-based integration** — `error_handler.py` imports concrete exceptions. **REJECTED**: same reasoning. An Anti-Corruption Layer applies when two bounded contexts integrate; mapping domain exceptions to HTTP is not cross-context integration.

### 10. Test Coverage Specialist — APPLIED 1
- `error_handler.py:37` — `_obter_request_id` fallback `"desconhecido"` lacked a dedicated negative test. **APPLIED**: added `test_request_id_fallback_quando_ausente` that exercises the path without SecurityHeadersMiddleware setting the request_id.
- `src/main.py:53-56` — `if __name__ == "__main__"` uncovered. **ACCEPTED AS-IS**: uvicorn bootstrap cannot run in-process without binding the port; this is the standard pragma.

### 11. OOP Specialist — REJECTED 2
- `EncryptionService` singleton with class-level mutable state. **REJECTED**: the pattern is intentional — `instance()` is the factory, `__init__` runs once at first call, and the mutable attributes are initialized there. A class-based singleton with properties would add ceremony without changing behavior.
- `dependencies._session_factory` module-level global with `global` keyword. **REJECTED**: FastAPI convention for application-scoped state. The factory is set once at startup and reused; the global is idiomatic. Refactoring to a class container introduces an extra layer without benefit.

### 12. DDD Specialist (Tactical) — PASS
Dinheiro fully complies: frozen dataclass, value equality, `Decimal` arithmetic with `ROUND_HALF_UP`, validation in `__post_init__`, operations return new instances, currency invariant enforced in `_validar_mesma_moeda`, no I/O. Tests cover all paths.

### 13. Maintenance Engineer — APPLIED 1
- `encryption.py:40-41` — broad `except Exception` silently returned ciphertext, no observability. **APPLIED**: narrowed to `InvalidToken` (specific) and added `logger.warning` explaining the fallback. Also adds observability for misuse patterns.

### 14. AI Agent (Implementor/Maintainer) — PASS
Interfaces are unambiguous, error handling explicit, extension points clear. Another agent can add exceptions to `_EXCEPTION_STATUS_MAP` or add middleware functions without clarifying questions.

### 15. Git & GitHub Workflow Expert — PASS
Branch naming `pr/03-compartilhado-interfaces` matches convention. Linear history from main. CI triggers unchanged. No hardcoded tokens introduced.

### 16. DevOps / SRE Engineer — APPLIED 3, REJECTED 4, DEFERRED 3
- **CRITICAL #1** Encryption key regeneration breaks multi-replica. **APPLIED**: added `logging.warning` when falling back to ephemeral key plus docstring warning. Hard fail-fast moved to step 12/13 hardening because current step flow uses auto-generation in tests.
- **CRITICAL #2** In-memory rate limiter not replicated. **APPLIED**: added docstring on `configurar_rate_limiting` documenting single-replica contract and pointing to Redis backend as the production fix. Redis adoption is in step 13/14.
- **CRITICAL #3** Middleware order risk. **REJECTED**: the current order (SecurityHeaders added first, CORS/rate limiting/error handlers after) matches FastAPI's "last-added runs first" semantics so SecurityHeaders runs last on response, which is correct — it should always stamp headers regardless of rate-limit rejection.
- **CRITICAL #4** Health checks missing (docker-compose.yml, entrypoint.sh). **OUT OF SCOPE**: step 01 artifacts, not touched here. Tracked for step 14.
- **HIGH #5** Secrets hardcoded in docker-compose.yml. **OUT OF SCOPE**: step 01 artifacts. Tracked for step 13/14.
- **HIGH #6** No graceful SIGTERM handling in entrypoint.sh. **OUT OF SCOPE**: step 01 artifact.
- **HIGH #7** Logging initialized in lifespan, not before `criar_app()`. **REJECTED**: `criar_app()` has no I/O — only wiring. Lifespan is the correct hook because it runs before the first request, after the app is composed. Moving to module-level would break test isolation (multiple `criar_app()` calls).
- **MEDIUM #8** No resource limits in docker-compose.yml. **OUT OF SCOPE**: step 01 artifact.
- **MEDIUM #9** Rate limit hardcoded to "60/minute". **APPLIED**: now reads `RATE_LIMIT` env var with the same default.
- **LOW #10** CORS empty origins not logged. **REJECTED**: intentionally silent — an empty `CORS_ORIGINS` is a valid deployment config (admin-only deployment with no browser frontend). Logging every empty config would be noise.

## Sequential batch

### S1 — #17 AI-Trace Removal & Polish — PASS
No AI markers, hedging, AI tone, hallucinated references, boilerplate, or history leaks. Docstrings in Portuguese per ADR-009; naming idiomatic.

### S2 — #18 Human Reader — APPLIED 5
- `middleware.py:44` — "nao e suportado aqui intencionalmente" (defensive phrasing). **APPLIED**: reworded to "A especificacao CORS proibe o uso de wildcard `*` junto com credenciais; esta configuracao nao aceita esse caso."
- `error_handler.py:53-55` — parenthetical HTTP codes interrupt the sentence. **APPLIED**: split into two sentences — "Cada DomainException levantada no request vira um JSONResponse com o envelope..." + "Os codigos suportados sao 404, 401, 403 e 409."
- `dependencies.py:25` — "— sinaliza bug de startup" redundant with RuntimeError semantics. **APPLIED**: removed the dash clause.
- `logging.py` / `middleware.py` — inconsistent detail levels between docstrings. **APPLIED**: `middleware.py` SecurityHeadersMiddleware docstring now points to the dispatch method for the concrete header list instead of inlining it.
- `middleware.py:42-45` — three-clause sentence hard to parse. **APPLIED**: split into two sentences per the S2 rewording above.

### S3 — #17 AI-Trace Removal & Polish (final pass) — PASS
Re-scan after S2 rewrites. No new AI traces introduced by the rewordings. Docstrings read as single-voice, human-authored Portuguese.

## Verification after all fixes

- `ruff check src/ tests/` → clean
- `ruff format --check src/ tests/` → clean
- `mypy src/` → clean (strict mode, zero `src.*` overrides)
- `bandit -r src/` → zero high-severity findings
- `pytest tests/unitarios/` → 140 passing, 98.81% overall coverage
- `src/compartilhado/**` → 100% line coverage
- `src/main.py` → 86% (uvicorn bootstrap guarded by `__name__ == "__main__"`)

## Copilot Gap Analysis

Copilot posted its full review ~15 minutes after the initial push (so my T+75s check was premature). 5 findings, all valid. This section records each one, the perspective that should have caught it, and the fix.

| # | File:Line | Copilot finding | Missed by | Why missed | Fix |
|---|---|---|---|---|---|
| 1 | `src/main.py:48-50` | Middleware order: `SecurityHeadersMiddleware` added before CORS/rate limiting; CORS preflights and 429 rate-limit responses bypass the security headers | #16 DevOps/SRE | This was flagged in the initial parallel review and **I rejected it** citing "last-added runs first" semantics. The rejection was wrong: "last added runs first" is correct, but since I added SecurityHeaders FIRST, it ran LAST on request — meaning the rate limiter could reject a request with 429 before SecurityHeaders ever saw it, so the 429 response had no `X-Request-ID`/CSP/HSTS headers | Moved `add_middleware(SecurityHeadersMiddleware)` to AFTER `configurar_cors` and `configurar_rate_limiting` so it is the outermost wrapper. Added a comment explaining the ordering contract. |
| 2 | `src/compartilhado/interfaces/middleware.py:36` | `Content-Security-Policy: default-src 'none'` breaks Swagger UI and ReDoc in development because the inline scripts/styles cannot load | #5 Security Engineer, #16 DevOps/SRE | Both perspectives looked at CSP in isolation (is it restrictive? yes, pass) without cross-checking against the docs endpoints enabled on line 42-43 of `main.py`. The interaction between two reviewed items is a blind spot | Added `_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")` and a `request.url.path.startswith(...)` check in `dispatch` to skip CSP for those paths. Added test `test_csp_nao_aplicado_em_rotas_de_docs`. |
| 3 | `src/compartilhado/interfaces/middleware.py:54` | `configurar_cors` docstring claims `*` is rejected when credentials are enabled, but the code does not enforce it | #1 Implementation Engineer, #5 Security Engineer, #18 Human Reader | This is a docstring-vs-behavior drift. I added the docstring in the S2 rewording pass without also adding the runtime guard. No perspective checklist currently says "when docstring asserts X, code must also enforce X" | Added runtime validation in `configurar_cors`: raises `ValueError` if `*` appears in `CORS_ORIGINS`. Added test `test_cors_rejeita_wildcard_com_credenciais`. |
| 4 | `src/compartilhado/infraestrutura/logging.py:49` | `scrub_pii` only masks string values at the top level of `event_dict`; nested dicts/lists (common in structured log payloads) leak PII | #5 Security Engineer | The security perspective verified the three patterns (CPF/CNPJ/email) and top-level scrubbing but did not stress-test nested structures. Nested-payload PII leakage is a real LGPD exposure in a structured-logging codebase | Extracted `_mask_string` and `_scrub_value` helpers; added recursive traversal over `dict`, `list`, `tuple` with `_MAX_SCRUB_DEPTH=6` to prevent pathological/cyclic cases. Added 4 new tests covering nested dicts, lists, tuples, and depth limit. |
| 5 | `src/compartilhado/infraestrutura/encryption.py:63` | `decrypt()` logs a warning for every `InvalidToken` fallback, but that fallback is a supported contract (legacy/unmigrated plaintext) — generates log noise in normal flows | #13 Maintenance Engineer | I introduced the warning as part of finding #13 during this very review ("consider adding a log"). The Maintenance Engineer's checklist now says "error handling consistent" but not "log level must match severity of the expected case" | Downgraded `_logger.warning` to `_logger.debug` and expanded the docstring to document the contract. |

### Perspective checklist updates

Two findings (#1 and #4) map to perspective #5 (Security Engineer) and #16 (DevOps/SRE). Since both flag blind spots in the existing checklists, I am planning follow-up commits on `postech-ai-helper/ai/perspectives/` that add:

- **#5 Security Engineer** — new bullet: "When security headers or CORS are configured, verify their interaction with other enabled routes (e.g., Swagger/ReDoc CSP compatibility, middleware ordering against rate limiting)."
- **#16 DevOps/SRE** — new bullet: "Middleware ordering: verify the outermost/innermost contract against the specific middlewares used (CORS, rate limit, error handling) so headers land on preflights and rate-limit responses."

These will go in a separate commit on `postech-ai-helper`.

### Lessons learned this round

- **Rejecting a finding with reasoning can still be wrong.** The middleware ordering rejection was based on correct understanding of "last added runs first" but failed to reason through what happens when an earlier-in-execution middleware short-circuits. Review findings should be re-verified against the concrete behavior, not just the execution model.
- **Docstring edits must be followed by the code change they imply.** The S2 pass reworded a docstring to claim `*` is rejected; the rewording should have been a red flag that the code also needed updating.
- **Security checklists should stress interactions between items, not only items in isolation.**
