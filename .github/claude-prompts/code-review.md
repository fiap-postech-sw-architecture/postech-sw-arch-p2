# Prompt do auto-review do Claude (PytStop)

> Carregado por `.github/workflows/claude-code-review.yml` no momento do
> dispatch. O workflow injeta o cabecalho `REPO:` + `PR NUMBER:` antes
> deste conteudo. Iterar este arquivo NAO requer mexer no YAML do
> workflow — basta editar e commitar.

Code review deste PR seguindo as convencoes do PytStop.

## Estrategia de exploracao

Use Task tool pra paralelizar quando o PR for grande.

Se o PR mexe em mais de ~10 arquivos, dispare ate 4 sub-agents em
**PARALELO** via Task tool, cada um com foco unico:

- **subagent A — SEGURANCA**: JWT/auth, LGPD/PII em logs e responses,
  secrets, header leak, validacao de input.
- **subagent B — DDD/ARQUITETURA**: agregados, eventos, cross-context
  imports, aderencia a Ports/Adapters, violacoes de bounded context.
- **subagent C — BUGS/PERFORMANCE**: edge cases, race conditions, N+1
  queries, loops sobre dados que crescem, off-by-one.
- **subagent D — TESTES**: cobertura dos paths novos, qualidade dos
  casos (edge cases reais ou trivials), regressoes pinadas.

Cada sub-agent retorna um relato de 200-400 palavras com findings
citados como `arquivo:linha`. Voce (main agent) consolida em UM unico
review estruturado.

Se o PR for pequeno (<=10 arquivos), revise inline sem sub-agents.

## Convencoes do projeto

Ver `.claude/CLAUDE.md` na raiz do repo.

- **Hybrid PT/EN**: termos de negocio em portugues SEM acentos
  (ex.: `OrdemDeServico`, `aprovar_orcamento()`); patterns tecnicos
  em ingles (`Repository`, `Port`, `Event`).
- **DDD com bounded contexts isolados via Ports/Adapters**.
- **Cobertura: 95%** no `src/` e em `ui/` (gate em CI).

## OBRIGATORIO — como publicar o review

Sem isso o output nao chega no PR. O Claude tem essas tools no allowlist
(`mcp__github_inline_comment__create_inline_comment`, `Bash(gh pr comment:*)`).

- **Achados pontuais em linha especifica do diff**: use
  `mcp__github_inline_comment__create_inline_comment` com
  `confirmed: true`.
- **Resumo final com a estrutura abaixo**: poste via
  `gh pr comment <PR_NUMBER> --body "..."`.
- **NAO devolva** o review como mensagem de chat — somente comments do
  GitHub contam.

## Formato obrigatorio do comment de resumo

- 🔴 **Criticos** (bloqueiam merge) — `arquivo:linha` em cada
- 🟡 **Sugestoes** (nao-bloqueantes) — `arquivo:linha` em cada
- 🟢 **Pontos fortes**
- 📋 **Resumo** (1-2 paragrafos)

Threads ja resolvidos por outro reviewer (Copilot, humano): **nao
repita** — foque em achados novos. Em duvida, marque como sugestao em
vez de critico.
