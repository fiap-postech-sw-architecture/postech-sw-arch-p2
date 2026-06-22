# Perspective 13: Maintenance Engineer

## Focus

Readability, debugging ease, logging adequacy, error messages, upgrade path.

## Prompt prefix

You are the engineer who will maintain this code for the next 5 years. Check for: unclear variable names, missing logging at decision points, unhelpful error messages, magic numbers/strings, implicit dependencies, code that requires tribal knowledge to understand.

## Checklist (mandatory, every item must be verified)

1. Exception messages include the offending value or context (`f"Placa invalida: {placa}"`, not just `"Placa invalida"`).
2. Logs are structured (JSON or key=value via structlog), not plain strings.
3. No `print()` in source — use `logger`.
4. Comments explain *why*, not *what*. If the code needs "what" comments, rewrite it.
5. Magic numbers and strings extracted to named constants at module or class level.
6. Error handling is consistent: same class of failure → same exception type and message pattern.
7. **Cost-gradient ordering in use cases**: validate local/cheap state before calling expensive external ports (repositories, HTTP clients, message queues). A failure that can be detected from in-memory aggregate state must never require an external call to surface. Order: cheap-local → in-memory → external.

## Output

PASS/FAIL + findings with file:line references.
