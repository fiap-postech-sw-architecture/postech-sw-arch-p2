# Step 04 Review Findings — Cliente+Veiculo Domain

PR branch: `pr/04-cliente-veiculo-domain`
Scope: CPF, CNPJ, Placa VOs; Documento Protocol; Cliente aggregate; Veiculo entity; domain exceptions; domain events (new: `VeiculoAdicionadoEvent`, `VeiculoRemovidoEvent`, `ClienteAtualizadoEvent`, `ClienteDesativadoEvent`); ClienteRepository Protocol (LGPD methods excluded); OrdemDeServicoPort Protocol; 7 test files + 2 new test files (`test_exceptions.py`, `test_ports.py`).

`make check`: 222 tests passing, 99.29% overall coverage, 100% on every `src/cliente_veiculo/**` file, `src/main.py` 86% (uvicorn bootstrap guard).

## Parallel batch (perspectives 1–16)

### 1. Implementation Engineer — APPLIED 2
- `cliente.py:26` / `veiculo.py:32` — `# type: ignore[assignment]` on sentinel `None` defaults missing inline justification. **APPLIED**: added `# validated in __post_init__` comment plus a class-level paragraph in Cliente/Veiculo docstrings explaining the sentinel pattern.

### 2. Staff Engineer — APPLIED 1
- `cpf.py:15-20` and `cnpj.py:15-20` — duplicated `__post_init__` validation block. **APPLIED**: extracted module-level `_NAO_DIGITO` compiled regex and `_normalizar_e_validar(numero, rotulo)` helper in both files. Each VO's `__post_init__` is now one line, behavior preserved.

### 3. Staff Architect — PASS
Domain layer has zero upstream deps (only stdlib + `brutils` + `src.compartilhado`). Application uses only domain Protocols via `ports.py`. No circular imports.

### 4. Test Engineer — APPLIED 1
- `test_veiculo.py:63-77` — two tests use `datetime.now(UTC).year` directly (real wall-clock). **APPLIED**: added an autouse `_congelar_ano_maximo` fixture that monkeypatches `veiculo_module._ano_maximo_permitido` to a deterministic `_ANO_CONGELADO + 1 = 2031`. All boundary tests now use the fixed constant. Also required a small production change: `veiculo.py` now calls a module-level `_ano_maximo_permitido()` function, making the indirection injectable without touching `datetime` directly.

### 5. Security Engineer — PASS, 1 observation DEFERRED
Checklist items verified: no PII in exception messages (CPF/CNPJ: "CPF invalido"/"CNPJ invalido" without the value), `__repr__` masks document numbers, `mascarado()` defined on all VOs, no hardcoded secrets.
- **DEFERRED** (MEDIUM): CPF/CNPJ masking currently shows 2 last digits. Reviewer suggested showing only 1 digit or hash-based masking. Deferred to a future security hardening pass — current masking already satisfies LGPD Art. 46 for debugging purposes and matches industry practice for payment systems (e.g., Stripe masks last 4 of card number).

### 6. PM — PASS
Every file traces to an RF/RNF/RN (RF-001, RF-002, RF-011, RN-005, RN-006, RN-009). LGPD intentionally excluded per step file — no scope creep.

### 7. TPM — PASS (N/A for domain-only PR)
No new dependencies, no orphan TODOs, no breaking changes.

### 8. Tech Doc Writer — APPLIED (9 items)
Added docstrings to every public class and Protocol:
- `CPF`, `CNPJ`, `Placa` (VOs)
- `Documento` (Protocol, with method docstrings)
- `Cliente` (AggregateRoot, documents invariants and event emission)
- `Veiculo` (Entity, documents year bounds and identity)
- `ClienteRepository` (Protocol, one docstring per method)
- `OrdemDeServicoPort` (ACL Protocol, documents cross-context intent)
- All 4 domain exceptions
- Each new `_normalizar_e_validar` helper

### 9. DDD Specialist (Strategic) — PASS
`cliente_veiculo` does not import from any other bounded context. Shared kernel (`compartilhado`) consumed correctly. `OrdemDeServicoPort` is the ACL to integrate with `ordem_servico`.

### 10. Test Coverage Specialist — APPLIED 1, 1 observation
- **APPLIED**: added `test_desigualdade_numero_diferente` to `test_cnpj.py` for consistency with CPF/Placa.
- `src/main.py:53-56` — uvicorn bootstrap `if __name__ == "__main__"` uncovered, standard pragma.

### 11. OOP Specialist — PASS
Cliente as AggregateRoot encapsulates Veiculo children (list private, defensive copy returned). Documento is a Protocol (structural subtyping). No god classes, composition where appropriate.

### 12. DDD Specialist (Tactical) — APPLIED 1
- Cliente aggregate had no domain events emitted. **APPLIED**: created `src/cliente_veiculo/dominio/events.py` with four events (`VeiculoAdicionadoEvent`, `VeiculoRemovidoEvent`, `ClienteAtualizadoEvent`, `ClienteDesativadoEvent`); every state-changing method on `Cliente` now calls `self._registrar_evento(...)`. `desativar` is now idempotent (second call is a no-op that does not emit a duplicate event). Added `test_eventos_emitidos_nas_transicoes_de_estado` and `test_desativar_idempotente`.

### 13. Maintenance Engineer — APPLIED 3, REJECTED 1
- `placa.py:20` — "Placa invalida" without offending value. **APPLIED**: `f"Placa invalida: {self.valor!r}"`. Placa is NOT PII; revealing the invalid input aids debugging. CPF and CNPJ error messages remain PII-safe (no raw value) per perspective #5.
- `veiculo.py:24` — hardcoded `+ 1` magic number. **APPLIED**: extracted `_ANOS_FUTURO_PERMITIDO = 1` constant. The error message now also includes the offending `ano` value: `f"Ano deve ser entre {_ANO_PRIMEIRO_CARRO + 1} e {ano_maximo}: {self._ano}"`.
- Error handling consistency: `ValueError` in VOs vs domain exceptions in cliente/repository operations. **REJECTED**: the distinction is intentional. `ValueError` signals a VO construction invariant violation (the caller passed a bad value to a `@dataclass(frozen=True)` field); domain exceptions (`ClienteNaoEncontradoException`, `PlacaDuplicadaException`) signal runtime business rules violations (e.g., "you tried to add a veiculo whose placa already exists in THIS aggregate"). Mixing them would collapse two distinct concepts.

### 14. AI Agent — PASS
Interfaces are self-documenting. Another agent could add a new VO, extend Cliente, or implement `ClienteRepository` without asking clarifying questions.

### 15. Git & GitHub Workflow — PASS
Branch `pr/04-cliente-veiculo-domain` matches convention, linear history from `main`, CI unchanged.

### 16. DevOps / SRE — PASS (N/A for domain-only PR)
No infra changes, no config drift, no new dependencies.

## Sequential batch

### S1 — #17 AI-Trace Removal & Polish — PASS
All 12 AI-trace checklist items clean on the first pass. No hedging, no AI tone, no "comprehensive" language, no editing-history leaks.

### S2 — #18 Human Reader — APPLIED 2
- `cpf.py:28` — "A instancia e imutavel (frozen dataclass)." The `(frozen dataclass)` parenthetical repeats the decorator. **APPLIED**: trimmed to "A instancia e imutavel" and then removed the whole line since the decorator is self-documenting.
- `repository.py:19` — sentence about "metodos de LGPD serao adicionados num PR futuro quando o modulo LGPD for wirado" uses slang ("wirado") and assumes internal dev-timeline context. **APPLIED**: removed the sentence entirely. The repository's current shape is what it is; future additions will be explained in their own PR.

### S3 — #17 AI-Trace Removal & Polish (final pass) — PASS
Re-scan after S2 rewrites. No new AI traces introduced. Docstrings read as single-voice human Portuguese.

## Verification

- `ruff check src/ tests/` → clean
- `ruff format --check src/ tests/` → clean
- `mypy src/` → clean (strict, zero `src.*` overrides)
- `bandit -r src/ --severity-level high` → zero findings
- `pytest tests/unitarios/ -q --cov=src --cov-fail-under=80` → 226 passing, 99.30% total coverage
- `src/cliente_veiculo/**` → 100% line coverage across all 10 files

## Copilot Gap Analysis

Copilot posted 5 findings on PR #56, all valid and all applied. This round revealed two blind spots the 18-perspective review had: PII leakage through dataclass `__repr__`, and the relationship between Protocol definitions and their actual usage.

| # | File:Line | Copilot finding | Missed by | Why missed | Fix |
|---|---|---|---|---|---|
| 1 | `events.py:30` | Domain event fields default to `""`/`0`, masking bugs (caller can emit a veiculo event with empty placa without error) | #1 Implementation Engineer, #12 DDD Tactical | I introduced the defaults myself to satisfy the `dataclass` ordering rule (`DomainEvent` has `ocorrido_em` with a default_factory, so subclass fields can't be mandatory without `kw_only`). I took the shortcut instead of using `kw_only=True`. Both perspectives looked at event content but not at the field signature | Added `kw_only=True` to the two events that carry mandatory payload (`VeiculoAdicionadoEvent`, `VeiculoRemovidoEvent`), removed all defaults, and rewrote `test_veiculo_adicionado_event_payload_obrigatorio` to check the full payload. |
| 2 | `events.py:31` | `ClienteAtualizadoEvent` carries `nome` and `contato` (PII) in the event body; events get persisted/forwarded to outbox/logs/mensageria → unnecessary PII propagation | #5 Security Engineer | The perspective flagged PII in logs and error messages, but not in domain events. Event payloads are a separate channel — outbox tables, message brokers, audit logs — that the checklist did not explicitly cover | Stripped the payload entirely. `ClienteAtualizadoEvent` now only carries `agregado_id` + `ocorrido_em` (from base). Consumers query the aggregate for current state. Test `test_cliente_atualizado_event_nao_carrega_pii` added. |
| 3 | `veiculo.py:38` | `Veiculo` documents `placa` as a required invariant, but `__post_init__` only validates `_ano`. Instantiating `Veiculo(_placa=None, ...)` succeeds and blows up later at `v.placa.valor` | #1 Implementation Engineer, #12 DDD Tactical | I added the `# type: ignore[assignment]  # validated in __post_init__` comment on the sentinel default but failed to follow up with the actual runtime guard. The comment was a promise I did not keep | Added `if self._placa is None: raise ValueError("Placa do veiculo e obrigatoria")` at the top of `Veiculo.__post_init__`. Added `test_placa_none_invalida`. |
| 4 | `cliente.py:48` | `@dataclass`-generated `__repr__` includes `_contato` (telephone) in plain text. CPF/CNPJ are masked via their own `__repr__`, but `_nome` and `_contato` are not | #5 Security Engineer | This is the single most important miss: the checklist said "PII never logged or in error messages" but did not cover Python's implicit `__repr__`. Any code that logs a `Cliente` instance (debug log, exception traceback) leaks the telephone and name | Marked `_nome`, `_contato`, and `_veiculos` with `field(repr=False)`. Added `test_repr_nao_vaza_nome_nem_contato`. |
| 5 | `cliente.py:67` | `Documento` Protocol was introduced but never used in type hints. `Cliente._documento`, `Cliente.documento` and `ClienteRepository.obter_por_documento` all still typed as `CPF | CNPJ` | #3 Staff Architect, #12 DDD Tactical | The Protocol was added for documentation; the concrete types were kept because `obter_por_documento` needed `.numero`, which wasn't on the Protocol. I did not extend the Protocol to close the gap | Added `numero: str` as a class attribute to the `Documento` Protocol. Rewired `Cliente._documento`, `Cliente.documento`, `ClienteRepository.obter_por_documento` to use `Documento`. CPF and CNPJ satisfy the Protocol structurally (no nominal subclassing needed). |

### Perspective checklist updates applied on postech-ai-helper

Two findings (#2 and #4) both target perspective #5 (Security Engineer) in the same blind spot: PII through implicit channels (event payloads, dataclass `__repr__`). Per the three-strikes rule in the canonical review protocol, a separate commit on `postech-ai-helper/ai/perspectives/` will extend #5's checklist with:

- PII in domain events: event bodies published via outbox/mensageria/audit log must not carry raw PII (nome, contato, full document). Prefer minimal payloads with `agregado_id` + consumer lookup.
- PII in `__repr__`: any `@dataclass` containing PII fields must mark them `field(repr=False)` or override `__repr__`. The default dataclass `__repr__` is a PII exfiltration vector in logs/tracebacks.

Finding #5 also touches perspective #3 (Staff Architect): a Protocol that is defined but unused is dead weight. Add to #3's checklist:

- A new abstraction (Protocol, ABC, base class) must be wired into at least one consumer at the same step it is introduced. If the concrete types are still used verbatim everywhere, the abstraction adds complexity without benefit.

### Lessons learned this round

- **Defaults in domain events are a red flag.** A `VeiculoAdicionadoEvent(placa_valor="", marca="", ...)` constructed with missing fields should fail loudly at construction time, not silently emit a garbage event.
- **Every `# type: ignore` with a "validated in __post_init__" comment must actually be validated in `__post_init__`.** Comments that promise runtime guards are debts that must be paid.
- **`@dataclass` default `__repr__` is a PII exfiltration vector.** Treat `repr=False` on PII fields as the default, not the exception.
- **A newly-defined Protocol that no one uses is worse than no Protocol.** Either wire it immediately or delete it.
