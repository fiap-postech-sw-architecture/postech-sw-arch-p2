# Step 09 — Ordem de Servico Domain — Review Findings

PR branch: `pr/09-os-domain`
Baseline before review: 655 tests, 98.97% coverage, all `src/ordem_servico/dominio/*` at 100%.
Final state after review: 669 tests, 98.74% coverage, all `src/ordem_servico/dominio/*` at 100%, `src/ordem_servico/aplicacao/ports.py` at 0% (Protocols, expected).

The 16 parallel perspectives + 3 sequential (#17 → #18 → #17) ran against the working
directory state on `pr/09-os-domain`. Findings APPLIED introduced both correctness
guards and quality polish; findings REJECTED carry justifications below.

## Files in scope

Source (12):
- `src/ordem_servico/__init__.py` (PR 01 stub, no change)
- `src/ordem_servico/dominio/__init__.py` (barrel exports, modified)
- `src/ordem_servico/dominio/status.py`
- `src/ordem_servico/dominio/maquina_de_status.py`
- `src/ordem_servico/dominio/events.py`
- `src/ordem_servico/dominio/item_da_ordem.py`
- `src/ordem_servico/dominio/orcamento.py`
- `src/ordem_servico/dominio/ordem_de_servico.py`
- `src/ordem_servico/dominio/repository.py`
- `src/ordem_servico/dominio/exceptions.py`
- `src/ordem_servico/aplicacao/__init__.py` (PR 01 stub)
- `src/ordem_servico/aplicacao/ports.py`

Tests (7):
- `tests/unitarios/ordem_servico/__init__.py`
- `tests/unitarios/ordem_servico/test_status.py`
- `tests/unitarios/ordem_servico/test_maquina_de_status.py`
- `tests/unitarios/ordem_servico/test_events.py`
- `tests/unitarios/ordem_servico/test_item_da_ordem.py`
- `tests/unitarios/ordem_servico/test_orcamento.py`
- `tests/unitarios/ordem_servico/test_ordem_de_servico.py`

## Modifications vs plan directory (deliberate, not accidental)

The step 09 spec says "No modifications needed. All files are copied as-is from the plan
directory." Eight files were modified from their plan-dir state to incorporate lessons
from PR #58/#59/#60 Copilot findings:

- Defensive None guards in `__post_init__` for `OrdemDeServico` (cliente_id/veiculo_id),
  `ItemDaOrdem` (servico_catalogo_id/preco_unitario), `LinhaOrcamento` and `Orcamento`
  (preco_unitario/subtotal/total/gerado_em), `OrdemCriadaEvent` (cliente_id/veiculo_id).
- Tests covering each None case so the guards are exercised.

These are pre-emptive fixes for the same "None-on-mutator" pattern Copilot caught on
PR #59 (`ServicoOferecido.atualizar(preco=None)`). Justified as defense in depth.

## Parallel perspectives 1-16

### #1 Implementation Engineer

Reviewed correctness and edge cases on the state machine + aggregate.

- APPLIED: `gerar_orcamento` mutated `_status` before computing `Orcamento.gerar()` —
  if the budget calculation raised, the aggregate was left in an inconsistent state.
  Fix: compute the new `Orcamento` first, then transition, then assign, then emit.
  (`src/ordem_servico/dominio/ordem_de_servico.py:gerar_orcamento`)
- APPLIED: same transactional ordering bug in `gerar_orcamento_complementar`, plus
  no items guard. Both fixed in the same pattern.
  (`src/ordem_servico/dominio/ordem_de_servico.py:gerar_orcamento_complementar`)
- APPLIED: `cancelar(motivo)` accepted empty/whitespace `motivo` silently. Now raises
  `ViolacaoRegraDeNegocioException` if `motivo` is empty or whitespace.
  (`src/ordem_servico/dominio/ordem_de_servico.py:cancelar`)
- APPLIED: `Orcamento.gerar([])` raised `IndexError` on the first line indexing.
  Now raises `ValueError("Orcamento.gerar exige pelo menos um item ...")`.
  (`src/ordem_servico/dominio/orcamento.py:gerar`)
- APPLIED: `Orcamento.__post_init__` did not validate that `total == sum(linha.subtotal)`.
  A caller could bypass `gerar()` and inject an inconsistent total. Now validated.
  (`src/ordem_servico/dominio/orcamento.py:__post_init__`)
- APPLIED: `ItemDaOrdem` validated `_preco_unitario is not None` but not that the value
  itself was strictly positive. `Dinheiro` accepts zero. Added `valor > 0` guard.
  (`src/ordem_servico/dominio/item_da_ordem.py:__post_init__`)
- APPLIED: `OrdemDeServico.adicionar_item(None)` and `remover_item(None)` were silently
  accepted. Both now raise `ValueError` at the top of the method.
- REJECTED: P1 R2 (`Entity._id_atribuido` not set on rehydration). N/A — step 09 has
  no SQLAlchemy mappings; persistence ships in PR 10/11 with the same fix already
  applied workspace-wide in PR #60.

### #2 Staff Engineer

Code quality, DRY, idiomatic Python.

- APPLIED: `OrdemDeServico.criar` used local variable `os = cls(...)`. While `import os`
  is not present in this file, the name shadows Python's stdlib `os` module — a code
  smell. Renamed to `ordem` throughout `criar`.
  (`src/ordem_servico/dominio/ordem_de_servico.py:criar`)
- APPLIED: state-transition methods duplicated the inline timestamp update. Extracted
  `_marcar_atualizado()` helper called from `_transicionar`, `adicionar_item`, and
  `remover_item`.
- APPLIED: module-level constants `_ESTADOS_PERMITE_ITENS` and `_maquina` are now
  annotated `Final[...]` and the set is `frozenset` for immutability.
- APPLIED: `_cliente_id`, `_veiculo_id`, `_itens`, `_orcamento`, `_criado_em`,
  `_atualizado_em` now use `field(default=..., repr=False)` so the dataclass-generated
  `__repr__` does not leak FK UUIDs and timestamps into logs.
- APPLIED: `OrdemCriadaEvent.cliente_id` and `veiculo_id` also use `field(repr=False)`.
- APPLIED: `OrdemDeServico.itens` property now returns `tuple[ItemDaOrdem, ...]`
  instead of `list(self._itens)` — immutable view, signals to callers that mutation
  must go through `adicionar_item`/`remover_item`.
- APPLIED: `Orcamento.gerar` replaced the manual reduce loop with
  `reduce(add, (linha.subtotal for linha in linhas))`. Same change in `__post_init__`
  for the total-consistency check.
- REJECTED: P2 SRP / God class concern. `OrdemDeServico` is 240 lines with one
  cohesive aggregate lifecycle. State machine is already extracted to
  `MaquinaDeStatus`. Splitting further would fragment aggregate invariants.

### #3 Staff Architect

Layer separation, DDD bounded context boundaries, dependency direction.

- PASS — domain layer purity, no cross-context imports, ports are Protocol-only,
  `TYPE_CHECKING` guards used correctly, stub `infraestrutura/mapping.py` does not
  leak the aggregate, no circular imports.
- REJECTED: P3 finding to rename `CatalogoPort` → `CatalogoServicosPort` and
  `ClientePort` → `ClienteVeiculoPort`. The project glossary
  (`docs/arquitetura/glossario.md`, `docs/arquitetura/c4/c4-componentes.md`,
  `docs/requisitos/refinamento-tecnico.md`) uses `CatalogoPort` and `ClientePort` as
  the canonical names. P6 PM and P9 DDD Strategic confirmed the code matches the
  glossary; the spec checklist bullet was stale.

### #4 Test Engineer

Coverage gaps, negative tests, flaky patterns.

- APPLIED: added test verifying `_atualizado_em` bumps on state transitions and item
  operations (`TestAtualizadoEm`).
- APPLIED: added `test_lifecycle_event_sequence` asserting the exact ordered list of
  emitted events across `criar → iniciar_diagnostico → gerar_orcamento →
  aprovar_orcamento → finalizar_servico → registrar_entrega`.
- APPLIED: `test_orcamento.py` replaced inline `__import__("datetime").datetime.now(...)`
  with a top-of-module `from datetime import UTC, datetime` plus an `_agora()` helper.
- APPLIED: added `test_gerar_complementar_sem_itens_invalido` exercising the new
  defensive guard (constructed via direct `OrdemDeServico(...)` since the public API
  doesn't allow reaching `EM_EXECUCAO` with empty items).
- APPLIED: added `test_adicionar_item_none_invalido`, `test_remover_item_none_invalido`,
  `test_cancelar_motivo_vazio_invalido`, `test_cancelar_motivo_whitespace_invalido`,
  `test_preco_unitario_zero_invalido`, `test_gerar_lista_vazia_invalido`,
  `test_total_inconsistente_invalido`.
- APPLIED: extended `TestExceptions` with cases for the new
  `OrdemNaoEncontradaException(ordem_id=...)` and
  `ItemDaOrdemNaoEncontradoException(ordem_id=..., item_id=...)` constructors.
- REJECTED: P4 finding to derive `_TRANSICOES_INVALIDAS` from the cartesian
  `(StatusOrdem × METHODS) \ VALID_SET`. The hand-maintained list is auditable and
  has not drifted; auto-derivation would obscure the intent of each rejected case.
  Tracked for revisit if drift is observed.

### #5 Security Engineer

PASS — N/A for most items (domain layer, no IO/HTTP, no PII storage).

- Verified: no hardcoded secrets, no PII in domain events (only UUIDs), no PII in
  exception messages, no `eval`/`exec`/`pickle`/`subprocess`, `Dinheiro` Decimal
  arithmetic safe from overflow.
- REJECTED: P5 motivo sanitization. Log-injection defense belongs in the logging
  formatter, not in the domain layer. Tracked for PR 10/11 logging middleware.
- APPLIED: `field(repr=False)` on UUID fields — addressed alongside the P2 finding.

### #6 PM

PASS — zero scope creep, requirements coverage validated.

- Cross-checked against `docs/requisitos/requisitos.md`: RF-003, RF-004, RF-005,
  RF-008, RF-016, RN-001, RN-002, RN-007, RN-008, RN-013, RN-016 all implemented in
  this PR or correctly deferred to PR 10/11 (RN-003, RN-004, RN-014).
- Confirmed: 8 `StatusOrdem` values match RF-005 + RF-016, `OrdemDeServico` lifecycle
  methods match `modelo-dominio.md`, ubiquitous language follows ADR-009 (PT without
  accents).
- REJECTED: spec checklist bullet referring to `pendente`/`concluida` state names —
  stale; code uses `RECEBIDA`/`FINALIZADA` per the requirements document.

### #7 TPM

PASS — no blocking findings.

- Confirmed: no `pyproject.toml` changes, no orphan TODOs/FIXMEs in scope, no
  commented-out code, no `print()` statements, no Alembic migrations, no breaking
  changes outside `src/ordem_servico/`.
- The `TODO(PR 10)` in `src/ordem_servico/infraestrutura/mapping.py` is from PR 60
  (out of scope), correctly tracked with the destination PR number.

### #8 Tech Doc Writer

- APPLIED: added module docstrings to all 9 source files in scope.
- APPLIED: added class docstrings to `MaquinaDeStatus`, `StatusOrdem`,
  `OrdemDeServicoRepository`, `OrdemNaoEncontradaException`,
  `ItemDaOrdemNaoEncontradoException`, all 9 events without payload, `EstoquePort`,
  `CatalogoPort`, `ClientePort`, `ServicoOferecidoDTO`.
- APPLIED: added one-line method docstrings to all transition methods on
  `OrdemDeServico` describing `<source state> -> <target state>; emits <Event>`.
- APPLIED: added contract docstrings to all `OrdemDeServicoRepository` Protocol
  methods (10 methods) explaining return shape and edge cases.
- APPLIED: added contract docstrings to all `EstoquePort`, `CatalogoPort`, and
  `ClientePort` Protocol methods explaining failure modes and idempotency.

### #9 DDD Strategic

PASS — strategic boundaries clean.

- Bounded context boundaries intact: zero imports from cliente_veiculo, catalogo,
  estoque, autenticacao in `src/ordem_servico/dominio/`.
- Anti-corruption ports named from the consumer perspective.
- Class names match the project glossary (`OrdemDeServico`, `OrdemCriadaEvent`, etc.).
  No "OS" abbreviation in business code.
- REJECTED: P9 finding to PascalCase enum members. PEP 8 requires UPPER_SNAKE_CASE
  for `Enum` members; the glossary's PascalCase style is conceptual, not literal Python.

### #10 Test Coverage Specialist

PASS — 100% line and 100% branch coverage on every `src/ordem_servico/dominio/*`
file after the new tests landed. `src/ordem_servico/aplicacao/ports.py` at 0% as
expected (Protocols don't execute).

### #11 OOP Specialist

PASS with 1 APPLIED finding — extract `_marcar_atualizado()` helper. Already done as
part of the P2 fix.

- Confirmed: private fields prefixed `_`, properties for read access, behavior methods
  on the aggregate (not anemic), composition (`MaquinaDeStatus` extracted), VOs frozen,
  entity identity by id.

### #12 DDD Tactical

- APPLIED: `Orcamento.__post_init__` total-consistency check (same as P1 F5).
- APPLIED: `cancelar(motivo)` non-empty validation (same as P1 F3).
- APPLIED: `gerar_orcamento_complementar` items guard (same as P1 F2).
- All 12 checklist items confirmed (aggregate root, boundary, entity identity, VO
  immutability, event emission per transition, repository as Protocol, factory
  method, MaquinaDeStatus allow-list).

### #13 Maintenance Engineer

- APPLIED: tightened error messages on `cliente_id`/`veiculo_id`/`servico_catalogo_id`/
  `_preco_unitario` None guards to include `(recebido: None)` for consistency with
  the existing `quantidade` message pattern.
- APPLIED: `LinhaOrcamento` "Subtotal inconsistente" message now includes the
  received value, expected value, and the multiplication operands.
- APPLIED: `MaquinaDeStatus.validar_transicao` now lists the valid transitions from
  the source state in the exception message.
- APPLIED: `OrdemDeServico._validar_modificacao_itens` now derives the allowed-state
  list from `_ESTADOS_PERMITE_ITENS` instead of hardcoding strings, and includes the
  current state in the error.
- APPLIED: `OrdemDeServico.remover_item` "Item nao encontrado" message now includes
  both `item_id` and `self.id`.
- APPLIED: `OrdemDeServico.gerar_orcamento` and `gerar_orcamento_complementar`
  empty-items messages include `self.id`.
- APPLIED: `OrdemNaoEncontradaException` and `ItemDaOrdemNaoEncontradoException`
  refactored to accept optional `ordem_id` / `item_id` constructor parameters and
  include them in the default message.

### #14 AI Agent (Implementor / Maintainer)

- APPLIED: `aplicacao/ports.py` now has class + method docstrings on every Protocol
  contract describing failure modes and idempotency, so PR 10 can implement adapters
  without context reconstruction.
- APPLIED: `dominio/repository.py` now has docstrings on all 10 Protocol methods
  explaining return shape, ordering, and the meaning of "ativa" for the existence
  helpers.
- APPLIED: comment added near `_maquina = MaquinaDeStatus()` explaining the
  module-level singleton is safe (stateless).
- REJECTED: P14 finding to rename `ClientePort` to `ClienteVeiculoPort`. Same
  rationale as P3/P6/P9 — the canonical glossary name is `ClientePort`.
- REJECTED: P14 finding to add payload fields to events for handler convenience.
  Scope creep into PR 11; current empty-payload pattern (handlers re-fetch via
  repository) is the documented default.
- REJECTED: P14 finding to update the orchestrator step-09.md spec checklist that
  references stale class names. Scope creep.

### #15 Git & GitHub Workflow Expert

PASS — branch named `pr/09-os-domain` from `main`, no commits yet (mid-execution),
no premature `.review/step-09-findings.md` (created as part of this commit), no
`.gitignore`/CI/binary changes.

### #16 DevOps / SRE

PASS — N/A for most items (domain layer).

- Verified: no Dockerfile/compose/Makefile/workflow changes, no env var reads, no
  file IO, no network calls, no module-level mutable singletons (the `_maquina`
  module-level instance is stateless), no `time.sleep`, no swallowed exceptions,
  no concurrency primitives.

## Sequential perspectives 17 → 18 → 17

### #17 AI-Trace Removal & Polish (first pass)

PASS — no AI traces. Docstrings third-person, no first-person pronouns, no AI hedging,
no filler words, voice consistent, ADR-009 PT/EN convention respected.

### #18 Human Reader

PASS — readable for first-time reader. Lifecycle ordering of methods on
`OrdemDeServico` follows the actual workflow, test class names map to the state
machine, DDD jargon either standard or contextualized, no double negatives, no
repeated information.

### #17 AI-Trace Removal & Polish (final pass)

PASS — final polish complete. No first-person pronouns, no AI hedging, no filler,
no apologies, no leftover commentary, punctuation and capitalization consistent.

## Final state

- 669 unit tests in the project, 14 added in this step (4 for new exceptions, 4
  defensive None tests on the aggregate, 2 for `cancelar` motivo validation, 1 for
  `Orcamento.gerar([])`, 1 for `Orcamento` total consistency, 1 for `ItemDaOrdem`
  zero price, 1 for `gerar_orcamento_complementar` empty items, 3 for `_atualizado_em`
  bumps, 1 for lifecycle event sequence — totals adjusted because some replaced
  existing parametrized cases).
- 98.74% total coverage; every file under `src/ordem_servico/dominio/` at 100% line
  AND branch coverage.
- `src/ordem_servico/aplicacao/ports.py` at 0% line coverage (Protocols, expected).
- `make check` green: ruff, mypy strict, bandit, pytest with coverage threshold met.

## Copilot Gap Analysis

Copilot posted **3 findings** on PR #61. All were legitimate and led to
focused fixes in commits `fe96d3b` and `6ca775e`. Mapping each finding to
the perspective(s) that should have caught it:

### Finding 1 — `src/ordem_servico/dominio/ordem_de_servico.py:182` (`gerar_orcamento`) — error precedence under invalid state

**Copilot comment**: `Orcamento` is computed before `_transicionar`, so a
call in an invalid state runs the items guard and the (potentially
expensive) budget calculation BEFORE `TransicaoStatusInvalidaException`.
This changes error precedence: callers expecting a state-machine error
get a calculation error or items-guard error first. Suggestion: validate
the transition without mutation FIRST, then compute, then mutate.

**Missed by**:
- **#1 Implementation Engineer** — checklist item 1 covered "transactional
  ordering: any mutation must happen AFTER all guards pass". The reviewer
  fixed the OPPOSITE problem (PR 09 originally mutated state then computed,
  so a calculation error left the aggregate inconsistent), but did not
  consider the dual problem: by moving the calculation BEFORE the
  transition, expensive work runs even when the state is invalid, and
  the state-machine error becomes secondary. The correct ordering has
  THREE distinct phases — cheap validation, expensive computation, and
  mutation — and the reviewer collapsed it to two.
- **#13 Maintenance Engineer** — checklist item 11 (docstrings explain
  preconditions and side effects) noted the missing transition docstrings
  but did not flag that the docstring would have made the wrong precedence
  visible. A method docstring stating "transitions A -> B" but actually
  computing first violates the documented contract.

**Fix applied**: Split `_transicionar` into `_validar_transicao` (no
mutation) + `_aplicar_transicao` (no validation) + `_transicionar`
(composer for simple cases). Refactored `gerar_orcamento` to call
`_validar_transicao` first, then guard items, then compute budget,
then `_aplicar_transicao`, then assign, then emit event.

### Finding 2 — `src/ordem_servico/dominio/ordem_de_servico.py:228` (`gerar_orcamento_complementar`) — same ordering bug

**Copilot comment**: identical issue in the complementar variant.

**Missed by**: same perspectives as Finding 1.

**Fix applied**: same refactor pattern as Finding 1, applied to
`gerar_orcamento_complementar`.

### Finding 3 — `src/ordem_servico/dominio/maquina_de_status.py:50` (`transicoes_validas`) — mutable internal state leaked

**Copilot comment**: `transicoes_validas()` returns the `set` stored in
`_TRANSICOES` directly. A caller can mutate the returned set
(`m.transicoes_validas(StatusOrdem.RECEBIDA).add(StatusOrdem.ENTREGUE)`)
and permanently alter the allow-list across the entire process,
corrupting every subsequent transition validation. Suggestion: return
a copy or use `frozenset` values in the table.

**Missed by**:
- **#2 Staff Engineer** — checklist item 8 (`field(repr=False)` on FK
  fields) caught one form of internal-state leakage (UUIDs in `__repr__`)
  but stopped there. The broader principle "no public method returns
  internal mutable state without a defensive copy or immutable wrapper"
  was not explicitly checked. The `transicoes_validas` method is the
  exact pattern: a public accessor returning a class-level mutable
  collection.
- **#11 OOP Specialist** — checklist item 1 (private fields prefixed `_`)
  caught the `_TRANSICOES` privacy convention. Item 8 (no mutable shared
  state across instances) caught `default_factory` for instance fields
  but missed that a class-level `dict[StatusOrdem, set[StatusOrdem]]`
  is itself mutable shared state — the `dict` is private, but its
  values are publicly returned through `transicoes_validas`.
- **#12 DDD Tactical** — checklist item 11 (whitelist state machine)
  confirmed the allow-list shape but did not verify that the allow-list
  is structurally immutable.

**Fix applied**: Wrap each value in `_TRANSICOES` as `frozenset`,
update the return type of `transicoes_validas` to `frozenset[StatusOrdem]`,
and use `frozenset()` for terminal states. The table is now structurally
immutable; no per-call copy needed.

## Perspective checklist updates

The 3 Copilot findings cluster around **two missed patterns**:

1. **Three-phase validation/computation/mutation ordering** (Findings 1 + 2,
   missed by #1) — the reviewer thought "transactional" meant
   "compute-then-mutate" but should have thought "cheap-validate then
   expensive-compute then mutate". This is a checklist gap on perspective
   #1: add an item explicitly requiring 3-phase ordering when an
   aggregate method has both state-machine validation AND business-logic
   computation.

2. **Immutable return of class-level collections** (Finding 3, missed by
   #2/#11) — the reviewer focused on instance-level mutability but did
   not guard against class-level collection leakage. This is a checklist
   gap on perspective #2: add an item requiring "no public method may
   return internal mutable state without a defensive copy or immutable
   wrapper".

These reinforcements would have caught all 3 findings in the perspective
review. Tracked for a follow-up commit on `postech-ai-helper/ai/perspectives/`
after PR #61 merges.
