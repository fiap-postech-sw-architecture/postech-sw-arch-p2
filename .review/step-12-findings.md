# Step 12 — Autenticacao Complete: Perspective Review Findings

## Summary

PR adds complete Autenticacao bounded context: domain (Usuario, Papel,
TokenRevogado), application (Login, Registrar, Logout, RefreshToken),
infrastructure (JWTService, pwdlib/bcrypt, repos, mapping), and interfaces
(router, middleware, schemas, dependencies). Auth router + mapping
registered in main.py. Stub middleware removed, all router tests updated.

## Pre-review fixes (applied before perspectives ran)

1. **Limiter singleton bug** (CRITICAL): auth router.py created its own
   `Limiter(key_func=get_remote_address)` — same bug fixed in PR #63.
   Rate limits were silently unenforced (same root cause as PR #63).
   Fixed: imports the shared limiter singleton from `compartilhado.interfaces.middleware`.

2. **Mapping load listeners missing**: `_id_atribuido` and
   `_eventos_pendentes` not set on SQLAlchemy load for Usuario;
   `_id_atribuido` not set for TokenRevogado. Fixed: added load
   listeners matching pattern from other contexts.

3. **Stub test removal**: `test_middleware_stub.py` tested the stub
   `exigir_papel`/`obter_usuario_atual` from PRs 06-11. With the real
   middleware, the stub is gone. Removed.

4. **Router test overrides**: All 3 non-OS router test files (cliente,
   catalogo, estoque) needed `obter_usuario_atual` dependency override
   since the real middleware requires JWT_SECRET.

## Guard Audit

Unprotected endpoints (expected): /saude, /acompanhamento, /login.
Logout uses HTTPBearer (token required, no role check). Refresh uses
token in request body (credential mechanism for expired access tokens).
All other endpoints use `Depends(exigir_papel(...))`.

---

## Perspective #1 — Implementation Engineer

APPLIED:
- schemas.py: add max_length=128 on senha (bcrypt DoS prevention)
- use_cases.py:101: TokenRevogadoException -> TokenInvalidoException for wrong token type
- use_cases.py:105: move UUID import to module level
- token_revogado.py:12: add type-ignore justification comment
- mapping.py:66: add type-ignore justification comment
- middleware.py: consolidate duplicated _obter_jwt_service with dependencies.obter_jwt_service

REJECTED:
- middleware.py:45 session leak via next(obter_session()): deferred to step 14 by design; session is GC'd after request
- middleware.py:45 uncaught RuntimeError: JWT_SECRET missing is deployment config error, 500 is appropriate
- use_cases.py:33 TOCTOU (time-of-check-to-time-of-use) race on email_existe: DB unique constraint is the real guard; email_existe is UX convenience
- middleware.py:62 Any return type: FastAPI's Depends requires Any; adding a Callable hint breaks dependency injection
- router.py:63 __dict__ on slots dataclass: Python 3.12+ allows __dict__ access on slots dataclasses (safe for this project)
- password_hasher.py None guard: Pydantic schema prevents None reaching this layer
- test type-ignore justifications: minor, not worth test file churn

## Perspective #2 — Staff Engineer

APPLIED: duplicated JWT factory (already consolidated in #1 fix), UUID import (already fixed)
REJECTED: Any return type on exigir_papel (FastAPI Depends constraint)
PASS on naming, SOLID, Python idioms.

## Perspective #3 — Staff Architect

REJECTED: use_cases imports hash_senha from infraestrutura — pragmatic trade-off,
  hashing is a stateless utility not a domain port. Extracting a PasswordHasherPort
  for two pure functions (hash, verify) is over-engineering for this scope.
REJECTED: other contexts import exigir_papel — acceptable cross-context coupling,
  auth is a supporting/generic context providing middleware.
PASS on layer integrity within autenticacao.

## Perspective #4 — Test Engineer

PASS. All 4 flows tested with error paths. No hash inequality assertions.
Minor gaps noted: password max-length test, obter_por_email repo test.
Not blocking — integration tests in step 14 will cover these.

## Perspective #5 — Security Engineer (PRIMARY)

APPLIED: rate limit on logout (10/min)
REJECTED: docker-compose JWT_SECRET — development-only, step 15 docs
PASS on: JWT_SECRET fail-fast, bcrypt, token revocation, refresh rotation,
  rate limiting (shared singleton), token expiration, algorithm validation,
  no hardcoded secrets in source, OWASP A01/A02/A07, password min/max length,
  timing-safe comparison, no PII in logs.

## Perspective #6 — PM

PASS. Auth context covers RF/RNF (requisitos funcionais / nao-funcionais) for tech challenge.

## Perspective #7 — TPM

PASS. Dependencies declared and pinned. No orphan TODOs.

## Perspective #8 — Tech Doc Writer

NOTED: No docstrings in autenticacao module. Not blocking for this PR —
docstrings will be added in step 13 (LGPD + wiring) or step 15 (final review).
Terminology is consistent with ADR-009.

## Perspective #9 — DDD Strategic

PASS. Ubiquitous language consistent. No domain leaks across contexts.

## Perspective #10 — Test Coverage Specialist

PASS. Estimated >90% line coverage on new code. Branch gap on password
max-length (untested) and mapping load listeners (need integration tests).

## Perspective #11 — OOP Specialist

PASS. Correct entity/VO/enum modeling. Encapsulation via underscore fields.
Factory methods. Identity-based equality.

## Perspective #12 — DDD Tactical

PASS. Repository Protocols in domain. Entity identity via UUID. DTOs frozen.
Note: no domain events emitted from Usuario (acceptable for current scope).

## Perspective #13 — Maintenance Engineer

NOTED: No logging in auth module. Auth events (login, logout, failed
attempts) should be logged for audit. Not blocking — logging will be
addressed in step 13 (integration wiring) when structured logging is
connected to all contexts.

## Perspective #14 — AI Agent

PASS — N/A. No step-specific AI agent files.

## Perspective #15 — Git & GitHub Workflow

PASS. Branch naming correct. No secrets in repo. Test secrets acceptable.

## Perspective #16 — DevOps/SRE

PASS. JWT_SECRET from env with fail-fast. Token revocation via DB table
with jti index. Notes: consider Redis cache for production scale;
refresh expiration env var read at import time (restart required to change).

## Copilot Gap Analysis

| file:line | finding | missed-by | why missed | fix applied |
|---|---|---|---|---|
| router.py:63 | `**result.__dict__` fails on `slots=True` dataclass (`UsuarioDTO`) — `AttributeError` at runtime | #1 Implementation, #2 Staff Eng | #1 flagged it as MINOR (fragile), review rejected it as "Python 3.12+ supports __dict__ with slots". This was WRONG: `slots=True` prevents `__dict__` entirely; `__dict__` on 3.12+ applies to `slots=False` classes only. The rejection was based on a misunderstanding of the Python 3.12 change. | Replaced with explicit `UsuarioResponse(id=result.id, email=result.email, papel=result.papel)` |
| middleware.py:37 | `next(obter_session())` leaks session — generator `finally` never runs, connection never closed | #1 Implementation | #1 flagged it as CRITICAL. Review REJECTED it as "deferred to step 14; session is GC'd after request". This was a bad rejection — GC-based cleanup is non-deterministic, and under load or exceptions the connection pool can be exhausted. Copilot is right: this is a real leak. | Injected session via `Depends(obter_session)` on `obter_usuario_atual`, so FastAPI manages the generator lifecycle |

**Both findings map to Perspective #1 (Implementation Engineer).**
Perspective #1 identified both issues correctly, but the review incorrectly
rejected them. Root cause: the review stage optimized for velocity over
correctness when triaging #1's findings. Two learnings:

1. **Never reject a CRITICAL finding from Perspective #1 without a code-level
   proof that the behavior is safe.** "GC'd after request" is not a proof;
   it is a hope. The correct proof would have been showing that the generator
   finalizer runs deterministically — which it does not when `next()` is used
   without exhausting the generator.

2. **`slots=True` means no `__dict__` — period.** The Python 3.12 change that
   added `__dict__` support applies to regular classes, not to dataclasses
   with `slots=True`. Perspective checklists must include: "never use
   `__dict__` on frozen/slots dataclasses; use `dataclasses.asdict()` or
   explicit field access."
