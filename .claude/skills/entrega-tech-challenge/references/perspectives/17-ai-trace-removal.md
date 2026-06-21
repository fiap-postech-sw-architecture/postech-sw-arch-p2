# Perspective 17: Final Review — AI-Trace Removal & Polish

## Focus

Remove all AI-generated patterns, editing artifacts, and verify human readability.

Runs in sequence AFTER the 16 parallel reviews are applied, AFTER #18 on re-run, and one final time after #18.

## Prompt prefix

You are a senior engineer doing a final review to ensure this code and documentation reads as if written by a skilled human developer from scratch. You must catch patterns that reveal AI generation, iterative editing, or multi-version history. Check for and flag:

## Checklist (mandatory, every item must be verified)

1. **AI markers**: unintentional mentions of AI, Claude, GPT, Copilot in comments, docstrings, or docs.
   - **Exception**: Preserve intentional AI attribution (e.g., "Co-Authored-By: Claude"). The goal is removing stylistic traces, not hiding authorship.
2. **AI-style prose**: overly verbose comments explaining obvious code, unnecessary 'Note:' or 'Important:' prefixes, generic placeholder text, bullet points that all start with the same word pattern.
3. **Unnatural naming**: overly descriptive variable/function names that no human would write (e.g., `get_customer_by_unique_identifier_from_database`).
4. **AI tone in docs**: 'I'd be happy to', 'Let me explain', 'Here's how', 'As mentioned earlier', 'It's worth noting that'.
5. **Hallucinated references**: imports that don't exist, files referenced that don't exist, URLs that are broken, library APIs that don't match the pinned version.
6. **Inconsistent style**: voice/tense shifts between sections, mix of formal/informal tone, varying heading styles that suggest multiple authors.
7. **Boilerplate comments**: comments that add no value (e.g., `# Initialize the database connection` above `db = Database()`).
8. **Editing history leaks**: statements that reference prior versions, deleted content, or previous decisions that were changed (e.g., 'not just P1', 'unlike the previous approach', 'we changed this from X to Y'). A clean document should read as if it was written once, correctly.
9. **Contextless qualifiers**: phrases that qualify a statement against something the reader has no reason to expect (e.g., 'All repos are private, not just the submission repo' — if you haven't said otherwise, why clarify?). These reveal that a prior version said something different.
10. **Redundant justifications**: over-explaining decisions by arguing against alternatives the reader hasn't considered (e.g., 'We chose X because Y, not Z' when Z was never a plausible option). One-sentence rationale is sufficient unless alternatives are documented in an ADR.
11. **AI structural patterns**: numbered lists where bullets would suffice, excessive use of bold for emphasis, tables used where prose would be clearer, overly symmetric section structures.
12. **Comprehensive/exhaustive language**: words like 'comprehensive', 'exhaustive', 'thorough', 'robust' that are AI favorites but add no meaning.

## Output

List of specific removals/changes needed with file:line references. Every finding must include the exact text to change and the suggested replacement (or deletion).
