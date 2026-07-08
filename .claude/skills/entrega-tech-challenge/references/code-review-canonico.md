# Code Review Protocol

Single-shot review with checklist + Judge filter. Replaces the 16-parallel-perspective protocol (archived at `../_archive/perspectives-2026-04/`).

## When to use

- **Pre-commit**: on the diff of any non-trivial change. Mandatory.
- **CI rapido (auto)**: on PR open, single-shot prompt + Judge filter (cheap model).
- **CI deep (on-demand)**: triggered by `@claude` comment, evaluator-optimizer iterative loop on top of the same prompt. Reserve for high-stakes diffs (DDD core, security, infra).

For documentation-only diffs (`*.md`, `docs/`), run sections **8 + 9** only.

## The single-shot review prompt (canonical)

> You are reviewing a diff. Walk this checklist sequentially and report findings ONLY where evidence exists in the diff. Each finding must include: `file:line` + one sentence + severity (`CRITICAL` | `HIGH` | `MEDIUM` | `LOW`) + suggested fix. For each section with nothing to flag, output `PASS — <one-line reason>`.

### 1. Correctness & edge cases
Off-by-one, null/empty, unexpected types, async races, error swallowing, primitives crossing boundaries, exception classes too broad/narrow.

### 2. Security
Injection (SQL, shell, path), authz drift, secret leakage, PII/LGPD masking, deserialization, SSRF. Defer details bandit/semgrep already cover unless the diff disables them.

### 3. Tests
Missing branch coverage, missing negative path (e.g. exception NOT swallowed), fragile mocks, missing assertion of non-effects (e.g. "ensure X was NOT called"), tests that pass without exercising the change.

### 4. DDD layering
Cross-context imports, domain depending on infra/aplicacao, aggregate boundaries violated, primitives where Value Objects exist, drift from ubiquitous language. See `ai/ddd/strategic.md` and `ai/ddd/tactical.md`.

### 5. Architecture & maintainability
SOLID violations that hurt readability, premature or missing abstraction, duplicated logic, dead code, mutable returns from collections.

### 6. Naming & language (ADR-009)
PT/EN hybrid respected, accents stripped from identifiers, ubiquitous language drift. See `ai/canonical/language.md`.

### 7. Operational concerns
Logging level, error messages actionable for ops, observability gaps, deployment surface (CI, Dockerfile, secrets, env vars).

### 8. Documentation
Public API undocumented, README/ADR drift, inline comments saying *what* instead of *why*, hallucinated PR/issue numbers.

### 9. AI-trace removal (always last)
AI-isms (`certainly`, `would like to`, `I'll`), references to nonexistent files, editing leaks (`# removed:`, half-applied diffs), repetitive prose in docstrings/commits.

## Judge filter (two-stage)

After the generator returns findings, run a Judge prompt with a cheap model (Haiku/Sonnet, single call):

> Given these findings and the project's MEMORY.md, drop any finding that:
> (a) repeats a known accepted tradeoff documented in MEMORY.md;
> (b) is severity < MEDIUM AND repeats a finding already raised in this batch;
> (c) is speculative — the finding's own rationale doesn't cite a specific symbol/line that the generator already saw.
>
> Output the surviving findings in the same format.

Implementation note: Judge sees only findings + MEMORY.md, not the diff or full repo — keeps cost ~$0.02–0.05/PR. Speculative findings are detected from the finding text itself, not by re-reading the diff.

## Iterative deep mode (on-demand, replaces 16-perspective deep)

For diffs that warrant extra rigor (touched by `@claude deep` comment, or labels `security`/`ddd-core`):

1. Run the single-shot prompt (generator).
2. Run the Judge filter.
3. For each surviving HIGH/CRITICAL finding, prompt the generator with: *"Challenge: argue why this finding might be wrong. If you concede, drop it; otherwise restate with stronger evidence."* This is the evaluator-optimizer pattern — single-thread, no parallelism.
4. Optional final pass: synthesize a 5-line summary for the human reviewer.

## Anti-rules

- **DO NOT** spawn parallel sub-agents per concern. Coding tasks fail at coordination (MAST 2025: 37% of multi-agent failures are coordination breakdowns; Cognition: "don't build multi-agents"; Anthropic: multi-agent ≠ coding).
- **DO NOT** append new findings to checklists indefinitely. Lessons go to `MEMORY.md` Review Lessons section; consolidation per `memory.md`.
- **DO NOT** use this protocol on doc-only diffs in full — run sections 8+9 only.
- **DO NOT** rerun the same finding across sections. Each finding belongs to one section.

## Context pack

Before invoking the prompt, the agent assembles a deterministic context pack per `context-pack.md` (diff + touched aggregates/ports + adjacent tests + MEMORY.md slice). Investing in *what* enters context produces more recall than adding reviewers.

## Why this replaces the 16-perspective protocol

Empirical: PR #97 (postech-sw-arch-p1-review) — single-shot rapido captured the same anchor finding as 16-perspective local at 1/60th the cost. Literature: Anthropic, Cognition, MAST, arXiv 2505.18286 all converge: under matched compute, single-agent code review equals or beats multi-agent. Trust drops with noise (Stack Overflow 2026: trust at 29%, -11pp YoY); Judge filter recovers it (Diamond/Graphite: <3% FP).

Detailed historical checklist items (lessons accumulated from prior PRs) live in `code-review-checklist-extended.md` — consultable, not always-loaded.
