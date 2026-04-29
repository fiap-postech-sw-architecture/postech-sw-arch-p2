# Project Memory -- postech-sw-arch-p1

Add-only log of project-specific learnings. New entries go to the **top** of each section. Never edit historical entries -- add a contradicting entry instead.

Updated by AI agents at task end per `postech-ai-helper/ai/canonical/task-end-review.md`. Format and update rules: `postech-ai-helper/ai/canonical/memory.md`.

> Entries tagged **[in-flight from PR #N]** describe behaviour that lives on a feature branch not yet merged to `main`. They are kept here so the lesson survives across reviews; once the PR merges, drop the tag.

## Recent decisions

- 2026-04-28 - Correção de inventário no apêndice de funcionalidades extras: o arquivo lista 19 features (5+3+2+3+3+3), não 14 como a entrada de 2026-04-27 indicou; entrada anterior preservada por add-only mas o número canônico no documento é 19
- 2026-04-27 - Apêndice de funcionalidades extras criado em `docs/entrega/apendice-funcionalidades-extras.md`; documenta 14 features além do escopo mínimo do desafio FIAP, ancoradas em commits/PRs (#19, #62, #64, #65, #75, #81)
- 2026-04-27 - 10 issues abertas (#99–#108) no `fiap-postech-sw-architecture/postech-sw-arch-p1` para fechar gaps de entrega (soat-architecture access, Discord, vídeo, PDF, 6 scans de segurança); cada issue formatada como playbook executável por agente (workflow A/B/C/D)
- 2026-04-26 - Added the NiceGUI-based UI of simulation (`ui/`) as a sandbox for manual API testing -- not a production deliverable, dev-only, not packaged in `pyproject.toml` `setuptools.packages.find` -- PR #81
- 2026-04-26 - Adopted unified harness pointers around `postech-ai-helper/ai/agent-bootstrap.md` -- prior per-harness configs duplicated content and drifted -- PR on `postech-ai-helper/feat/agent-bootstrap-and-memory`

## Discovered conventions

- 2026-04-26 - Coverage configuration lives in `pyproject.toml` (not `.coveragerc`) -- look there for thresholds and exclusions
- 2026-04-26 - The `Makefile` uses `bash -c '...'` extensively in its rules -- on Windows it must run from Git Bash, not PowerShell
- 2026-04-26 - Per ADR-009 the codebase identifiers (entities, methods, variables) are written in Portuguese **without accents**; user-facing prose (READMEs, ADRs, setup guides) is in Portuguese with normal orthography

## Gotchas

- 2026-04-26 - On Git Bash (MSYS2) absolute Unix-style paths (`/tmp/foo`) passed as args to native Windows binaries (e.g. `docker.exe`) are auto-translated to Windows paths (`C:/Users/.../Temp/foo`); the Makefile prefixes `MSYS_NO_PATHCONV=1` on `docker compose cp/exec` lines that pass `/tmp/...` to keep the path literal inside the container. Without it, `make seed-users-docker` and `make reset-db` fail with `No such file or directory: /app/C:/Users/...` from python in the container
- 2026-04-26 - The canonical workspace root is `~/git/fiap/postech-sw-architecture/` (per `postech-ai-helper/ai/canonical/workspace-structure.md`); cloning directly under `~/git/fiap/` still works for sibling-relative pointers, but the helper's `setup.sh` exits non-zero when run from a non-canonical workspace, and on Windows symlink creation requires Developer Mode regardless
- 2026-04-26 - On Windows, the project's Docker socket detection script must detect the named pipe (`\\.\pipe\docker_engine`) instead of probing only Unix sockets; the MINGW/MSYS/CYGWIN branch in `scripts/docker-check.sh` (added in PR #81) resolves this
- 2026-04-26 - Server-side render of NiceGUI `@ui.page` handlers runs before the client websocket connects; any handler-time HTTP call that writes to `app.storage.tab` raises `RuntimeError` unless the storage adapter is defensive (returns None and no-ops on writes when the backend is unreachable)

## Tech debt / TODO

- 2026-04-26 - LOW - HTTP probes during initial render of a NiceGUI page should be deferred to a `client.on_connect` handler (or equivalent) so they execute with a client context instead of as side effects of import/render
