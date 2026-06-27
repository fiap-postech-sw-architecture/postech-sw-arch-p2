# Idas e voltas a antecipar (e evitar)

Tropecos reais das fases 1 e 2. Cada um custou tempo; ler isto ANTES economiza
retrabalho. Formato: **sintoma → causa → o que fazer de cara**.

## Git / PR / histórico

1. **Squash colapsa o histórico empilhado.** Em PRs empilhados (stacked) ou que
   carregam histórico (ex.: seed de fase anterior), "Squash and merge" joga fora
   os commits. → Use **merge commit**, nunca squash, nesses PRs.
2. **`allow_merge_commit` vem `false` em repo novo** (só aparece "Squash and
   merge"). → No começo: `gh api -X PATCH repos/OWNER/REPO -F allow_merge_commit=true`.
   Confirme antes de abrir a cadeia de PRs.
3. **Histórico da fase anterior no repo novo:** `git merge -s ours` incorpora o
   histórico sem mudar a árvore (tree idêntica). Force-push em `main` protegida é
   bloqueado (**GH006**) — vá por PR.
4. **PRs empilhados re-squashados** ao mergear a cadeia: re-reconstrua as
   branches restantes com cherry-pick na main atualizada + push.
5. **`git cherry-pick -q` falha (exit 129):** flag inválida; use `>/dev/null`.
6. **Sem auto-merge sem autorização:** o usuário revisa cada PR. Não use
   `gh pr merge --auto` salvo autorização explícita na sessão.

## Transferência de repo / org

7. **Transfer do GitHub NÃO leva secrets.** Após mover pro org, todo secret
   (`CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, etc.) some → reconfigurar.
8. **Refs hardcoded do owner antigo** quebram: clone URL, badges, links de PR/run,
   path de imagem GHCR (`ghcr.io/OWNER/...`), `--repo` do script de PDF. → `git grep`
   o owner antigo e reescrever. `cd.yml` que usa `${GITHUB_REPOSITORY}` se
   auto-resolve (não mexer); imagens da FASE ANTERIOR seguem sob o owner antigo
   (intencional — não reescrever essas).
9. **Remote local** continua no owner antigo: `git remote set-url origin <novo>`.
10. **Runs antigos** resolvem na URL nova (transfer preserva Actions) — pode
    reescrever links de run com segurança.

## PDF de entrega

11. **pandoc NÃO renderiza Mermaid.** Sem renderizar o bloco pra PNG antes, o
    diagrama sai como bloco de código no PDF. → `scripts/gerar_pdf_entrega.py` já
    faz (mermaid-cli). Garanta `npx` no PATH.
12. **Links relativos não abrem no PDF** → reescrever pra URL absoluta do GitHub
    (`blob/<branch>`). O owner certo importa (ver #8).
13. **Regenerar SEMPRE** após qualquer edição no markdown ou após colar o link do
    vídeo — o PDF não se atualiza sozinho.
14. **Warnings do weasyprint** (`@media`, `text-rendering`, `overflow-x`) são
    inócuos; o PDF sai mesmo assim.

## Code review do Claude (claude-code-action)

15. **`401 Invalid bearer token`:** o token no secret está inválido/errado. Tem
    que ser OAuth `sk-ant-oat01-...` (de `claude setup-token`, plano Pro/Max),
    **não** API key `sk-ant-api...`. Valide com curl (`Authorization: Bearer`,
    header `anthropic-beta: oauth-2025-04-20`, system começando com "You are
    Claude Code, Anthropic's official CLI for Claude.") — 401 = token ruim,
    200/400 = token ok (problema é o valor gravado).
16. **Regra mudou em 15/jun/2026:** uso da Action sai do **crédito mensal de
    Agent SDK** do plano (Max 5x $100, Max 20x $200), não do pool do chat. Max +
    OAuth funciona, sem API key.
17. **`track_progress` não suporta `workflow_dispatch`** → o botão "Run workflow"
    do on-demand falha. Teste via **PR** ou comentário `@claude`.
18. **A action NÃO propaga `is_error` pro exit code** (track_progress) → review
    quebrado fica verde sem revisar. → Adicione um step que lê
    `claude-execution-output.json` e falha em `is_error` (gate honesto).
19. **Modelo do review:** default era Sonnet; para a entrega use o **melhor
    Opus** (`claude-opus-4-8`). Composite valida o nome no whitelist.
20. **Secret é por-repo e não transfere** (ver #7): `gh secret set CLAUDE_CODE_OAUTH_TOKEN -R OWNER/REPO`.

## Ferramentas / ambiente

21. **RTK filtra a saída do `grep`** (mostra "0 matches in 0 files"). → Use a
    ferramenta Read, `git grep`, scan em python, ou `grep -l`/`-c` (flags raw).
22. **`api.github.com` intermitente** atrás de proxy/VPN (DNS reescrito) →
    `gh pr create`/`gh api` dão timeout; git SSH funciona. Retestar quando a rede
    mudar.
23. **`cp`/`rm` têm alias `-i`** (interativo). → `/bin/cp`, `/bin/rm`, ou
    `cat src > dest`.
24. **Docker/colima parado:** o E2E completo local precisa de colima ~4GiB
    (`colima start --memory 4`). Se indisponível, valide no CI (runner tem Docker).

## Gates de qualidade (não negociar)

25. **Coverage no gate + integração TÊM que ficar verdes** a cada mudança. O
    job `test` roda unit (cov ≥95% src, ≥95% ui) + integração + (no full-test-ci)
    o plano E2E completo. Mudança em docs/CI não toca src → não afeta cobertura.
26. **Rodar os dois planos do full-test juntos colide documentos** (mesmo seed →
    CPF duplicado, 409). `plano_full` é superset → rode só `-m slowest`.
27. **tech-debt/README.md estala:** ao resolver um débito, mova-o pra "Itens Resolvidos"
    e cruze com a issue. Itens já feitos (ex.: CSP, PII em traces) podem estar
    listados como abertos — confira antes de "implementar de novo".

## Submissão

28. **`soat-architecture` como colaborador** é ação outward-facing — confirme com
    o usuário; não convide sozinho.
29. **Os 3 itens do PDF** (link do repo compartilhado, diagrama, link do vídeo)
    são exigência do enunciado — o PDF sem o vídeo preenchido é inútil.
