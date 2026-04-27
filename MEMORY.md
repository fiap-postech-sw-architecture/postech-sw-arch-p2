# Project Memory -- postech-sw-arch-p1

Add-only log of project-specific learnings. New entries go to the **top** of each section. Never edit historical entries -- add a contradicting entry instead.

Updated by AI agents at task end per `postech-ai-helper/ai/canonical/task-end-review.md`. Format and update rules: `postech-ai-helper/ai/canonical/memory.md`.

> Entries tagged **[in-flight from PR #N]** describe behaviour that lives on a feature branch not yet merged to `main`. They are kept here so the lesson survives across reviews; once the PR merges, drop the tag.

## Recent decisions

- 2026-04-26 - Adopted unified harness pointers around `postech-ai-helper/ai/agent-bootstrap.md` -- prior per-harness configs duplicated content and drifted -- PR on `postech-ai-helper/feat/agent-bootstrap-and-memory`

## Discovered conventions

- 2026-04-26 - Coverage configuration lives in `pyproject.toml` (not `.coveragerc`) -- look there for thresholds and exclusions
- 2026-04-26 - The `Makefile` uses `bash -c '...'` extensively in its rules -- on Windows it must run from Git Bash, not PowerShell
- 2026-04-26 - Per ADR-009 the codebase identifiers (entities, methods, variables) are written in Portuguese **without accents**; user-facing prose (READMEs, ADRs, setup guides) is in Portuguese with normal orthography

## Gotchas

- 2026-04-26 - The canonical workspace root is `~/git/fiap/postech-sw-architecture/` (per `postech-ai-helper/ai/canonical/workspace-structure.md`); cloning directly under `~/git/fiap/` still works for sibling-relative pointers, but the helper's `setup.sh` exits non-zero when run from a non-canonical workspace, and on Windows symlink creation requires Developer Mode regardless
- 2026-04-26 - **[in-flight from PR #81]** On Windows, the project's Docker socket detection script must detect the named pipe (`\\.\pipe\docker_engine`) instead of probing only Unix sockets; the MINGW/MSYS/CYGWIN branch in `scripts/docker-check.sh` (added in PR #81) resolves this
- 2026-04-26 - **[in-flight from PR #81]** Server-side render of NiceGUI `@ui.page` handlers runs before the client websocket connects; any handler-time HTTP call that writes to `app.storage.tab` raises `RuntimeError` unless the storage adapter is defensive (returns None and no-ops on writes when the backend is unreachable)

## Tech debt / TODO

- 2026-04-26 - LOW - **[in-flight from PR #81]** HTTP probes during initial render of a NiceGUI page should be deferred to a `client.on_connect` handler (or equivalent) so they execute with a client context instead of as side effects of import/render
