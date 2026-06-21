# Perspective Review Protocol

This protocol is also invoked by the [commit workflow](commit-workflow.md) before every commit.

## When to Use

Whenever a review is requested, or upon completing a significant artifact (architecture document, code module, RFC, ADR, PR diff).

## Flow

1. Load `../perspectives.md` (one level up, in the `ai/` directory) for the index of 18 perspective files.
2. Launch perspectives **1 through 16 as parallel sub-agents**. Each sub-agent receives only its own file under `../perspectives/NN-*.md` plus the artifact content and applicable spec/glossary.
3. Collect findings from all 16 sub-agents.
4. Evaluate each finding against the full context of the plan and existing decisions.
5. Apply all findings that make sense, regardless of severity.
6. Explicitly reject (with 1-line justification) those that don't — reviewers have narrow expertise and may suggest changes that conflict across perspectives or with existing architectural decisions.
7. No finding may be silently ignored: every finding is either applied or rejected with reason.
8. If a sub-agent fails or returns no findings, retry once; if it fails again, log as `SKIPPED [Perspective N]: <error reason>` and continue.
9. Launch perspective **#17 (AI-Trace Removal)** alone on the cumulative result, apply corrections.
10. Launch perspective **#18 (Human Reader)** alone on the result of #17, apply corrections.
11. Launch perspective **#17** one final time on the result of #18.
12. Run the **Copilot Gap Analysis** loop (see below) after the PR is pushed.

## Rules

- Never skip #17 (AI-Trace Removal).
- #17 runs twice: once after the parallel batch is applied, and once after #18.
- Every finding of any severity (CRITICAL, HIGH, MEDIUM, LOW) must be resolved (applied or rejected with justification) before proceeding.
- No finding becomes a "later issue" — resolve in the same pass.
- Rejected findings must be listed as `REJECTED [Perspective N]: <finding> — Reason: <justification>`.
- Conflicts between perspectives: the decision that best serves the overall plan prevails; document the conflict and the reasoning.
- Each perspective file ends in a mandatory Checklist. A sub-agent may not return PASS without verifying every checklist item.

## Copilot Gap Analysis (MANDATORY after PR push)

After the 18-perspective review is complete and the PR is pushed, GitHub Copilot will post its own review. For every Copilot finding:

1. Map it to the perspective(s) that should have caught it (#1-#18).
2. Append a `## Copilot Gap Analysis` section to `.review/step-NN-findings.md` with: the exact finding (file:line + description), the mapped perspective(s), why it was missed, and the fix applied.
3. If **three or more** Copilot findings in a single PR map to the same perspective, update that perspective's checklist in `postech-ai-helper/ai/perspectives/NN-*.md` with a new item that would have caught the pattern. Commit separately on `postech-ai-helper` with a `docs(perspectives): strengthen N checklist after gap analysis` message.

This feedback loop keeps the checklists sharp against real misses.

## How to Use

### For document reviews

Sub-agents receive: perspective file + artifact content + tech challenge doc (e.g., `postech-sw-arch-p1/docs/requisitos/requisitos.md` relative to workspace root) + glossary.

### For code reviews

Sub-agents receive: perspective file + git diff + full file context + architecture docs (RFC, ADRs, context map).
After the #17 → #18 → #17 sequence, re-run static checks (`ruff check`, `ruff format --check`, `mypy src/`, `bandit -r src/`) and tests (`pytest`).

### If a perspective does not apply

Output `PASS — N/A (reason)`. Example: `PASS — N/A, documentation file, no runtime code.`
