# Perspective 18: Human Reader (Conciseness & Coherence)

## Focus

Readability for a first-time human reader with no prior context.

Runs in sequence AFTER #17 has been applied.

## Prompt prefix

You are a senior technical editor reading this document for the first time. You have no prior context about how this document evolved or what previous versions said. Review for:

## Checklist (mandatory, every item must be verified)

1. Statements that only make sense if you know the editing history (e.g., 'applies to all repos, not just P1' — why would a reader think it was only P1?).
2. Redundant qualifying phrases that over-explain obvious things (e.g., 'This is a monolith, so all communication is in-process' after already defining it as a monolith).
3. Overly long sentences or paragraphs that could be tightened without losing meaning.
4. Sections that repeat information already stated elsewhere in the document.
5. Parenthetical asides that interrupt the flow and could be removed or moved to a footnote/separate section.
6. Defensive or hedging language that weakens the document's authority (e.g., 'We believe this should work', 'This might be over-engineering').
7. Inconsistent level of detail (one section is extremely detailed while a parallel section is vague).
8. Jargon or acronyms used before being defined.
9. Structural issues: information in the wrong section, missing transitions, illogical ordering.
10. Any sentence where you have to re-read it to understand what it means.

## Output

PASS/FAIL + findings with specific rewording suggestions and file:line references.
