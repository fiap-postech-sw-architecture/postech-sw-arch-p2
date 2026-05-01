# Project Memory -- postech-sw-arch-p1

Add-only log of project-specific learnings. New entries go to the **top** of each section. Never edit historical entries -- add a contradicting entry instead.

Updated by AI agents at task end per `postech-ai-helper/ai/canonical/task-end-review.md`. Format and update rules: `postech-ai-helper/ai/canonical/memory.md`.

> Entries tagged **[in-flight from PR #N]** describe behaviour that lives on a feature branch not yet merged to `main`. They are kept here so the lesson survives across reviews; once the PR merges, drop the tag.

## Recent decisions

- 2026-04-29 - [in-flight from PR #117] Fix #83: ValueError em invariantes de dominio agora retorna **HTTP 422 VALOR_INVALIDO** via handler global em `error_handler.py`, em vez de cair no fallback 500 ERRO_INTERNO. Escolha consciente da abordagem handler-only (Solucao 5 do triage da issue) em vez de migrar 57 `raise ValueError` em 20 arquivos de `src/` para `ValorInvalidoException(DomainException)` -- mantemos intactos os 94 sites de teste com `pytest.raises(ValueError, ...)`. Trade-off: ValueError acidental (lib externa, bug interno) tambem vira 422 em vez de 500; ate aqui as mensagens de domain raise sao todas rotulos curtos sem PII (auditado via grep). Migrar para subclasse fica como tech-debt se o trade-off vazar
- 2026-04-29 - Read-side cross-context enrichment (resolver nomes a partir de IDs de outros bounded contexts) vive em `<contexto>/aplicacao/queries.py` via query handler que orquestra Ports em batch — NUNCA no router. CatalogoPort/EstoquePort ganharam `obter_servicos_em_lote(ids: set[UUID])` e `obter_itens_em_lote(ids: set[UUID])` que retornam `dict[UUID, DTO]`; adapters concretos short-circuitam em `set` vazio sem tocar a session. ItemDaOrdemDTO carrega `servico_nome`/`item_estoque_nome` opcionais (default None) preenchidos por `EnriquecerOrdemDeServico.executar(ordem_dto)` antes do mapping pra Pydantic. Pattern aplicavel a qualquer endpoint que precise hidratar IDs cross-context — issue #87
- 2026-04-29 - LGPD anonymization: VO `DocumentoAnonimizado(cliente_id: UUID)` substitui o patch tatico `numero="ANONIMIZADO"` em `CPF.__new__` (PR #78). Mapping reidrata como VO de primeira classe; `isinstance(doc, CPF/CNPJ)` volta a ser coerente para anonimizados. Tipo "anonimizado" adicionado a `_tipo_documento` helper em `aplicacao/use_cases.py`. Issue #79
- 2026-04-29 - ADR-014 (gerenciador de pacotes `uv`) promovida de Proposta para Aceita; uso na pratica ja consolidado em `Makefile`, `Dockerfile`, guias de setup e `docs/desenvolvimento.md`. Fallback `python -m venv` + `pip install` mantido apenas como contingencia -- issue #84
- 2026-04-29 - README raiz reorganizado: ponto de entrada com Quick Start canonico (`make reset-db`) + links curtos para detalhes; dev workflow movido para `docs/desenvolvimento.md`; troubleshooting cross-platform de Docker em `docs/setup/troubleshooting.md`. `ui/README.md` aponta para README raiz como "como rodar" e cobre apenas o que e especifico da UI -- elimina Quick Start duplicado entre raiz e ui/ -- issue #84
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

- 2026-04-29 - [in-flight from PR #117] Em macOS com Colima, testcontainers (suite de integracao) precisa de duas variaveis pra achar o socket: `DOCKER_HOST=unix:///Users/<user>/.colima/default/docker.sock` (o cliente docker) e `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (o path que o testcontainers passa pra dentro do ryuk container). Sem o override do socket, ryuk tenta montar o path literal do host (`.colima/default/...`) que nao existe dentro da VM e o teste falha com "operation not supported"
- 2026-04-29 - SQLAlchemy ORM imperative mapping: o evento `load` so dispara no PRIMEIRO carregamento de uma instancia. Apos `session.expire(obj)` + re-fetch na mesma sessao, o evento que dispara e `refresh` (assinatura diferente: `target, context, attrs`). Listeners que reidratam VOs precisam estar registrados em ambos — `cliente_veiculo/infraestrutura/mapping.py` ilustra o padrao com `_reidratar_documento` chamado por `_reconstruir_documento_on_load` e `_reconstruir_documento_on_refresh`. Sem o listener de refresh, `repository.anonimizar_dados` + `session.expire_all()` + `obter_por_id` retorna o documento ANTIGO em memoria
- 2026-04-26 - On Git Bash (MSYS2) absolute Unix-style paths (`/tmp/foo`) passed as args to native Windows binaries (e.g. `docker.exe`) are auto-translated to Windows paths (`C:/Users/.../Temp/foo`); the Makefile prefixes `MSYS_NO_PATHCONV=1` on `docker compose cp/exec` lines that pass `/tmp/...` to keep the path literal inside the container. Without it, `make seed-users-docker` and `make reset-db` fail with `No such file or directory: /app/C:/Users/...` from python in the container
- 2026-04-26 - The canonical workspace root is `~/git/fiap/postech-sw-architecture/` (per `postech-ai-helper/ai/canonical/workspace-structure.md`); cloning directly under `~/git/fiap/` still works for sibling-relative pointers, but the helper's `setup.sh` exits non-zero when run from a non-canonical workspace, and on Windows symlink creation requires Developer Mode regardless
- 2026-04-26 - On Windows, the project's Docker socket detection script must detect the named pipe (`\\.\pipe\docker_engine`) instead of probing only Unix sockets; the MINGW/MSYS/CYGWIN branch in `scripts/docker-check.sh` (added in PR #81) resolves this
- 2026-04-26 - Server-side render of NiceGUI `@ui.page` handlers runs before the client websocket connects; any handler-time HTTP call that writes to `app.storage.tab` raises `RuntimeError` unless the storage adapter is defensive (returns None and no-ops on writes when the backend is unreachable)

## Tech debt / TODO

- 2026-04-26 - LOW - HTTP probes during initial render of a NiceGUI page should be deferred to a `client.on_connect` handler (or equivalent) so they execute with a client context instead of as side effects of import/render
