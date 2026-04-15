# Step 07 — Catalogo de Servicos — Review Findings

**Branch**: `pr/07-catalogo-servicos`
**PR**: #59 (to be created)
**Baseline**: 368 tests, 99.30% coverage (before review)
**Post-fix**: 378 tests, 99.38% coverage, `src/catalogo_servicos/*` at 100% (except N/A lines)

## Review Protocol

Executed the full 18-perspective review as mandated by
`postech-ai-helper/ai/canonical/perspective-review.md`:

1. **Parallel batch** — 16 perspectives dispatched concurrently (#1–#16)
2. **Sequential #17** — AI-Trace Removal & Polish (first pass)
3. **Sequential #18** — Human Reader
4. **Sequential #17** — AI-Trace Removal & Polish (final pass)

All perspectives ran against the files copied from the plan directory, with
proactive pattern-matching against PR #58 Copilot findings
(`@dataclass(slots=True)` + `__dict__`, `SimpleNamespace` mocks, missing
`order_by` in paginated queries, silent Protocol-vs-Union fallbacks).

## Regression Check

`make check` executed once on the baseline and once after every batch of
fixes. All 368 tests from steps 01–06 continued to pass at every stage —
**no regressions introduced by step 07**. Final state: 378 tests green,
99.38% total coverage.

---

## Perspective #1 — Implementation Engineer — FINDINGS APPLIED

1. `dominio/servico_oferecido.py` — `_preco: Dinheiro = None` had no validation
   in `__post_init__`. Any construction without `_preco` succeeded silently
   and crashed at first mapping insert. **APPLIED**: added explicit
   `if self._preco is None: raise ValueError("Preco do servico e obrigatorio")`,
   plus a negative test `test_preco_none_invalido`.

2. `infraestrutura/mapping.py` — `target.__dict__["_preco"] = ...` would
   crash if `ServicoOferecido` ever adopts `__slots__`. Same fragility pattern
   Copilot flagged in PR #58. **APPLIED**: replaced with
   `object.__setattr__(target, "_preco", Dinheiro(...))`.

3. `dominio/servico_oferecido.py` — `type: ignore[assignment]` without
   justification. **APPLIED**: added concise comment explaining the SQLAlchemy
   `load` event rehydration pattern.

4. `interfaces/dependencies.py` — UoW closing a request-scoped session it
   does not own (carry-over from `cliente_veiculo` in PR #58).
   **REJECTED** for this PR's scope: it is a pre-existing pattern across
   contexts and will be addressed in a dedicated refactor PR to avoid
   scope creep here. Tracked for the consolidation step.

5. `aplicacao/use_cases.py` — `ListarServicos.executar()` and `contar()`
   are not atomic. **REJECTED**: acceptable for Phase 1 pagination; client
   may see a brief inconsistency between `total` and `len(items)` under
   write contention. Hardening deferred to Phase 2.

6. `interfaces/router.py` — `usuario: dict[str, object]` parameter unused.
   **REJECTED**: FastAPI requires the parameter binding for the `Depends`
   side-effect to run. The `_=Depends(...)` pattern would work but would
   diverge from the established pattern in PR #58's `cliente_veiculo`
   router. Preserving consistency across contexts.

## Perspective #2 — Staff Engineer — FINDINGS APPLIED (partially)

1. `dominio/servico_oferecido.py` — `_preco: Dinheiro = None` same issue as P1.
   **APPLIED** (see P1).

2. Duplicated validation block in `__post_init__` and `atualizar()`.
   **APPLIED**: extracted module-private `_validar_nome_e_descricao(nome, descricao)`.

3. `CriarServicoDTO` == `AtualizarServicoDTO` (byte-identical), same for
   the request schemas. **REJECTED**: kept separate to allow independent
   evolution (e.g., adding mandatory-only-on-create fields later). This
   is the same pattern established in `cliente_veiculo`.

4. Five near-identical factory functions in `dependencies.py`.
   **REJECTED**: each factory has its own return type and set of arguments;
   a unified helper would either leak types (`Any`) or need a Generic with
   five overloads, which is noisier than the repetition. Pattern matches
   `cliente_veiculo/interfaces/dependencies.py` in PR #58.

5. `usuario: dict[str, object]` unused. **REJECTED** (see P1).

6. Local import inside `CriarServico.executar`. **APPLIED**: added concise
   justification comment (`# Import local evita ciclo com o modulo de dominio.`).

7. `infraestrutura/mapping.py` — module-level `_mapeamento_iniciado` flag.
   **REJECTED**: pattern matches `cliente_veiculo/infraestrutura/mapping.py`;
   thread-safety not a concern since `iniciar_mapeamentos` is called once at
   startup (not during request handling).

8. `infraestrutura/repository.py` — review-chatter comment referencing PR 58
   and "checklist #1 item 10". **APPLIED**: removed the chatter; the
   `.order_by(...)` call is self-explanatory.

9. `infraestrutura/mapping.py` — `target.__dict__["_preco"] = ...`.
   **APPLIED** (see P1).

## Perspective #3 — Staff Architect — PASS with minor findings

1. Function-local imports in `interfaces/dependencies.py` and
   `aplicacao/use_cases.py`. **APPLIED** (partially): added module docstring
   to `dependencies.py` documenting the intent, and an inline comment in
   `use_cases.py`. **REJECTED** moving imports to module top: the current
   pattern matches `cliente_veiculo`, and runtime cycles would only surface
   at first request.

2. `_preco` default with type ignore. **APPLIED** (see P1).

3. Module-level `_mapeamento_iniciado` state. **REJECTED** (see P2.7).

4. `object.__setattr__` fragility. **APPLIED** (see P1.2).

Protocol wiring satisfies checklist #8: all five use cases type-hint against
`ServicoOferecidoRepository` Protocol, not the concrete SQLAlchemy class.

## Perspective #4 — Test Engineer — FINDINGS APPLIED (partially)

1. `test_use_cases_catalogo.py::TestListarServicos::test_com_dados` only
   asserted `len == 1`; no field assertions. **APPLIED**: added assertions
   on `nome`, `preco`, `moeda`, `ativo`.

2. `test_use_cases_catalogo.py` — no `contar()` test. **APPLIED**:
   added `TestListarServicos::test_contar`.

3. `test_dependencies_catalogo.py` — only asserts `uc is not None`.
   **REJECTED** for this PR's scope: pattern matches `cliente_veiculo`
   dependencies tests; strengthening requires a workspace-wide refactor.
   Tracked for consolidation step.

4. `test_repository_catalogo.py` — MagicMock args not verified with
   `assert_called_once_with(...)`. **REJECTED**: the tests exercise
   delegation shape, not SQL semantics; the SQLite round-trip in
   `test_mapping_catalogo.py::TestEventosMapeamentoServico` is the
   integration test of record.

5. `test_router_catalogo.py` — `test_adicionar_servico_direto` style tests
   bypass FastAPI. **REJECTED**: calling the route function directly is
   the pattern used to exercise the `dataclasses.asdict()` conversion
   that PR #58 flagged. The `TestClient`-based tests (`test_criar_servico`,
   `test_listar_servicos`) also exist for full-stack coverage.

6. `test_router_catalogo.py` uses `MagicMock` (not `spec=`). **REJECTED**
   for now: `spec=` would require importing five use-case classes and
   tighten tests slightly; tracked for a workspace-wide test hardening
   pass.

7. `test_mapping_catalogo.py` — UPDATE event listener not covered.
   **APPLIED**: added `TestEventosMapeamentoServico::test_update_decompoe_preco`
   that mutates `_preco` and asserts `preco_valor`/`preco_moeda` are
   rewritten on flush.

## Perspective #5 — Security Engineer — FINDING APPLIED

1. `schemas.py` — `descricao: str = Field(min_length=1)` had no `max_length`;
   FastAPI would accept ~MB-sized strings from admins. **APPLIED**: added
   `max_length=5000`, plus a negative test `test_rejeita_descricao_acima_do_limite`.

Other checks: all 5 endpoints protected by `exigir_papel`; no PII (services
= business inventory); parametrized queries only; exceptions don't leak IDs.

## Perspective #6 — PM — PASS with minor findings

1. RBAC drift: `requisitos.md` lists all `/servicos` endpoints as admin-only,
   but the router grants read access to `admin`, `atendente`, `mecanico`.
   **REJECTED** for code changes: the broader read access matches the step
   file's focus checklist (`admin`, `atendente`, `mecanico` is the explicit
   target). Tracked as a documentation sync task for `postech-sw-arch-p1`.

2. PR body doesn't list out-of-scope items (e.g., referential integrity
   check against `ItemDaOrdem`). **APPLIED**: PR body (created below)
   mentions deferred items.

## Perspective #7 — TPM — FINDINGS PARTIALLY APPLIED

1. No Alembic migration for `servicos_oferecidos` table. **REJECTED** for
   this PR's scope: consistent with `cliente_veiculo` in PR #58 — migrations
   are deferred to a dedicated consolidation step (aligned with the
   incremental PR plan in `orchestrator-incremental-prs.md`).

2. Router not wired in `src/main.py`. **REJECTED** for this PR's scope:
   consistent with `cliente_veiculo` in PR #58 — wiring is deferred to the
   dedicated consolidation step.

3. `iniciar_mapeamentos()` not called at startup. **REJECTED**: same
   deferred-to-consolidation rationale.

4. Uncommitted working tree state. **N/A**: this is the reviewer observing
   a work-in-progress state; commits follow immediately after review.

## Perspective #8 — Tech Doc Writer — FINDINGS PARTIALLY APPLIED

1. `ServicoOferecido` aggregate root has no class docstring. **APPLIED**:
   added a class docstring documenting invariants.

2. `__post_init__`, `atualizar`, `desativar`, `ativar` have no docstrings.
   **APPLIED**: added concise docstrings to `atualizar`, `desativar`, `ativar`.

3. Use cases (`CriarServico`, `ListarServicos`, etc.) have no docstrings.
   **REJECTED** for this PR's scope: the use-case class names are
   self-descriptive (CQRS-style), and adding placeholder docstrings would
   be busy-work. If a specific use case grows non-obvious behavior, a
   docstring will be added at that time.

4. Pydantic models missing `Field(description=...)`. **REJECTED** for this
   PR's scope: OpenAPI descriptions will be polished in a dedicated
   documentation pass across all schemas.

5. Router endpoints missing `summary`/`response_model` kwargs. **REJECTED**
   for same reason as #4.

## Perspective #9 — DDD Strategic — PASS

- No cross-context leaks (only import outside `catalogo_servicos` is from
  `compartilhado` and the sanctioned `autenticacao.interfaces.middleware`).
- Folder = context boundary.
- Ubiquitous language respected: `ServicoOferecido`, `Dinheiro`, `preco`.

## Perspective #10 — Test Coverage Specialist — FINDING APPLIED

1. `aplicacao/use_cases.py:63` — `ListarServicos.contar()` uncovered (98% line).
   **APPLIED**: added `test_contar` (use_cases.py now at 100%).

All other `catalogo_servicos/*` files already at 100% line coverage.

## Perspective #11 — OOP Specialist — PASS

- Encapsulation respected (private `_` fields, read-only properties).
- No god classes.
- SRP per use case.
- Composition over inheritance.
- Factories return Protocols.

Minor suggestion to add a `ServicoOferecido.criar(...)` classmethod
**REJECTED** for this PR's scope: the dataclass kwargs pattern is
established across all contexts; changing it here would diverge.

## Perspective #12 — DDD Tactical — FINDINGS APPLIED

1. `_preco: Dinheiro = None` missing invariant check. **APPLIED** (see P1).

2. `desativar()`/`ativar()` idempotent without documentation. **APPLIED**:
   added "Idempotente" to each method's docstring, plus two regression
   tests `test_desativar_idempotente` and `test_ativar_idempotente`.

3. No domain events registered. **REJECTED** for this PR's scope: no
   consumers of `ServicoDesativadoEvent`/`PrecoAlteradoEvent` exist yet.
   Adding events with no consumers would be speculative. Events will be
   added when `OrdemDeServico` needs to react (PR 10+).

## Perspective #13 — Maintenance Engineer — FINDINGS PARTIALLY APPLIED

1. `ValueError` messages in `servico_oferecido.py` don't include the
   offending value. **APPLIED**: added `{nome!r}` / `{descricao!r}` to both
   validation messages via the new `_validar_nome_e_descricao` helper.

2. `ServicoNaoEncontradoException` doesn't include `servico_id`.
   **REJECTED** for this PR's scope: matches the pattern across all
   other `NaoEncontradoException` subclasses in the workspace. Changing
   here only creates drift; workspace-wide change tracked separately.

3. No logging in use cases. **REJECTED** for this PR's scope: no logging
   exists in any context yet. Logging will be added in a dedicated
   observability PR (step 14/15).

4. Role strings hardcoded ("admin", "atendente", "mecanico"). **REJECTED**:
   role enum belongs in `autenticacao` context (PR 12); using strings
   consistent with the stub `exigir_papel` until then.

5. Review-chatter comment in `repository.py`. **APPLIED** (see P2.8).

6. Cost-gradient ordering. **PASS** — use cases correctly order Pydantic
   (cheap boundary) → domain validation (in-memory) → DB hit (expensive).

## Perspective #14 — AI Agent — PASS with minor findings

1. Line-count drift in step file table. **REJECTED** for this PR's scope:
   line counts changed because of the in-scope fixes applied above; step
   file will be updated in a follow-up commit on `postech-sw-arch-p1`.

2. "Copy as-is" has no verification command. **REJECTED**: tracked as
   enhancement to orchestrator docs; not a code issue.

3. Numbering contradiction (`#17 → #18 → #17` in step file vs canonical
   protocol). **REJECTED** — already fixed in `perspectives/` refactor
   on `postech-ai-helper`.

## Perspective #15 — Git & GitHub Workflow — PASS

- Branch name correct: `pr/07-catalogo-servicos`.
- Branch base correct: HEAD at PR #58 merge commit.
- Upstream will be set via `git push -u origin pr/07-catalogo-servicos`.
- Commit format will match prior PR single-line style.

## Perspective #16 — DevOps/SRE — FINDINGS REJECTED (out of scope)

1. Router not wired in `main.py`. **REJECTED** (see P7.2).
2. `iniciar_mapeamentos()` not called. **REJECTED** (see P7.3).
3. Alembic migration missing. **REJECTED** (see P7.1).

Middleware ordering (preserved from PR #58), config SSOT, and logging to
stdout all **PASS**.

---

## Perspective #17 — AI-Trace Removal & Polish (first pass) — FINDINGS APPLIED

1. `mapping.py` — tribal-knowledge reference to "Copilot no PR 58".
   **APPLIED**: removed.

2. `test_router_catalogo.py` — review-chatter block + "tests antigos
   usavam SimpleNamespace". **APPLIED**: trimmed to one concise sentence.

3. `test_router_catalogo.py` — `# Note:` block explaining why we don't
   override `obter_usuario_atual`. **APPLIED**: deleted.

4. `servico_oferecido.py` — helper docstring `(elimina duplicacao)`
   parenthetical. **APPLIED**: removed.

5. `repository.py` — boilerplate SQL behavior comment. **APPLIED**:
   deleted (the `.order_by(...)` call is self-explanatory).

6. `test_use_cases_catalogo.py` — review-chatter comment on `test_contar`.
   **APPLIED**: deleted.

7. `test_servico_oferecido.py` — boilerplate comment on `test_preco_none_invalido`.
   **APPLIED**: deleted.

8. `servico_oferecido.py` — verbose `_preco` default comment. **APPLIED**:
   condensed.

9. `test_mapping_catalogo.py` — boilerplate on `test_update_decompoe_preco`.
   **APPLIED**: deleted.

## Perspective #18 — Human Reader — FINDINGS APPLIED

1. `_preco` default comment unclear for first-time readers. **APPLIED**:
   expanded to name the mechanism (SQLAlchemy `load` event).

2. "invariante" vague. **APPLIED**: clarified.

3. `__slots__` future-state hedge. **APPLIED**: comment deleted.

4. `dependencies.py` repetitive factories without a hint. **APPLIED**:
   added module docstring explaining the intent.

5. `uc` jargon in router. **APPLIED**: renamed to `use_case`.

6. Local import in `CriarServico.executar` unexplained. **APPLIED**:
   added one-line comment.

7. `_servico_dto(s)` single-letter param. **APPLIED**: renamed to `servico`.

8. `CriarServicoRequest` == `AtualizarServicoRequest` duplication unclear.
   **REJECTED** — the pattern is established; adding a comment here would
   invite a comment in every workspace DTO pair.

## Perspective #17 — AI-Trace Removal & Polish (final pass) — FINDINGS APPLIED

1. `use_cases.py` — defensive qualifier on local import. **APPLIED**:
   trimmed.

2. `servico_oferecido.py` — over-explained `_preco` default. **APPLIED**:
   condensed to a single sentence.

Final verdict: **PASS**. No residual AI-trace patterns, no hedging, no
tribal-knowledge leakage. Code reads as if written by a human reviewer.

---

## Copilot Gap Analysis

Copilot posted **2 findings** on PR #59. Both were legitimate and fixed in
commit `0791ecc`. Mapping each finding to the perspective(s) that should
have caught it:

### Finding 1 — `servico_oferecido.py:68` — `atualizar()` missing `preco is None` guard

**Copilot comment**: The domain method `ServicoOferecido.atualizar()`
accepts `preco=None`, violating the `__post_init__` invariant that `_preco`
is mandatory. Fix: raise `ValueError` if `preco is None` before mutating.

**Missed by**:
- **#1 Implementation Engineer** — checklist item 4 ("inputs validated
  before use") caught the same issue in `__post_init__` (and it was
  APPLIED), but the reviewer stopped there. The `atualizar()` method was
  treated as "follows the same shape as cliente_veiculo's update" and the
  symmetry was not verified field-by-field. The new `_preco` guard was
  only added to construction; the mutator path kept the original
  unvalidated assignment from the plan-directory copy.
- **#12 DDD Tactical** — checklist item 7 ("aggregate methods must preserve
  invariants") caught the construction-time gap but applied the same
  "construction only" scope. An aggregate root's invariants must hold
  after ANY public method, not just construction.

**Why missed**: Both perspectives recognized the invariant-protection
pattern but limited their scope to `__post_init__`. The reviewers did
not trace every mutator to verify the invariant is reapplied. The helper
function `_validar_nome_e_descricao` was extracted for symmetry but
`_preco` validation was NOT lifted into a similar helper, so the mutator
quietly kept the old shape.

**Fix applied**: Added the same `if preco is None` guard to
`atualizar()`, plus `test_atualizar_preco_none_invalido` regression test.

### Finding 2 — `test_use_cases_catalogo.py:166` — `# type: ignore[union-attr]` in assertion

**Copilot comment**: Avoid `# type: ignore[union-attr]` by capturing
`obter_por_id` result in a variable, asserting `is not None`, then
checking `.ativo`. Clearer failure message + no ignore comment.

**Missed by**:
- **#4 Test Engineer** — checklist item 6 ("minimize `# type: ignore` in
  tests; prefer `assert ... is not None` when narrowing a `T | None`
  result"). The reviewer flagged many MagicMock/spec issues but skipped
  over the single `type: ignore` line in `test_desativar_servico::test_sucesso`.

**Why missed**: The `# type: ignore[union-attr]` was copied verbatim
from the plan-directory file and blended into a test body the reviewer
was already marking PASS. Narrow-by-assertion is a pattern the reviewer
did not actively search for.

**Fix applied**: Captured the lookup in `servico_atualizado`, added
`assert servico_atualizado is not None`, then `assert not
servico_atualizado.ativo`.

### Reinforcement action

Neither perspective exceeded the 3-finding threshold for mandatory
checklist reinforcement, but Finding 1 reveals a gap pattern worth
tightening:

**Perspective #1 — Implementation Engineer**, checklist item 4
should be sharpened from "Inputs validated before use" to explicitly
name the mutator audit: **"Invariants validated in `__post_init__`
AND in every public mutator that can change the same field. If the
field is `Optional` by type but required by contract, both entry
points must raise the same `ValueError`."**

This change is small enough to land as a single-commit update on
`postech-ai-helper` after merging PR #59. Tracked as a follow-up task.

### Verdict

**PASS** after fixes. 0 findings remain unresolved; both threads marked
`isResolved: true` via GraphQL.
