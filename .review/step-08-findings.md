# Step 08 — Estoque — Review Findings

**Branch**: `pr/08-estoque`
**PR**: #60 (to be created)
**Baseline (after file copy)**: 441 tests, 98.29% coverage (mapping 36%, repository 83%)
**Post-fix**: 468 tests, 99.51% coverage, `src/estoque/*` at **100%** line coverage

## Review Protocol

- **16 parallel** perspectives (#1–#16) dispatched with step-08 context
- **Sequential #17 → #18 → #17** polish passes
- **Proactive pattern fixes** from PR #58/#59 lessons applied BEFORE review
- **Regression check**: all 371 prior-step tests verified passing throughout

## Proactive fixes applied (before review dispatch)

These came from PR #58/#59 lessons — we didn't wait for the perspectives to
find them again:

- **`_preco_unitario = None` invariant** — validated in both `__post_init__`
  AND `atualizar()`, matching the PR #59 Copilot finding. Extracted helpers
  `_validar_nome`, `_validar_quantidade_nao_negativa`, `_validar_preco_obrigatorio`.
- **`object.__setattr__` in mapping load listener** — replaces `target.__dict__`
  (PR #58 Copilot finding pattern).
- **`asdict()` in router responses** — 5 call sites replacing `result.__dict__`
  (PR #58 pattern).
- **`order_by(id)` on repository `listar`** — deterministic pagination
  (PR #59 perspective reinforcement).
- **`contar()` wrapper on `ListarItensEstoque`** — router no longer accesses
  private `uc._repo` (PR #59 encapsulation fix).
- **Real DTO mocks in `test_router_estoque.py`** — rewritten from
  `SimpleNamespace` to real `ItemEstoqueDTO`, exercising the `asdict`
  conversion (PR #58 regression guard).
- **Class + reservar/liberar docstrings** in `ItemEstoque`.

Baseline check after proactive fixes: **457 tests, 99.52% coverage**, all
estoque files already at 100%.

---

## Perspective #1 — Implementation Engineer — FINDINGS TRIAGED

1. **`liberar()` has no upper cap — unbounded stock inflation.**
   **REJECTED** for this PR's scope. Phase 1 design: total/reserved split is
   deferred to PR 10 (Ordem de Servico) when reservation accounting requires
   it. Current `liberar` is a compensating action, not a general mutator.
2. **`ajustar_quantidade` bypasses reservation accounting.** **REJECTED** —
   same reason. No reservation state exists yet to compare against.
3. **Event `agregado_id` + `item_id` duplicated.** **APPLIED**. Dropped
   `item_id` field from both events; the base `DomainEvent.agregado_id`
   already carries the aggregate id. Updated `reservar`/`liberar` call sites
   and two tests.
4. **Listener crash on unset `_preco_unitario`.** **REJECTED** — the
   `__post_init__` guard now catches this at construction; SQLAlchemy ORM
   rehydration always populates `_preco_valor`/`_preco_moeda` before the
   listener reads them.
5. **Transaction boundary: read-then-write outside UoW.** **APPLIED** —
   `AtualizarItemEstoque`, `AjustarQuantidade`, `DesativarItemEstoque` now
   open the UoW BEFORE calling `_obter_ou_falhar`, so the read and write
   happen in the same transaction.
6. **`obter_por_ids` drops missing ids silently.** **REJECTED** — this is
   the documented contract consumed only by PR 10. A `len` mismatch is a
   legitimate "some items disappeared" signal.
7. **`DesativarItemEstoque` race.** **APPLIED** together with #5 — the
   port check now happens inside the UoW, same transaction as the read.
8. **`type: ignore[assignment]` missing justification.** **REJECTED**
   minor — the comment explains the SQLAlchemy rehydration rationale.
9. **`listar_itens` total/items non-atomic.** **REJECTED** — Phase 1
   acceptable (same as catalogo_servicos).
10. **`EstoqueInsuficienteException` keyword construction.** Parity note,
    no action.

## Perspective #2 — Staff Engineer — FINDINGS TRIAGED

1. `obter_obter_item` awkward naming. **REJECTED** — consistent with
   `catalogo_servicos`'s factory naming.
2. Duplicated factories. **REJECTED** — same as catalogo; cross-context
   refactor tracked separately.
3. Local `ItemEstoque as _Item` alias. **APPLIED** — removed; import moved
   to module top.
4. Duplicated `load/mutate/save` shape in use cases. **APPLIED** — extracted
   module-private `_obter_ou_falhar(repo, item_id)` helper used by 4 use
   cases. Combined with finding #5 from P1 above.
5. `_preco_unitario = None` type ignore. **REJECTED** — documented.
6. `dict[str, object]` usuario. **REJECTED** — cross-context consistency.
7. `adapters.py` `(scalar(stmt) or 0) > 0`. **APPLIED** — rewrote query to
   use `select(exists().where(...))` for a clean short-circuit.
8. `repository.contar()` ternary. **APPLIED** — simplified to `or 0`.
9. Undocumented `type: ignore[attr-defined]` in mapping. **REJECTED** —
   the attributes ARE set dynamically by the mapper.

## Perspective #3 — Staff Architect — PASS

Verified: onion layers clean, domain has no leaks, `OrdemDeServicoPort`
correctly owned by Estoque (Anti-Corruption Layer), no circular imports.
Minor observation about "stub coupling risk" with PR 10 noted — not
actionable in this PR.

## Perspective #4 — Test Engineer — FINDINGS TRIAGED

1. **`# type: ignore[union-attr]` in test_use_cases_estoque.py:204.**
   **APPLIED** — replaced with the `capture → assert is not None → chain`
   pattern that the reinforced #4 checklist item 11 demands.
2. **`# type: ignore[arg-type]` on `engine_sqlite: object` fixture.**
   **APPLIED** — retyped fixture as `Generator[Engine, None, None]`, all
   5 ignores removed. (Pre-existing instances in catalogo/cliente_veiculo
   tests are out of scope.)
3. **Event payload assertions incomplete.** **APPLIED** — added
   `assert evento.agregado_id == item.id` to both `test_reservar_evento_registrado`
   and `test_liberar_evento_registrado`. This also exercises the new "drop
   item_id" event shape.
4. **`test_adapters_estoque.py` lacks real SQL test.** **APPLIED** — rewrote
   as 4 SQLite round-trip tests covering: no OS, active OS, terminal OS
   (entregue + cancelada), different item id. The adapter SQL join is now
   exercised end-to-end.
5. Repository `listar`/`obter_por_ids` don't verify SQL. **REJECTED** —
   same pattern rejected in PR #59.
6. **`AjustarQuantidade` negative path.** **APPLIED** as domain-level test
   (`_validar_quantidade_nao_negativa`).
7. **Pagination offset coverage.** **APPLIED** — new
   `test_executar_respeita_offset_e_limit` with 3 items.
8. `test_router_estoque` heavy MagicMock. **REJECTED** — same as PR #59.
9. **`assert_called_once_with` missing arg checks.** **REJECTED** minor —
   would duplicate the DTO-shape assertions already in the full-stack tests.
10. **Load round-trip for `ativo=False`.** **APPLIED** — renamed and
    extended `test_update_decompoe_preco_e_persiste_ativo` to also mutate
    `ativo` and assert the reload.
11. **`AtualizarItemEstoqueRequest` negative tests.** **APPLIED** — new
    `TestAtualizarItemEstoqueRequest` class with 3 tests.
12. Weak `test_dependencies_estoque.py`. **REJECTED** — same as catalogo.
13. Legitimate type ignores in `test_item_estoque.py`. N/A.

## Perspective #5 — Security Engineer — FINDINGS APPLIED

1-3. PASS (SQL injection, authz matrix, row locking).
4. **`descricao` no `max_length`.** **APPLIED** — `max_length=2000` on both
   `CriarItemEstoqueRequest` and `AtualizarItemEstoqueRequest`.
5. **`preco_unitario` no `max_digits/decimal_places`.** **APPLIED** —
   `max_digits=10, decimal_places=2` matches the DB column.
6. **`quantidade` no upper bound.** **APPLIED** — `le=1_000_000` on
   `CriarItemEstoqueRequest` and `AjustarQuantidadeRequest`.
7. Error messages echo user input. **REJECTED** — no PII; this is
   diagnostic detail, not a leak.

## Perspective #6 — PM — FINDINGS TRIAGED

1-3. PASS (RF-006, RN-004, RN-011).
4. **Scope drift: step file uses `adicionar_estoque`/`consumir_estoque`
   vocabulary, delivery ships `reservar`/`liberar`.** **REJECTED** for
   code change: the delivered semantics match the domain better
   (reservation is the ubiquitous-language concept); the step file is
   stale. Documented in PR body and tracked for `postech-sw-arch-p1`
   step file update.
5. PR body missing "additions beyond step file" section. **APPLIED**
   via PR body.
6. **RNF-013 no INFO logs on reservation changes.** **REJECTED** — no
   logging exists in any context yet; deferred to dedicated observability
   PR.
7-9. PASS.

## Perspective #7 — TPM — PASS

- No new deps, no orphan TODOs (the `ordem_servico` stub has a tracked
  `TODO(PR 10)`), upstream deps all satisfied. Router wiring + Alembic
  migrations deferred to consolidation step per incremental plan.

## Perspective #8 — Tech Doc Writer — FINDINGS PARTIALLY APPLIED

1-2. `reservar`/`liberar` missing preconditions + event names. **APPLIED**
   — both methods now document pre-conditions, emitted event, and raised
   exceptions.
3. Other methods missing docstrings. **REJECTED** for this PR's scope —
   matches the pattern across other contexts.
4. Events missing docstrings. **APPLIED** — added one-line docstrings to
   both event classes noting that `agregado_id` identifies the item.
5-10. Pydantic field descriptions, router summaries, etc. **REJECTED**
   for this PR's scope — tracked for a dedicated OpenAPI documentation pass.

## Perspective #9 — DDD Strategic — PASS

Anti-Corruption Layer pattern correctly applied: `OrdemDeServicoPort`
lives in Estoque, `OrdemDeServicoSQLAlchemyAdapter` translates OS tables
into Estoque's query. Zero imports from `ordem_servico.dominio` or
`ordem_servico.aplicacao`. Minor naming observation about
`OrdemDeServicoPort` vs a more Estoque-centric name — non-blocking, kept
as-is for clarity.

## Perspective #10 — Test Coverage Specialist — FINDINGS APPLIED

1. **Boundary mutation `<` vs `<=` on `reservar` guard.** **APPLIED** —
   added `test_reservar_um_acima_do_disponivel` (stock=5, reservar=6).
2. `liberar` coincidental values. PASS (non-coincidental already).
3. **`EstoqueInsuficienteException` message not asserted.** **APPLIED** —
   `match=r"disponivel=5.*solicitado=10"` on `test_reservar_estoque_insuficiente`.
4. **`DesativarItemEstoque` ordering mutant.** **APPLIED** — added
   `test_bloqueado_por_os_ativa_nao_desativa` asserting
   `recarregado.ativo is True` after the exception.
5. **`ajustar_quantidade(0)` boundary.** **APPLIED** — new test.
6. **Pagination branches.** **APPLIED** — see P4 finding 7.

## Perspective #11 — OOP Specialist — FINDINGS APPLIED

1-3. PASS.
4. **DRY: extract `_obter_ou_falhar` helper.** **APPLIED** (matches P2.4).
5-7. PASS.

## Perspective #12 — DDD Tactical — PASS

Verified that the reinforced checklist item 7 ("trace invariant
preservation through every public mutator") holds: all 6 mutators now
re-validate or toggle safely. PR #59 gap pattern correctly avoided.

## Perspective #13 — Maintenance Engineer — FINDINGS TRIAGED

1. **Cost-gradient: `DesativarItemEstoque` early return on already
   inactive.** **APPLIED** — added `if not item.ativo: return` before
   the port check, plus `test_idempotente_em_item_ja_inativo`.
2. `ItemEstoqueNaoEncontradoException` lacks offending id. **REJECTED** —
   consistent workspace pattern.
3-4. Deferred (minor).

## Perspective #14 — AI Agent — FINDINGS TRIAGED

1. **Step file says "self-contained" but adapter crosses into `ordem_servico`.**
   **TRACKED** — the step file at `postech-sw-arch-p1/orchestrator/plans/incremental-prs/incremental-step-08.md`
   needs rewording. Not actionable in this PR's working directory.
2-4. Same: step-file wording issues to fix upstream.

## Perspective #15 — Git & GitHub Workflow — PASS

Branch `pr/08-estoque` based correctly on `2fcbcd5` (PR #59 merge).
Commit format will match established pattern.

## Perspective #16 — DevOps/SRE — FINDINGS TRIAGED

1. `AjustarQuantidade` row-lock race. **REJECTED** — needs a new
   `obter_por_id_for_update` helper, out of scope for Phase 1.
2. SQLite doesn't exercise `nowait`. **REJECTED** — acknowledged Phase 1
   limitation.
3. Domain events never published. **REJECTED** — documented Phase 1
   design; outbox pattern comes with integration PRs.
4. UoW session lifecycle. **REJECTED** — carry-over from catalogo.
5. Observability. **REJECTED** — deferred.

---

## Perspective #17 — AI-Trace Removal & Polish (first pass) — APPLIED

1. Over-explained `_preco_unitario` default comment. **APPLIED** — condensed.
2. "Idempotente: itens ja inativos evitam o round-trip..." — **APPLIED**
   (deleted).
3. Adapter docstring design-rationale prose. **APPLIED** — trimmed.
4. `ordem_servico/mapping.py` "Stub incluido em PR 08... chega em PR 10"
   chatter. **APPLIED** — deleted; the module-level TODO remains.
5. "Boundary mutation-resistance" comment on reservar test. **APPLIED**.
6. "Boundary: zero e valor valido" comment. **APPLIED**.
7. "Mutante que reordene..." comment on DesativarItemEstoque test.
   **APPLIED**.
8. "os_ativa=True garante que se o early-return nao funcionar..."
   **APPLIED** (deleted).

## Perspective #18 — Human Reader — FINDINGS APPLIED

1. `_preco_unitario` comment clarity. **REJECTED** minor (already concise).
2. **Invariantes phrasing.** **APPLIED** — rewrote to "verificados na
   construcao e revalidados nos metodos que alteram estado".
3. `_obter_ou_falhar` docstring not needed. PASS.
4. **`OrdemDeServicoPort` docstring missing.** **APPLIED** — added
   three-line docstring explaining the ACL role.
5. **Adapter double-negative comment.** **APPLIED** — added
   `# OS ativa = qualquer status que nao seja terminal.`
6. **`mapping.py` properties block unexplained.** **APPLIED** — added
   comment above `map_imperatively` explaining `Dinheiro` decomposition.
7. Dependencies.py factory repetition. **REJECTED** minor.

## Perspective #17 — AI-Trace Removal & Polish (final pass) — PASS

No residual AI-trace patterns in the #18-polished comments. PR ready for
commit.

---

## Copilot Gap Analysis

Copilot posted **1 finding** on PR #60. It was legitimate and led to a
**workspace-wide** fix across all three imperative mappings. Commit
`9fa6ffa`.

### Finding 1 — `src/estoque/infraestrutura/mapping.py:66` — entity id guard not re-armed on rehydrated instances

**Copilot comment**: SQLAlchemy does not invoke `__post_init__` when
reconstructing an entity via the imperative mapper, so
`Entity.__post_init__` (which sets `self._id_atribuido = True`) never
runs on loaded instances. The `Entity.__setattr__` guard therefore
lets a caller silently mutate `id` on any entity fetched from the DB.
Fix: set `_id_atribuido = True` via `object.__setattr__` inside the
`load` listener.

**Missed by**:
- **#1 Implementation Engineer** — checklist item 9 (`@dataclass(slots=True)`
  and attribute assignment) covers the `__dict__` pattern but stops short
  of tracing the entire set of Entity invariants that `__post_init__`
  normally enforces. The reviewer looked at the VO rehydration and stopped.
- **#12 DDD Tactical** — checklist item 2 ("entities use UUID identity,
  `__eq__` by identity only, not by field equality"). The `Entity` base
  class ships a `__setattr__` guard to make identity immutable; that guard
  has to survive ORM rehydration. The reviewer verified the identity
  equality but not the immutability guarantee under rehydration.
- **#16 DevOps/SRE** — checklist item 5 (idempotent deserialization
  paths). The same `load` listener that rebuilds the VO is where the
  identity flag should also be re-armed; the reviewer focused on
  concurrency and lifecycle but did not audit the "what invariants does
  `__post_init__` set that the ORM must re-establish?" question.

**Why missed**: all three perspectives stopped at "the listener rebuilds
the VO correctly". None asked "what else does `__post_init__` normally
do that the load path is skipping?". The `_id_atribuido` field is the
only such invariant, but it's invisible unless you read the `Entity`
base class side-by-side with the listener.

**Fix applied**:
- Estoque mapping `load` listener now calls
  `object.__setattr__(target, "_id_atribuido", True)` after rebuilding
  `_preco_unitario`.
- Same fix applied to `catalogo_servicos/infraestrutura/mapping.py` and
  `cliente_veiculo/infraestrutura/mapping.py` (both had the identical
  latent bug from PRs #55 and #59).
- `cliente_veiculo` also had two remaining `target.__dict__[...]` assignments
  from the pre-PR-58 era (for `_placa` and `_documento`); those were
  replaced with `object.__setattr__` in the same commit.
- Four regression tests added: one per context's loaded-aggregate type
  (estoque, catalogo, cliente, veiculo). Each asserts that mutating
  `id` on a freshly-loaded instance raises
  `AttributeError: nao pode ser alterada apos criacao`.

### Reinforcement action

Only 1 finding on this PR (below the `>=3` threshold for mandatory
checklist reinforcement), but this maps to a shared-kernel invariant
that all imperative mappers must honor. The reinforcement will be:

**Perspective #1 — Implementation Engineer**, add checklist item 11:
"**SQLAlchemy `load` listeners must re-establish every `__post_init__`
invariant the ORM skips.** Specifically: `Entity._id_atribuido = True`
(identity guard), any VO reconstructions from decomposed columns, any
derived/cached fields. Trace `Entity.__post_init__` + the subclass's
`__post_init__` line-by-line and confirm each line has an equivalent in
the load listener. Missing this lets callers mutate supposedly-immutable
fields on rehydrated entities."

Will be committed to `postech-ai-helper` after PR #60 merges.

### Verdict

**PASS** after fixes. 0 findings remain unresolved; thread marked
`isResolved: true` via GraphQL. CI green on `9fa6ffa`. Workspace-wide
patch ships in this PR to avoid leaving the same latent bug in two
prior contexts.
