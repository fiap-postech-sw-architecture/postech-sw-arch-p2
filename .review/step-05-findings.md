# Step 05 Review Findings — Cliente+Veiculo Application

PR branch: `pr/05-cliente-veiculo-app`
Scope: 8 use cases (`CriarCliente`, `ListarClientes`, `ObterCliente`, `AtualizarCliente`, `DesativarCliente`, `AdicionarVeiculo`, `ListarVeiculos`, `RemoverVeiculo`) + 6 DTOs (LGPD deferred) + helper functions (`_veiculo_dto`, `_tipo_documento`, `_cliente_dto`, `_cliente_resumo_dto`, `_obter_cliente_ou_falhar`) + comprehensive test suite. Also tightened the `Documento` Protocol (`@property` for `numero`) to satisfy mypy structural subtyping after the step 04 change.

`make check`: 255 tests passing, 99.46% overall coverage, 100% on every `src/cliente_veiculo/aplicacao/*.py`, `src/main.py` 86% (uvicorn bootstrap guard).

## Parallel batch (perspectives 1–16)

### 1. Implementation Engineer — APPLIED 2, REJECTED 1
- `test_use_cases_cliente.py:54` — `FakeUnitOfWork.__exit__` signature uses `exc_tb: object` instead of `TracebackType | None`. **APPLIED**: imported `TracebackType` under TYPE_CHECKING, tightened the type. Same fix as PR #54 recurrence — the fake wasn't updated when the Protocol was tightened.
- `use_cases.py:169-178 (AdicionarVeiculo)` — no validation on `dto.marca`/`dto.modelo` (empty strings accepted). **APPLIED**: added two `ViolacaoRegraDeNegocioException` guards at the top of `executar`, with messages including field name. Added tests `test_marca_vazia_rejeitada` and `test_modelo_vazio_rejeitado`. Note: `dto.ano` negative/zero is already rejected by `Veiculo.__post_init__` via the year bounds constant.
- `use_cases.py:127-135 (AtualizarCliente)` — no validation on `dto.nome`/`dto.contato`. **REJECTED**: `Cliente.atualizar()` already raises `ValueError` on empty nome (tested in PR #54). Empty contato is a valid state (client may not have a phone at creation time).

### 2. Staff Engineer — APPLIED 3
- 5 duplicated "save + uow.commit" blocks. **APPLIED**: extracted `_salvar_com_commit(cliente)` as a private method on `CriarCliente`, `AtualizarCliente`, `DesativarCliente`, `AdicionarVeiculo`, `RemoverVeiculo` (one per use case that persists state — kept local to each class instead of a module-level helper so the UoW dependency stays injected via constructor).
- 4 duplicated "obter_por_id + raise if None". **APPLIED**: extracted module-level `_obter_cliente_ou_falhar(repo, cliente_id) -> Cliente` that returns the non-None Cliente or raises `ClienteNaoEncontradoException`. Used across `ObterCliente`, `AtualizarCliente`, `DesativarCliente`, `AdicionarVeiculo`, `ListarVeiculos`, `RemoverVeiculo`.
- Local import `from src.cliente_veiculo.dominio.cliente import Cliente as _Cliente` inside `CriarCliente.executar`. **APPLIED**: moved to module level. No circular import results (verified via `make check`).

### 3. Staff Architect — PASS
Application layer has zero imports from infraestrutura/interfaces. `UnitOfWork` is the Protocol from `compartilhado.aplicacao`, never `SQLAlchemyUnitOfWork` directly. `OrdemDeServicoPort` is consumed via Protocol. `Documento` Protocol introduced in PR #56 is actively used in `use_cases.py` as the type annotation for the `documento:` local variable and in the repository signature — no dead-weight abstraction.

### 4. Test Engineer — APPLIED 2
- `test_paginacao` reused `CPF_VALIDO` for all 5 clients, which silently bypasses uniqueness in the fake repository. **APPLIED**: introduced `_POOL_CPFS` with 7 distinct valid CPFs (generated via `brutils.cpf.generate`) and `_cpf_alternativo(seed)` helper; `test_paginacao` now uses distinct documents.
- Missing negative test for invalid CPF/CNPJ format in `CriarCliente`. **APPLIED**: added `test_documento_invalido_cpf_malformado` and `test_documento_invalido_cnpj_vazio` that exercise the `ValueError` raised by CPF/CNPJ `__post_init__` through the use case.

### 5. Security Engineer — APPLIED 1, REJECTED 1, DEFERRED 1
- **HIGH** `dtos.py:42-50` — `ClienteDTO` default `__repr__` leaks PII (`nome`, `contato`, `documento_formatado`). **APPLIED**: marked `nome`, `documento_formatado`, `contato` on `ClienteDTO` and `nome`, `contato` on `ClienteResumoDTO`, `CriarClienteDTO`, `AtualizarClienteDTO` with `field(repr=False)`. This is the exact same PII-through-`__repr__` pattern we saw on the Cliente aggregate in PR #56; the updated perspective #5 checklist (items #11 and #12 added after PR #56) caught it here.
- **CRITICAL** `ClienteDTO.documento_formatado` exposes raw CPF/CNPJ. **DEFERRED**: this is a legitimate concern but removing the field now would break the expected contract for admin/detail endpoints in step 11. Mitigated for logs/tracebacks via `repr=False`. Tracked as an explicit follow-up: step 11 (Ordem de Servico Interfaces) and step 12 (Autenticacao) must revisit whether `documento_formatado` should be gated behind an admin role, returned only to owner, or replaced with a signed URL / explicit endpoint.
- **MEDIUM** `CriarClienteDTO.documento` carries raw input; risk if exception handlers log the whole DTO. **REJECTED (implicit):** the global error handler (`src/compartilhado/interfaces/error_handler.py`) never logs request bodies; it only logs the exception and request_id. The DTO itself now has `repr=False` on the document field, so even a debug traceback would not leak it.

### 6. PM — PASS
All 8 use cases + 6 DTOs trace to RF-001 (CRUD clientes), RF-002 (CRUD veiculos), RN-005 (unique CPF/CNPJ), RN-006 (unique placa), RN-009 (deactivation/remove guard against active OS). LGPD code confirmed absent per the step file (`dtos.py` has 6 DTOs, `use_cases.py` has 8 use cases).

### 7. TPM — PASS (N/A, application-layer PR, no new deps)

### 8. Tech Doc Writer — APPLIED (all items)
Added docstrings to:
- 8 use case classes (purpose, preconditions, postconditions, exceptions where relevant)
- 4 helper functions (`_veiculo_dto`, `_tipo_documento`, `_cliente_dto`, `_cliente_resumo_dto`)
- 1 new helper `_obter_cliente_ou_falhar`
- 6 DTOs (including PII handling notes on `ClienteDTO` and `ClienteResumoDTO`)

### 9. DDD Specialist (Strategic) — PASS
No cross-context imports. `OrdemDeServicoPort` is the ACL between `cliente_veiculo` and `ordem_servico`. DTOs translate domain aggregates at the boundary. Ubiquitous language consistent.

### 10. Test Coverage Specialist — PASS
Every critical branch covered: tipo_documento guard (cpf/cnpj/invalid), duplicate-documento, UoW commit/rollback, active-OS guard (deactivate and remove), placa duplicate, cliente_nao_encontrado, veiculo_nao_encontrado. 100% line coverage on `src/cliente_veiculo/aplicacao/**`.

### 11. OOP Specialist — PASS
Use cases as commands/queries with DI via constructor. No god classes (smallest use case has 1 method, largest has 2). Composition via injected Protocols. No isinstance chains except the single legitimate one in `_tipo_documento` to dispatch CPF vs CNPJ (which is the correct design — a CPF/CNPJ discriminator is not polymorphic, it's a value inspection).

### 12. DDD Specialist (Tactical) — PASS
DTOs are `@dataclass(frozen=True, slots=True)`. Aggregates are never returned raw — always translated via `_cliente_dto` / `_veiculo_dto` / `_cliente_resumo_dto`. Every write wraps in `with self._uow:` and commits. Invariants enforced in the aggregate, not re-implemented in the application layer (the `marca`/`modelo` empty check is an application-level validation, not a domain invariant — correct separation).

### 13. Maintenance Engineer — PASS
Exception messages include offending values where not PII (`tipo_documento invalido: <value>`). Domain exceptions (`ClienteNaoEncontrado`, etc.) correctly omit PII. No `print()`. Error handling consistent.

### 14. AI Agent (Implementor/Maintainer) — PASS
Next PR (infrastructure) will wire these use cases. Protocol signatures are unambiguous, every return type and exception documented. An agent can implement `ClienteSQLAlchemyRepository` and `OrdemDeServicoPort` without asking clarifying questions.

### 15. Git & GitHub Workflow — REJECTED (sub-agent misread work-in-progress state)
The sub-agent flagged "branch not from PR #56" and "uncommitted changes" as failures. Both are expected during active development — the branch IS from `main` post-PR #56 merge (commit `2ce119f`), and the uncommitted state is exactly what a review-in-progress looks like. No action.

### 16. DevOps / SRE — PASS (N/A, application-layer only)
No infrastructure, config, secrets, or operational surface changes.

## Sequential batch

### S1 — #17 AI-Trace Removal & Polish — PASS
All 12 AI-trace checklist items clean on first pass. Docstrings read as human-authored Portuguese.

### S2 — #18 Human Reader — REJECTED
The sub-agent suggested adding Portuguese accents (`unico` → `único`, `Precondicoes` → `Precondições`) and trimming "defensive" docstring language. **REJECTED**: ADR-009 is explicit that business terms use Portuguese WITHOUT accents; the suggested rewording would violate the language convention on nearly every item. The remaining "redundant preconditions" finding (AdicionarVeiculo docstring) is documenting the contract, not the implementation — legitimate docstring content. No action.

### S3 — #17 AI-Trace Removal & Polish (final) — PASS
Re-scan after S1 + S2 decisions. No new AI traces. Voice consistent throughout.

## Verification

- `ruff check src/ tests/` → clean
- `ruff format --check src/ tests/` → clean
- `mypy src/` → clean (strict mode, zero `src.*` overrides)
- `bandit -r src/ --severity-level high` → zero findings
- `pytest tests/unitarios/ -q --cov=src --cov-fail-under=80` → 256 passing, 99.46% coverage
- `src/cliente_veiculo/aplicacao/**` → 100% line coverage across 3 files

## Copilot Gap Analysis

Copilot posted 2 findings on PR #57, both valid and both applied.

| # | File:Line | Copilot finding | Missed by | Why missed | Fix |
|---|---|---|---|---|---|
| 1 | `use_cases.py:50` (`_tipo_documento`) | The helper returned `"cpf" if isinstance(cliente.documento, CPF) else "cnpj"`, silently labeling any future non-CPF Documento implementation as `"cnpj"`. Since the aggregate now types `_documento` as the `Documento` Protocol, any new structural implementation could be misclassified | #1 Implementation Engineer, #11 OOP Specialist | I introduced the `Documento` Protocol refactor in PR #56 and wired it through in PR #57 without revisiting the consumers that switch on concrete types. The helper was written before the Protocol existed and retained the binary assumption | Explicit `isinstance` chain for both `CPF` and `CNPJ` with a `ViolacaoRegraDeNegocioException` fallback that includes the offending type name. New test `test_tipo_documento_desconhecido_levanta` uses a structural `_DocumentoFake` that satisfies the Protocol but is neither CPF nor CNPJ. |
| 2 | `use_cases.py:264` (`RemoverVeiculo.executar`) | `self._os_port.existe_os_ativa_para_veiculo(veiculo_id)` was called before verifying the veiculo belongs to the client, causing an unnecessary (potentially expensive) port call when the veiculo does not exist in the aggregate — and potentially breaking if the port implementation assumes existence | #1 Implementation Engineer, #13 Maintenance Engineer | I mirrored the `DesativarCliente` flow (which calls the port first) without thinking about the ordering asymmetry — DesativarCliente already has the cliente loaded, but RemoverVeiculo must also confirm the veiculo_id is inside the client's veiculos list | Short-circuit check: `if not any(v.id == veiculo_id for v in cliente.veiculos): raise VeiculoNaoEncontradoException()` runs before the port call. The existing `test_veiculo_nao_encontrado` test now exercises the short-circuit path (no port invocation needed). |

### Perspective checklist updates

Finding #1 maps cleanly to perspective #1 (Implementation Engineer) and hints at a broader pattern: **whenever a Protocol is introduced, every consumer that switches on concrete types must be re-verified**. This is the inverse of #3's existing "don't introduce unused Protocols" rule. Adding to #1's checklist in `postech-ai-helper`:

- When a dependency changes from a Union (`CPF | CNPJ`) to a Protocol (`Documento`), every consumer that pattern-matches on the concrete types must be updated or hardened to handle the open-world case (raise on unknown, not silently default).

Finding #2 maps to perspective #13 (Maintenance Engineer). Adding a bullet:

- Validate state locally before calling out to external ports (repositories, HTTP clients, message queues). Ordering rule: cheap-local-checks before expensive-external-checks. Short-circuit failure modes should not require the external call to surface them.

### Lessons learned this round

- **Protocol introductions change the shape of consumers.** The step 04 refactor to expose `Documento` was safe in isolation, but step 05 consumers needed a matching audit.
- **Use case ordering should follow a cost gradient**: local-data guards first, then in-memory validation, then external/expensive ports. Short-circuit on the cheapest check available.
