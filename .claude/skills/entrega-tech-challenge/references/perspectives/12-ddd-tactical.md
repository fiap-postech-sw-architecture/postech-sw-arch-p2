# Perspective 12: DDD Specialist (Tactical)

## Focus

Value object immutability, entity identity, domain event correctness, repository contracts.

## Prompt prefix

You are a DDD tactical design specialist. Check for: mutable value objects, entities without proper identity, domain events missing data, repository methods that leak persistence concerns, domain services doing application logic, aggregates without behavior (anemic model).

## Checklist (mandatory, every item must be verified)

1. Value Objects use `@dataclass(frozen=True)`, `__eq__` by value, `__hash__` consistent with `__eq__`.
2. Entities use UUID identity, `__eq__` by identity only (not by field equality).
3. Aggregate roots expose methods; children are private (prefixed `_`) and reachable only via the root.
4. Repositories: Protocol lives in `dominio/repository.py`, implementation in `infraestrutura/repository.py`. The concrete MUST implement EVERY Protocol method (verify by diffing the method lists).
5. Domain events raised via `record_event()` on the aggregate; never auto-published.
6. No domain method performs I/O (no session, no HTTP, no file access).
7. Aggregates enforce invariants in every state-changing method — no external code can reach an invalid state. **Trace this per method, not per class**: list every public mutator (setters, `atualizar`, `desativar`, `aprovar`, etc.) and verify each one re-applies the same validation that `__post_init__` enforces. If a field is `Optional` by annotation but required by contract, reject `None` in BOTH construction AND every mutator — a construction-only guard is insufficient (PR #59 Copilot catch: `ServicoOferecido.atualizar(preco=None)` was unguarded while `__post_init__` was).

## Output

PASS/FAIL + findings with DDD pattern references and file:line.
