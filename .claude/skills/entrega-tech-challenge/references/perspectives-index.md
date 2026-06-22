# Expert Perspective Reviews — Index

This file is the index of the 18 review perspectives. Each perspective lives in its own file under `perspectives/` so agents only load what they need.

## Review process

1. Launch perspectives **#1 through #16 in parallel** as sub-agents. Each sub-agent receives ONLY its own perspective file (not this index, not the other perspectives).
2. Collect all findings. Apply those that make sense; reject with justification those that don't. No finding may be silently ignored. Format rejections as `REJECTED [Perspective N]: <finding> — Reason: <justification>`.
3. Run the final reviews in sequence: **#17 → #18 → #17**. Each runs as its own sub-agent on the cumulative result of the previous steps.
4. Perform the **Copilot Gap Analysis** step below after the PR is pushed and Copilot has posted its review.

Each perspective file ends with a mandatory Checklist. A sub-agent may not return PASS without verifying every checklist item and citing file:line for every violation found. If a perspective does not apply, output `PASS — N/A (reason)`.

## Parallel perspectives (1-16)

| # | Perspective | File |
|---|---|---|
| 1 | Implementation Engineer | [`perspectives/01-implementation-engineer.md`](perspectives/01-implementation-engineer.md) |
| 2 | Staff Engineer | [`perspectives/02-staff-engineer.md`](perspectives/02-staff-engineer.md) |
| 3 | Staff Architect | [`perspectives/03-staff-architect.md`](perspectives/03-staff-architect.md) |
| 4 | Test Engineer | [`perspectives/04-test-engineer.md`](perspectives/04-test-engineer.md) |
| 5 | Security Engineer | [`perspectives/05-security-engineer.md`](perspectives/05-security-engineer.md) |
| 6 | PM | [`perspectives/06-pm.md`](perspectives/06-pm.md) |
| 7 | TPM | [`perspectives/07-tpm.md`](perspectives/07-tpm.md) |
| 8 | Tech Doc Writer | [`perspectives/08-tech-doc-writer.md`](perspectives/08-tech-doc-writer.md) |
| 9 | DDD Specialist (Strategic) | [`perspectives/09-ddd-strategic.md`](perspectives/09-ddd-strategic.md) |
| 10 | Test Coverage Specialist | [`perspectives/10-test-coverage-specialist.md`](perspectives/10-test-coverage-specialist.md) |
| 11 | OOP Specialist | [`perspectives/11-oop-specialist.md`](perspectives/11-oop-specialist.md) |
| 12 | DDD Specialist (Tactical) | [`perspectives/12-ddd-tactical.md`](perspectives/12-ddd-tactical.md) |
| 13 | Maintenance Engineer | [`perspectives/13-maintenance-engineer.md`](perspectives/13-maintenance-engineer.md) |
| 14 | AI Agent (Implementor/Maintainer) | [`perspectives/14-ai-agent.md`](perspectives/14-ai-agent.md) |
| 15 | Git & GitHub Workflow Expert | [`perspectives/15-git-github-workflow.md`](perspectives/15-git-github-workflow.md) |
| 16 | DevOps / SRE Engineer | [`perspectives/16-devops-sre.md`](perspectives/16-devops-sre.md) |

## Sequential perspectives (run after the parallel batch is applied)

| # | Perspective | File | Order |
|---|---|---|---|
| 17 | Final Review: AI-Trace Removal & Polish | [`perspectives/17-ai-trace-removal.md`](perspectives/17-ai-trace-removal.md) | S1, S3 |
| 18 | Human Reader (Conciseness & Coherence) | [`perspectives/18-human-reader.md`](perspectives/18-human-reader.md) | S2 |

The sequence is strictly **S1 → S2 → S3**: run #17, then #18, then #17 again.

## Copilot Gap Analysis (mandatory after PR Copilot review)

After the 18-perspective review and the PR is pushed, Copilot may post its own review. For every Copilot finding:

1. Map it to the perspective(s) that should have caught it (#1-#18).
2. Append a `## Copilot Gap Analysis` section to `.review/step-NN-findings.md` with: the finding, the mapped perspective, why it was missed, and the fix applied.
3. If three or more Copilot findings in a single PR map to the same perspective, update that perspective's checklist in the corresponding file under `perspectives/` (nesta skill) with a bullet that would have caught the pattern — a skill evolui por fase.

This feedback loop keeps the checklists sharp against real misses.

## Input context per perspective

- **Document reviews**: perspective prompt + artifact content + tech challenge spec da fase (ex.: `docs/requisitos/faseN/desafio-tech-fase-N.md`) + glossary.
- **Code reviews**: perspective prompt + git diff + full file context + architecture docs (RFC, ADRs, context map).

After the #17 → #18 → #17 sequence for code reviews, re-run tests (`pytest`, `mypy`, `ruff`, `bandit`).
