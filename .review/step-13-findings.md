# Step 13 — LGPD + App Factory + Integration Wiring: Perspective Review Findings

## Summary

PR adds LGPD compliance (ConsentimentoCliente entity, 4 LGPD use cases,
5 new endpoints on cliente router) and finalizes integration. Proactively
fixed `__dict__` on `slots=True` dataclasses across all cliente router
endpoints (lesson from PR #64 Copilot). Added load listeners for
`_id_atribuido` and `_eventos_pendentes` on rehydration.

## Pre-review fixes

1. **`__dict__` on slots dataclasses** (proactive): all `**result.__dict__`
   calls in `cliente_veiculo/interfaces/router.py` replaced with
   `**dataclasses.asdict(result)`. DTOs use `frozen=True, slots=True`.

2. **Mapping load listeners**: added `_id_atribuido` re-arm on Veiculo
   and ConsentimentoCliente load; added `_eventos_pendentes` re-arm on
   Cliente load.

3. **Route count + route set tests** updated for 13 routes (was 8).

4. **Preserved working-dir improvements**: restored `schemas.py` from
   main (keeps dynamic year validation + docstrings), added LGPD schemas
   at end. Restored `Documento` Protocol import in infra repository (plan
   dir had `CPF | CNPJ`). Restored `order_by` on `listar()`.

---

## Perspective #1 — Implementation Engineer

APPLIED: repository.py:74-81 — anonimizar_dados did not clear _documento
(encrypted CPF/CNPJ) or documento_hash. Hash is brute-forceable for
11-digit CPF space. Added clearing of both fields.
PASS on ConsentimentoCliente validation, revogar() guard, dataclasses.asdict.

## Perspective #2 — Staff Engineer

PASS. Consistent patterns, TYPE_CHECKING used correctly, frozen+slots DTOs.

## Perspective #3 — Staff Architect

PASS. LGPD code contained within cliente_veiculo. No infra in domain.

## Perspective #4 — Test Engineer

APPLIED: added double-revocation propagation test for RevogarConsentimento.
PASS on remaining test coverage.

## Perspective #5 — Security (PRIMARY)

APPLIED: CRITICAL — anonimizar_dados now clears encrypted documento and
documento_hash (LGPD Art. 18, V right to erasure).
PASS on: data export returns all PII; no PII in logs; all endpoints
behind exigir_papel; encryption at rest for documento.

## Perspective #6 — PM

PASS. LGPD features satisfy RF/RNF (requisitos funcionais / nao-funcionais).

## Perspective #7 — TPM

PASS. No new deps. No orphan TODOs.

## Perspective #8 — Tech Doc Writer

PASS. Pydantic schemas provide field constraints and examples.

## Perspective #9 — DDD Strategic

PASS. Ubiquitous language consistent. ConsentimentoCliente in cliente_veiculo.

## Perspective #10 — Test Coverage Specialist

PASS. >90% coverage on new LGPD code. 893 tests, 98% total.

## Perspective #11 — OOP Specialist

PASS. ConsentimentoCliente extends Entity with identity and behavior.

## Perspective #12 — DDD Tactical

PASS. Entity with UUID identity, revogar() behavior, Protocol-based repo.

## Perspective #13 — Maintenance Engineer

PASS. No logging in LGPD use cases (correct — avoids PII leakage).

## Perspective #14 — AI Agent

PASS — N/A.

## Perspective #15 — Git & GitHub Workflow

PASS. Branch naming correct. No secrets.

## Perspective #16 — DevOps/SRE

PASS. No new infra concerns. Consentimentos table indexed by jti.

NOTE (not blocking): no unique constraint on (cliente_id, tipo) for
consentimentos table. Multiple historical consents allowed by design.

## Copilot Gap Analysis

8 findings. 7 missed by all 16 perspectives. 1 partially caught (#1 found
the missing fields but not the listener overwrite).

| file:line | finding | missed-by | why missed | fix applied |
|---|---|---|---|---|
| repository.py:86 | **CRITICAL**: before_update listener OVERWRITES anonymized values — PII survives | #1, #5 | #1 caught missing doc fields but fixed with direct attr write without tracing ORM event lifecycle. Fundamental flow-tracing gap. | Raw SQL UPDATE bypasses listener |
| repository.py:84 | "ANONIMIZADO" hash violates unique constraint | #1, #5 | Never considered multi-client anonymization scenario | Unique tombstone: `ANONIMIZADO:{id}` |
| mapping.py:154 | _decompor_documento fallback else silently writes "cnpj" | #1, #3 | Perspectives focused on domain, not infra event listeners | Explicit isinstance chain + TypeError |
| mapping.py:135 | Load listener fallback else creates wrong type | #1, #3 | Same infra blind spot | Explicit if/elif/else + ValueError |
| mapping.py:120 | __dict__ write instead of object.__setattr__ | #2 | Consistency check skipped | object.__setattr__ for slots-safety |
| repository.py:24 | Protocol uses CPF\|CNPJ instead of Documento | #3, #12 | Regression from plan dir copy not caught | Documento Protocol |
| dtos.py:16,50 | PII fields in repr (nome, documento, contato) | #5, #13 | Security review didn't check repr leakage | field(repr=False) on all PII |

**Root cause**: the perspective review dispatches breadth (16 angles) but
sacrifices depth. None of the 16 perspectives traced the full data flow:
`anonimizar_dados()` → `session.flush()` → `before_update` listener →
re-encryption of original `_documento`. This requires reading 3 files
together and mentally executing the SQLAlchemy event pipeline. The
perspectives read files individually and never simulate the flush cycle.

**Process change**: for steps with ORM persistence changes, add a mandatory
**data-flow trace** sub-step before the perspective review: for every
repository method that writes data, trace the value through all
before_insert/before_update/load listeners and verify the persisted
result matches intent.
