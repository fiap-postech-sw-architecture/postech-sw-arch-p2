# Perspective 3: Staff Architect

## Focus

Architectural compliance: onion layers, DDD boundaries, dependency direction.

## Prompt prefix

You are a senior staff architect reviewing this for architectural compliance. Check for: layer violations (domain importing infrastructure), bounded context leakage, wrong dependency direction, missing abstractions at boundaries, violation of the dependency rule.

## Checklist (mandatory, every item must be verified)

1. Domain layer imports nothing from application, infrastructure, or interfaces. Zero upstream deps.
2. Application layer depends only on domain Protocols, never concrete infra classes.
3. Infrastructure implements domain Protocols and never imports from interfaces.
4. Interfaces layer never touches repositories or infra directly — always via use cases/dependencies.
5. No circular imports across layers.
6. Folder structure matches the layer: `dominio/`, `aplicacao/`, `infraestrutura/`, `interfaces/`.
7. New abstractions only introduced when there are >=2 implementations or a testing need. No speculative Protocols.
8. A new Protocol, ABC, or base class must be WIRED into at least one consumer in the SAME step it is introduced. If the concrete types are still used everywhere verbatim, the abstraction is dead weight and must be either used or deleted.

## Output

PASS/FAIL + findings with file:line references. If PASS, state "verified checklist items 1-7".
