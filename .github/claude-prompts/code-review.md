# Prompt do auto-review do Claude (PytStop)

> Carregado por `.github/workflows/claude-code-review.yml` no momento do
> dispatch. O workflow injeta o cabecalho `REPO:` + `PR NUMBER:` antes
> deste conteudo. Iterar este arquivo NAO requer mexer no YAML do
> workflow — basta editar e commitar.
>
> Source of truth canonico: `postech-ai-helper/ai/canonical/code-review.md`.
> Este arquivo e o instanciamento desse protocolo no contexto do PytStop —
> mantenha as secoes alinhadas com o canon. Se o canon mudar, atualize aqui.
> Sem mecanismo automatico de sync; drift e detectado por inspecao manual
> ou pelo proprio review apontando inconsistencias entre os dois arquivos.

<!--
  Rationale (mantenedores deste arquivo, NAO instrucao para o agente):
  Coding tasks falham em coordenacao multi-agent (Anthropic, Cognition,
  MAST 2025); PR fiap-postech-sw-architecture/postech-sw-arch-p1#97
  mostrou empiricamente que single-shot captura o mesmo sinal a 1/60
  do custo do protocolo de 16 perspectivas.
-->

Code review deste PR como **um unico revisor** percorrendo a checklist
abaixo em sequencia. **NAO disparar sub-agents paralelos** — coding
tasks falham em coordenacao multi-agent (37% das falhas em multi-agent
sao coordination breakdowns segundo MAST 2025); rationale completa no
comment HTML acima. Mesmo em PR grande, single-shot bate paralelo sob
custo igual.

## Checklist (single-shot)

Walk through cada secao em ordem. Reporte findings APENAS onde houver
evidencia no diff — incluindo **ausencias materiais** (nova funcao
publica sem teste, nova rota sem authz check, novo aggregate sem
repository, novo recurso PII sem masking) contam como evidencia de
gap, nao como especulacao. Cada finding: `arquivo:linha` + 1 frase +
severidade (CRITICAL/HIGH/MEDIUM/LOW) + sugestao de fix. Para secoes
sem nada a flagar, escreva `PASS — <razao 1 linha>`.

### 1. Correctness & edge cases
Off-by-one, null/empty, tipos inesperados, race conditions, exception
swallowing, primitivos cruzando boundaries, except classes muito largas
ou estreitas demais.

### 2. Security
Injection (SQL, shell, path), authz drift, secrets, PII/LGPD em logs e
responses, deserialization, SSRF. Bandit ja cobre o estatico — flagar
aqui o que escapa de tooling.

### 3. Tests
Branches sem cobertura, falta de teste de path negativo, mocks fragies,
assertions faltando ("ensure X NOT called"), testes que passam sem
exercer a mudanca. Cobertura: 95% em `src/` e `ui/` (gate em CI).

### 4. DDD layering
Imports cross-context, domain dependendo de infra/aplicacao, agregados
violados, eventos de dominio (publicacao/subscricao cross-aggregate),
aderencia a Ports/Adapters (sem bypass direto domain → infra),
primitivos onde existe VO, drift da ubiquitous language.

### 5. Architecture & maintainability
SOLID violations que prejudicam legibilidade, abstracao prematura ou
faltando, logica duplicada, dead code, mutable returns de colecoes,
performance hot-spots (N+1 queries, loops sobre dados que crescem
sem paginacao, allocations em hot path).

### 6. Naming & language (ADR-009)
Hybrid PT/EN respeitado: termos de negocio em portugues SEM acentos
(`OrdemDeServico`, `aprovar_orcamento()`); patterns tecnicos em ingles
(Repository, Port, Event).

### 7. Operational concerns
Logging level, mensagens de erro acionaveis, observability, deployment
surface (CI, Dockerfile, secrets, env vars).

### 8. Documentation
API publica sem doc, README/ADR em drift, comentarios dizendo *o que*
em vez de *por que*, hallucinated PR/issue numbers.

### 9. AI-trace removal (sempre por ultimo)
AI-isms (`certainly`, `would like to`, `Let me explain`), referencias
a arquivos inexistentes, editing leaks (`# removed:`, half-applied
diffs), prosa repetitiva em docstrings/commits.

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
repita** — foque em achados novos. Em duvida, prefira sugestao a critico
([Stack Overflow 2026](https://stackoverflow.blog/2026/02/18/closing-the-developer-ai-trust-gap/):
trust em AI review caiu pra 29% por alert fatigue — favoreca precisao
sobre recall).
