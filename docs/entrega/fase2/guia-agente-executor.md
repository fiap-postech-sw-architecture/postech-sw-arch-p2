# Guia do agente executor — finalização da fase 2

> [↑ Raiz do projeto](../../../README.md) · [↑ Pai](README.md)

Você é um agente de codificação executando o [finalization-plan.md](finalization-plan.md) (issue índice [#128](https://github.com/fiap-postech-sw-architecture/postech-sw-arch-p2/issues/128)). Este guia é autossuficiente: siga-o na ordem, sem improvisar fora dele. Cada PR tem especificação própria na seção 5; em dúvida entre o guia e uma issue, a issue vence (é mais recente e mais específica).

## 1. Setup e leitura obrigatória (nesta ordem)

1. `postech-ai-helper/ai/agent-bootstrap.md` (workspace root `~/git/fiap/postech-sw-architecture/`) — protocolo de sessão
2. `postech-ai-helper/ai/canonical/commit-workflow.md` e `code-review.md` — como commitar e revisar
3. `MEMORY.md` na raiz deste repo — gotchas acumulados (leitura completa; economiza horas)
4. [finalization-plan.md](finalization-plan.md) — o plano que você executa
5. A issue do PR da vez — especificação de detalhe

Confirme o ambiente antes do primeiro PR: `cd ~/git/fiap/postech-sw-architecture/postech-sw-arch-p2 && git checkout main && git pull && make test` (baseline verde esperado; se vermelho, PARE e reporte).

## 2. Regras invioláveis

1. **Um PR por linha da tabela do plano.** Branch a partir de `main` atualizada: `git checkout -b <tipo>/<issue>-<slug>` (ex.: `fix/117-populate-existing`).
2. **TDD nos PRs de código**: escreva o teste que FALHA provando o bug (red) → fix → green. O teste red é evidência; cite-o na descrição do PR.
3. **Gates locais antes de cada commit** (todos, sem exceção):
   ```bash
   uv lock --check
   make lint          # ruff check + ruff format --check (o alvo roda os dois; formato NAO escapa)
   make lint-arch     # import-linter (contratos de camada)
   make typecheck     # mypy strict
   make security      # bandit (0 High)
   make test          # unit + cobertura ≥95 (src e ui)
   make test-integ    # integração (precisa Docker/colima — seção 6)
   CODEQL_DIR=$HOME/codeql-tools make codeql-quality   # 0 findings ativos
   ```
4. **Commits**: assunto ≤72 chars com prefixo convencional; corpo só quando o porquê não é óbvio; **NUNCA** trailer `Co-Authored-By`/`Signed-off-by`.
5. **Code review pré-commit** (canonical `code-review.md`): single-shot 9 seções + Judge no diff; doc-only = seções 8+9. Aplicar ou rejeitar cada finding com 1 linha — nada ignorado em silêncio.
6. **Push + PR**: `gh pr create` com resumo + test plan + `Closes #N`. **NUNCA `gh pr merge --auto`** — o usuário revisa e mergeia cada PR manualmente. Sua entrega termina no PR aberto + comentário de status.
7. **Idioma (ADR-009)**: identificadores de domínio em PT sem acento; padrões técnicos em EN; docs em PT com acento.
8. **Nunca**: commitar direto na `main`; mexer no PR #55 (decisão do usuário); convidar colaboradores; `git add -A` (sempre `git add <paths>` explícito); tocar em arquivos fora do escopo do PR da vez.
9. **Task-end**: atualize o `MEMORY.md` do repo (add-only, topo da seção) com gotchas/decisões novas do PR, no mesmo commit.

## 3. Fluxo por PR (repita para cada linha da tabela)

```
main atualizada → branch → ler a issue → escrever teste red → fix mínimo →
gates (regra 3) → code review no diff → MEMORY.md se houver aprendizado →
git add <paths> → commit → push → gh pr create (Closes #N) →
comentar na issue: "PR #X aberto" → PARAR (não mergear) → próxima linha
```

Se um gate quebrar por causa alheia ao seu diff: pare, reporte no PR/issue, não "conserte" fora do escopo.

## 4. Gotchas do ambiente (destilados do MEMORY.md — leia a fonte)

- **RTK**: hook reescreve comandos bash com prefixo `rtk`. O filtro do rtk QUEBRA a saída de `grep` cru ("0 matches" falso). Use a ferramenta Grep do harness, `git grep`, ou flags raw (`-l`/`-c`). Comando longo em background: `rtk proxy <cmd>` (rtk bufferiza stdout).
- **`rm`/`cp` têm alias `-i`** — use `/bin/rm`, `/bin/cp` ou `cat src > dest`.
- **Testcontainers (macOS+colima)**: `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` + `TESTCONTAINERS_RYUK_DISABLED=true` (ou `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`). Colima com 4GiB para stack completa (`colima start --memory 4`).
- **pip-audit**: `uv run --with pip-audit pip-audit`. `uvx pip-audit` audita o venv do uvx (inútil).
- **CodeQL**: o repo usa **default setup** do GitHub — NÃO crie `.github/workflows/codeql.yml` (conflita; erro "Advanced Security must be enabled" é enganoso). Gate local: `make codeql-quality`.
- **`make security`** bloqueia só High; Low aceitos documentados. `# nosec BXXX` sozinho na linha; razão em comentário SEPARADO acima (prosa após o código vira "Test in comment").
- **structlog**: `capture_logs` não intercepta logger module-level já cacheado (`cache_logger_on_first_use`) — monkeypatch do `_log` do módulo em fixture autouse (ver `test_notificacoes.py`).
- **Mapping imperativo**: `select(Classe)` exige `iniciar_mapeamentos()` registrado — fixture autouse nos arquivos de teste que montam select (padrão em `test_adapters.py`/`test_repository_estoque.py`). Não dependa da ordem de coleta.
- **Logs INFO de src/ não aparecem** no stdout do container (root logger em WARNING) — valide por efeito observável, não por log info.
- **Fixtures pytest** que fazem `yield` de valor não podem ter prefixo `_` (ruff PT019).
- **Integração comita de verdade?** Só o padrão dos testes de relay/concorrência (conexões próprias + cleanup escopado por id no `finally`). O resto usa a fixture `session` com savepoint — não misture.

## 5. Especificações por PR

### PR A — #117 `populate_existing` (comece por este)
- Alvos: `src/ordem_servico/infraestrutura/repository.py` (branch `com_lock`), `src/estoque/infraestrutura/repository.py` (idem).
- Mudança: `.execution_options(populate_existing=True)` no `select(...).with_for_update(...)` dos dois.
- Teste red (integração, padrão `tests/integracao/ordem_servico/test_concorrencia_lock.py`): session A carrega a entidade; conexão B (própria, commit real) altera a linha; A relê `com_lock=True` → DEVE ver o valor novo. Sem o fix, vê o stale.
- Unit: statement do branch `com_lock` carrega `populate_existing` (inspecionar `_execution_options`).
- Commit sugerido: `fix(concorrencia): populate_existing no branch com_lock — releitura fresca sob FOR UPDATE (#117)`

### PR B — #111 + #122 reversão do complementar (o maior; ler as DUAS issues + comentário de causa raiz)
- Alvos: `src/ordem_servico/dominio/ordem_de_servico.py`, `item_da_ordem.py`, `aplicacao/use_cases.py` (`RejeitarOrcamentoComplementar`), mapping se novo campo persistir.
- Semântica: `gerar_orcamento_complementar` snapshota o orçamento aprovado e marca os itens pós-aprovação; `rejeitar` restaura snapshot + remove itens marcados + **libera as reservas** (`estoque_port.liberar`) na mesma UoW; `finalizar_servico` ganha guard de cobertura (#122 — confirmar por teste red ANTES).
- Atenção: `AGUARDANDO_APROVACAO_COMPLEMENTAR` → rejeição volta a `EM_EXECUCAO` (rejeição parcial admin) vs recusa externa cancela tudo (RF-022) — NÃO mudar essa distinção.
- Testes: ampliar `test_fluxo_rejeitar` com asserts de orçamento/itens/reserva; e2e do ciclo completo; casos: rejeitar sem itens novos, rejeitar com N itens, finalizar com pendência → erro.
- Commit: `fix(ordem-servico): rejeicao do complementar reverte orcamento, itens e reservas (#111, #122)`

### PR C — #118 + #121 sessão de auth
- Alvos: `src/autenticacao/aplicacao/use_cases.py` (Logout), `interfaces/router.py`, `infraestrutura/token_revogado_repository.py`, schemas.
- #118: escolher opção da issue (A: refresh opcional no body do logout; B: claim `sid`). A opção A é menor e não muda tokens existentes — preferir A salvo objeção na issue.
- #121: `revogar` idempotente (`esta_revogado` antes ou `ON CONFLICT DO NOTHING`) → 2º logout 200.
- Testes red: refresh pós-logout 200 (deve virar 401); logout duplo 500 (deve virar 200).
- OpenAPI/schemas atualizados se o contrato mudar; collection só no PR F.
- Commit: `fix(auth): logout revoga refresh e vira idempotente (#118, #121)`

### PR D — #119 guard pós-lock (depois do A)
- Alvo: `src/ordem_servico/aplicacao/use_cases.py` (`DecidirOrcamento`, caminho `recusada`).
- Mudança: revalidar estados de espera DENTRO da tx com lock (2ª leitura), espelhando o teste `test_guard_le_sem_lock_e_delegada_le_com_lock`.
- Teste: integração de corrida — aprovação interna concorrente vence; recusa externa conflita (409), OS segue EM_EXECUCAO, 1 evento só.
- Commit: `fix(concorrencia): recusa externa revalida espera sob lock (#119)`

### PR E — #120 peça inativa
- Alvos: `src/ordem_servico/aplicacao/ports.py` (`ItemEstoqueDTO.ativo`), adapter de estoque em `ordem_servico/infraestrutura/adapters.py`, `_montar_item` em `use_cases.py`, `src/estoque/dominio/item_estoque.py` (`reservar` defensivo).
- Testes red: montar item com peça inativa → erro de domínio; e2e 422/409 (não 500); reservar inativo → exceção.
- Commit: `fix(estoque): peca desativada nao entra em OS nem reserva (#120)`

### PR F — #113 collection Postman
- Regenerar da stack viva: `make up` → `curl -s http://localhost:8000/openapi.json > openapi.json` → `npx -y openapi-to-postmanv2 -s openapi.json -p -O folderStrategy=Tags` → substituir `docs/entrega/fase2/postman_collection.json`.
- Adicionar pre-request script HMAC no request `decisao-orcamento` (assinatura `X-Webhook-Signature` + `X-Webhook-Timestamp`, algoritmo em `src/compartilhado/infraestrutura/webhook_signature.py` — HMAC-SHA256 de `{ordem_id}.{timestamp}.` + body, chave `ORCAMENTO_WEBHOOK_TOKEN`).
- Conferir 48 rotas presentes (incl. `GET /api/v1/admin/outbox/dead` e `POST .../reenfileirar`); variáveis `base_url`/token.
- Validar com runner do Postman/newman contra a stack local; anexar evidência no PR.
- Commit: `docs(entrega): collection regenerada com HMAC e endpoints admin (#113)`

### PR G — #124 segurança de fechamento
- Rodar na HEAD final: bandit (targets do pyproject já incluem relay/scripts), `uv run --with pip-audit pip-audit`, gitleaks, trivy. SonarQube manual (`sonar-project.properties`) + screenshot Quality Gate.
- Atualizar `docs/seguranca/scan-fase-2.md` → v1.1 (datas, resultados, sem a ressalva de cobertura); nova seção "Segurança na fase 2" em `entrega-fase-2.md` com tabela-resumo + links; justificativa de cobertura (95,34% atual vs 97,75% fase 1: o gate passou a cobrir src+ui+relay) no RNF-018 e README.
- Commit: `docs(seguranca): scans da HEAD final + sonar de fechamento + secao na entrega (#124)`

### PR H — #125 apêndice de extras
- Criar `docs/entrega/fase2/apendice-funcionalidades-extras.md` no formato da fase 1 (feature | onde vive | PR | motivação), ≥15 entradas do inventário da issue; linkar de `entrega-fase-2.md`.
- Commit: `docs(entrega): apendice de funcionalidades extras da fase 2 (#125)`

### PR I — #93 roteiro
- `docs/entrega/fase2/roteiro-video.md`: bloco 6 ganha beat Prometheus (port-forward 9090 + query de profundidade da outbox); bloco 1 nomeia relay/redis/prometheus; encerramento cita security.yml/CodeQL/DAST; bump de versão; manter ≤15min somados.
- Commit: `docs(roteiro): prometheus no bloco 6 + workloads e seguranca sincronizados (#93)`

### PR J — housekeeping #90 #95 #96 (+ import do PR #55)
- #90: README "Python 3.12" → 3.14 (1 linha). #95: denylist do `scripts/seed_admin.py` inclui o valor demo público (`k8s/secret.yaml:31`). #96: remover `default="admin"` da coluna `papel` em `src/autenticacao/infraestrutura/mapping.py` (o `before_insert` sempre seta do `_papel` explícito — confirmar teste). Import misto em `tests/unitarios/ordem_servico/test_repository_os.py:13` → estilo único (finding CodeQL do PR #55, reimplementado limpo).
- Testes: suíte cheia (o #96 pode ter teste afirmando o default — ajustar mantendo fail-safe).
- Commit: `chore: housekeeping da entrega — python 3.14, seed denylist, papel sem default, import unico (#90, #95, #96)`

### PR K — #123 pipeline do PDF (depois de G e H)
- `scripts/build-entrega-pdf.sh`: pré-pendar capa ABNT (FIAP · 15SOAT · nomes completos + RM · São Paulo · 2026 — copiar dados da capa da fase 1 nos assets da skill `entrega-tech-challenge`); concatenar Anexo A (scan-fase-2.md v1.1), Anexo B (screenshots de evidência em `docs/entrega/fase2/assets/`), Anexo C (apêndice de extras); filtrar a §8 Pendências do corpo.
- Validar: gerar PDF de teste e conferir capa/anexos/diagrama-imagem/links/ausência da §8.
- Commit: `build(entrega): pdf com capa ABNT, anexos A-C e filtro de pendencias (#123)`

### PR L — #99 #126 #127 (P2, opcional pré-entrega)
- #99: `_TELEFONE_PATTERN` aceita forma sem espaço pós-DDD (cuidado com falso-positivos — os 5 casos negativos do teste existente DEVEM continuar passando). #126: varredura de `raise ValueError` + teste guard. #127: fixture autouse resetando `EncryptionService._instance`.
- Commit: `fix(qualidade): scrubber fone sem espaco, guard 422, reset do EncryptionService (#99, #126, #127)`

## 6. Ambiente de integração

`make test-integ` exige Docker: `colima start --memory 4` + as env vars da seção 4. Sem Docker local, rode unit + gates e marque no PR que a integração precisa do CI — NÃO pule silenciosamente.

## 7. PDF final e submissão (executar só quando o usuário der o vídeo)

Siga a seção 6 do [finalization-plan.md](finalization-plan.md). Nunca gere o PDF de submissão com o marcador `VIDEO-LINK-FASE-2` vazio; nunca convide `soat-architecture` você mesmo — apenas verifique (`gh api repos/fiap-postech-sw-architecture/postech-sw-arch-p2/collaborators/soat-architecture` → 204 = ok, 404 = pendente) e reporte.

> [↑ Raiz do projeto](../../../README.md) · [↑ Pai](README.md)
