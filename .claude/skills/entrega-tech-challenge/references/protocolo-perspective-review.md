# Perspective Review Protocol

This protocol is also invoked by the [commit workflow](commit-workflow.md) before every commit.

Cost model (2026-07 revision): quality comes from *which* lenses run and from the
#17 → #18 → #17 sequence — not from launching every lens every time. Sources:
`postech-ai-helper` PR #7 (single-shot + Judge replaced the 16-perspective rules;
empirical: same anchor finding at ~1/60th the cost), superpowers
`requesting-code-review` (one reviewer with surgically-scoped context beats many
with shared history), ponytail-review (one narrow lens, one-line findings).

## Pick the tier FIRST

| Tier | When | What runs | Cost |
|---|---|---|---|
| **rapido** (default) | Day-to-day diffs, small docs, every commit | Single-shot checklist + Judge — see [code-review-canonico.md](code-review-canonico.md). Doc-only diffs: sections 8+9 only. NO per-perspective sub-agents. | 1 call + 1 cheap Judge call |
| **deep** | Significant artifact in iteration (spec, ADR, RFC, big PR, delivery doc mid-cycle) | 4–6 **grouped lenses** (below) + Judge + #17 → #18 → #17 | ~7-9 calls |
| **campeao** | ONCE per delivery artifact, at phase closing (where the 10 is decided) | Full applicable set from [perspectives-index.md](perspectives-index.md) + artifact-type extras + Judge + #17 → #18 → #17 | ~15-20 calls |

Do not escalate tiers mid-iteration: a doc that already passed campeao gets
**deep** on later touches, not campeao again. Campeao is a closing gate, not a loop.

## Select perspectives by artifact type

Launch only lenses whose checklist would NOT be mostly `N/A`. Reference sets:

- **Delivery document / README / spec**: completeness-vs-enunciado (#6/#7), factual
  accuracy vs repo (#2), structure/links (#8/#13), git/refs (#15), infra claims
  (#16), DDD/glossary naming (#9) — plus artifact-type extras: for graded school
  work, a *professor-with-rubric* lens (simulate the grader: rubric from the
  enunciado, seconds-to-find per item, where points are lost) and an *academic
  writing (PT-BR)* lens (norma culta, siglas, consistency).
- **Code / PR diff**: #1 implementation, #4 tests, #5 security, #10 coverage,
  #11 OOP, #12 DDD-tactical, #16 devops — grouped into 4-6 agents on deep tier.
- **Architecture doc (ADR/RFC)**: #3 architect, #9 strategic, #2 staff, #6 PM, #16.

Grouping for the deep tier: merge adjacent lenses into one agent each
(e.g. "completeness + traceability", "factual accuracy vs repo", "simplicity/
ponytail", "AI-trace + human reader pre-pass", "structure + links + PDF").
One agent per GROUP, not per perspective.

## Flow (deep and campeao tiers)

1. Pick the applicable perspective set (above). Each sub-agent receives ONLY:
   its perspective file(s) + the artifact + the phase spec/enunciado + glossary.
   Never the session history (surgical context — superpowers rule).
2. Launch the finders **in parallel on a cheap model** (Sonnet-class). The
   finder's job is recall; precision comes later. Findings in one-line format:
   `[SEVERITY] line — problem → concrete fix` (ponytail format).
3. **Judge filter** (canonical, cheap model or self-applied pass): drop findings that
   (a) repeat an accepted tradeoff documented in MEMORY.md;
   (b) are severity < MEDIUM AND duplicate another finding in the batch;
   (c) are speculative — their own rationale cites no specific line/symbol.
4. Triage the survivors against the plan and existing decisions. Apply what
   makes sense; explicitly reject the rest:
   `REJECTED [Perspective N]: <finding> — Reason: <justification>`.
   No finding is silently ignored. Conflicts between perspectives: the decision
   that best serves the plan prevails; document it.
5. If a sub-agent fails or returns nothing, retry once; then log
   `SKIPPED [Perspective N]: <reason>` and continue.
6. Launch **#17 (AI-Trace Removal)** alone on the cumulative result — session
   model, not the cheap one. Apply.
7. Launch **#18 (Human Reader)** alone on the result of #17, WITH this
   constraint added to its prompt: *"your rewrites must themselves satisfy the
   #17 checklist — no new bold emphasis, tricolons, hedging, marketing
   adjectives or em-dash chains"*. Apply.
8. **Verify #18's edits** (this replaces the old third agent pass — see
   rationale below):
   a. Run `python scripts/lint_ai_trace.py <artifact>` (mechanical subset of
      #17: banned phrases PT/EN + emphasis density; exits 1 on findings).
   b. Self-apply the judgment items of the #17 checklist to the DIFF that
      step 7 introduced (a handful of lines), not the whole document.
   c. Escalate to a full #17 agent pass ONLY if the linter fails, the
      self-check finds something, or step 7 rewrote a large share of the
      document (rule of thumb: >20% of lines). If step 7 made no prose
      rewrites (only mechanical applications), skip this step entirely.
9. Run the **Copilot Gap Analysis** loop (below) after the PR is pushed.

### Why the final sequence is no longer three agent passes

The old S1→S2→S3 (#17 → #18 → #17) existed because #18's rewrites can
reintroduce AI-isms. Measured on the fase-2 delivery doc (2026-07-07): S1
found 12 findings, S2 found 11, **S3 found 0** at the cost of a full-document
agent pass — pure regression insurance with near-zero yield once S2 is
constrained. The revision keeps the guarantee and drops the cost:

- **Prevent at the source** (superpowers `requesting-code-review`: the
  reviewer prompt carries its constraints): #18 is forbidden from
  reintroducing the patterns, so the regression source shrinks.
- **Verify with a script, not an agent** (official Anthropic skill guide,
  "Step 5: Verify output — run verify_output.py; if verification fails,
  return to Step 2"; superpowers `writing-skills`: "if it's enforceable with
  regex, automate it — save documentation for judgment calls").
- **Scope the check to the diff** — S2 touches a handful of lines; re-reading
  the whole artifact re-verifies text S1 already cleared.
- **Escalate on signal, not by default** (canonical evaluator-optimizer:
  loop until convergence, not a fixed N of passes; ponytail-review: when
  there is nothing to cut, say so and stop).

## Rules (unchanged invariants)

- Never skip #17. It runs twice: after the parallel batch is applied, and after #18.
- Every finding of any severity is resolved (applied or rejected with reason)
  in the same pass — nothing becomes a "later issue" silently; residuals worth
  tracking become GitHub issues, referenced in the rejection line.
- Each perspective file ends in a mandatory Checklist; a sub-agent may not
  return PASS without verifying every item. Non-applicable items:
  `PASS — N/A (reason)`.
- For code reviews, after #17 → #18 → #17 re-run `ruff check`,
  `ruff format --check`, `mypy src/`, `bandit -r src/` and `pytest`.

## Copilot Gap Analysis (MANDATORY after PR push)

For every Copilot finding on the pushed PR:

1. Map it to the perspective(s) that should have caught it.
2. Append a `## Copilot Gap Analysis` section to `.review/step-NN-findings.md`
   with: the finding (file:line + description), the mapped perspective, why it
   was missed, and the fix applied.
3. If three or more Copilot findings in one PR map to the same perspective,
   update that perspective's checklist with an item that would have caught the
   pattern, and commit separately.

## Context per review type

- **Documents**: perspective file + artifact + tech challenge enunciado + glossary.
- **Code**: perspective file + git diff + full file context + architecture docs
  (RFC, ADRs, context map).
