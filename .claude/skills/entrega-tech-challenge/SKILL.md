---
name: entrega-tech-challenge
description: >-
  Produz a entrega de uma fase do Tech Challenge da FIAP Pos Tech com qualidade
  de nota 10: orquestra o review multi-perspectiva (18 perspectivas em
  sub-agentes), resolve todas as findings, gera o PDF de submissao (links
  absolutos + Mermaid via pandoc/weasyprint) e roda o checklist de submissao.
  Use SEMPRE que o usuario pedir para "preparar/fechar a entrega da fase N",
  "review nota 10", "rodar as perspectivas", "review completo com multiplas
  perspectivas", "gerar/regenerar o PDF da entrega", "documento de entrega",
  "submeter no portal", ou ao revisar specs/ADRs/RFC/PR de uma fase do desafio.
  Aplica-se a qualquer fase (1, 2, 3, 4, hackathon), mesmo sem dizer "skill".
---

# Entrega Tech Challenge (FIAP Pos Tech) — processo nota 10

Esta skill captura o passo-a-passo que levou a entrega da fase 1 a nota 10 e foi
refinado na fase 2. Duas partes: **(A) o review multi-perspectiva** (a "formula
do 10") e **(B) a geracao do PDF de submissao**. Mais um arquivo de **idas e
voltas** com os tropecos reais ja vividos — leia ANTES de comecar para nao
repeti-los.

Recursos da skill:
- `references/protocolo-perspective-review.md` — o protocolo exato (18 perspectivas).
- `references/perspectives-index.md` — indice das 18 perspectivas.
- `references/perspectives/NN-*.md` — o prompt/checklist de CADA perspectiva (1 por sub-agente).
- `references/formula-nota-10.md` — a barra de qualidade do 10 + como as perspectivas a cobrem.
- `references/idas-e-voltas.md` — **gotchas a antecipar e evitar** (git/PR, PDF, CI/review, infra).
- `references/code-review-canonico.md` — alternativa single-shot+Judge (para code review do dia-a-dia, quando 18 perspectivas e exagero).
- `scripts/gerar_pdf_entrega.py` — gera o PDF de submissao.
- `assets/exemplos/fase1/`, `assets/exemplos/fase2/` — pacotes de entrega REAIS
  (a fase 1 tirou 10) como template a espelhar: `entrega-fase-N.md`,
  `roteiro-video.md`, `documento-aprovacao-solucao.md`, `apendice-*.md`, assets.
  Inclui `documento-entrega-fase-{1,2}.pdf` como referencia visual de "como fica
  um 10" (a fase 1 e a baseline da nota maxima).

## Antes de tudo

Leia `references/idas-e-voltas.md`. A maioria do tempo perdido nas fases
anteriores veio de ~10 armadilhas conhecidas (squash colapsando historico,
`allow_merge_commit=false`, transferencia de repo que nao leva secrets, pandoc
nao renderizando Mermaid, token do review invalido, RTK filtrando `grep`, etc.).
Antecipa-las e o maior ganho desta skill.

## Parte A — Review multi-perspectiva (a formula do 10)

Quando: ao fechar qualquer artefato significativo da entrega (spec, ADR, RFC,
modulo de codigo, diff de PR, e o proprio documento de entrega).

O protocolo completo esta em `references/protocolo-perspective-review.md`. Resumo
operacional:

0. **Escolha o NIVEL primeiro** (custo × momento — detalhe no protocolo):
   - **rapido** (default, diffs e docs do dia-a-dia): single-shot + Judge
     (`references/code-review-canonico.md`); doc-only = secoes 8+9. SEM
     sub-agente por perspectiva.
   - **deep** (artefato significativo em iteracao): 4–6 lentes AGRUPADAS por
     tipo de artefato + Judge + #17→#18→#17.
   - **campeao** (1× por artefato de entrega, no fechamento — onde o 10 e
     decidido): o conjunto APLICAVEL das 16 + extras do tipo de artefato
     (trabalho academico: professor-com-rubrica + escrita PT-BR) + Judge +
     #17→#18→#17. Nao relancar campeao a cada retoque: retoques usam deep.
1. **Paralelo (finders):** lance os sub-agentes do nivel escolhido — SO as
   perspectivas cujo checklist nao seria majoritariamente N/A para o artefato
   (lentes de codigo nao rodam em documento). Cada um recebe **apenas** o seu
   arquivo `references/perspectives/NN-*.md` + o artefato em revisao + o
   spec/enunciado da fase + glossario — nunca o historico da sessao.
   - Finders rodam em **modelo barato** (classe Sonnet); recall e o trabalho
     deles, precisao vem do Judge e da triagem. Findings em 1 linha:
     `[SEVERIDADE] linha — problema → correcao`.
   - Use o Agent tool com varios sub-agentes no mesmo turno (rodam concorrentes).
   - Cada perspectiva termina num **Checklist obrigatorio**: o sub-agente so
     retorna PASS depois de verificar cada item, citando `file:line` em cada
     violacao. Se nao se aplica: `PASS — N/A (motivo)`.
2. **Judge + triagem:** aplique o filtro Judge do canonico (derruba finding que
   repete tradeoff aceito no MEMORY, duplicata <MEDIUM, ou especulativo sem
   linha/simbolo citado). Cada sobrevivente e **aplicado** ou **rejeitado com
   justificativa de 1 linha** — nenhum e silenciosamente ignorado. Formato:
   `REJECTED [Perspectiva N]: <finding> — Motivo: <razao>`. Conflitos entre
   perspectivas: vence o que serve melhor o plano; documente.
3. **Sequencial #17 → #18 → verificacao** (no modelo da sessao, nao no barato):
   rode AI-Trace Removal (#17) sozinho no resultado acumulado; depois Human
   Reader (#18) com a restricao "suas reescritas devem obedecer o checklist do
   #17"; depois verifique as edicoes do #18 com `scripts/lint_ai_trace.py` +
   auto-checagem do checklist SO no diff. Agente #17 completo de novo APENAS se
   o linter acusar, o self-check achar algo, ou o #18 tiver reescrito >20% das
   linhas (racional e fontes no protocolo). **Nunca pule o #17 (S1)** — e o que
   remove "cara de IA" do texto (decisivo no 10 de docs).
4. **Copilot Gap Analysis (apos push do PR):** para cada finding do Copilot,
   mapeie a perspectiva que deveria ter pego, registre, e se 3+ findings caem na
   mesma perspectiva, reforce o checklist dela.

Para **code review**: cada sub-agente recebe o diff + contexto do arquivo + ADRs/RFC;
ao fim do #17→#18→#17, re-rode `ruff check`, `ruff format --check`, `mypy src/`,
`bandit -r src/` e `pytest`. **Coverage e testes de integracao TEM que ficar
verdes** — ver idas-e-voltas.

> Atalho: para diffs pequenos do dia-a-dia, `references/code-review-canonico.md`
> (single-shot 9 secoes + Judge) captura o mesmo achado-ancora a uma fracao do
> custo. As 18 perspectivas sao para a entrega/artefatos grandes — onde o 10 e
> decidido.

## Parte B — Gerar o PDF de submissao

Pre-requisitos: `pandoc`, `weasyprint`, `npx` (mermaid-cli on-demand), `python3`.

1. Ache o markdown: normalmente `docs/entrega/faseN/entrega-fase-N.md`
   (`ls docs/entrega/*/entrega-*.md`).
2. **Cheque o link do video** antes de gerar — `grep -rn "VIDEO-LINK" docs/entrega/faseN/`.
   Se ainda houver placeholder, avise: falta colar o link do video (e confirmar
   o link do repo + colaborador `soat-architecture`) antes de submeter.
3. Rode, da raiz do repo da fase:
   ```bash
   python ~/.claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py \
     docs/entrega/faseN/entrega-fase-N.md
   ```
   - Auto-detecta `owner/repo` (gh → git remote). **Se o repo foi transferido de
     org, confira o owner** (`--repo owner-novo/repo`) — senao os links do PDF
     apontam pro antigo. `--output` escolhe o destino; `--branch` (default main).
4. Confira: diagrama saiu como imagem (nao bloco de codigo) e links abrem no
   GitHub. O script nao toca o markdown fonte; o PDF sai fora do repo.

## Parte C — Checklist de submissao (os 3 itens do enunciado)

- [ ] Repo **privado** compartilhado com `soat-architecture` (acao outward-facing — confirme com o usuario; `gh api -X PUT repos/OWNER/REPO/collaborators/soat-architecture -f permission=pull`).
- [ ] **Desenho da arquitetura** no documento (Mermaid renderizado no PDF).
- [ ] **Link do video** (YouTube/Vimeo, ate 15min, publico ou nao listado) preenchido nos marcadores e no PDF.
- [ ] Rastreabilidade: todo requisito do enunciado mapeado a RF/RNF/RN → PR → evidencia (ver `references/formula-nota-10.md`).
- [ ] Coverage no gate e testes (unit + integracao + E2E) verdes; scans de seguranca limpos.
- [ ] PDF regenerado APOS o ultimo edit/preenchimento do video.

Detalhes da barra de qualidade do 10 em `references/formula-nota-10.md`.
