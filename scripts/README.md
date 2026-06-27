# Scripts

> [↑ Raiz do projeto](../README.md)

Scripts de build, conversão de artefatos e lints da entrega da Fase 1.

## lint-doc-anchors.sh

Verifica que todo doc tem o breadcrumb padronizado (`> [↑ Raiz do projeto](...)` no topo e como última linha não-vazia). `README.md` e `CONTRIBUTING.md` na raiz são pulados.

```bash
bash scripts/lint-doc-anchors.sh README.md docs/entrega/*.md
```

Exit 0 se todos passarem; exit 1 e lista de violações em stderr caso contrário. Sem args, imprime uso e sai 1.

## rewrite-md-links.py

Reescreve links relativos em markdown para URLs absolutas no GitHub (branch alvo). Usado para gerar o PDF da entrega autocontido (links resolvem mesmo fora do repo). Externos (`https://`, `mailto:`, anchors) passam direto.

```bash
python scripts/rewrite-md-links.py docs/entrega/fase2/entrega-fase-2.md /tmp/absolute.md \
  --repo fiap-postech-sw-architecture/postech-sw-arch-p2 \
  --branch main \
  --base-dir docs/entrega/fase2
```

Stdlib-only. Útil para qualquer doc com links relativos que precise virar um artefato autocontido. O documento de entrega já carrega URLs absolutas para `main` e dispensa este passo.

## export-egn-to-svg.js

Converte diagramas [egon.io](https://egon.io) (`.egn`) para SVG usando Puppeteer (headless Chrome). Usado na entrega da Fase 1 para incluir os diagramas Domain Storytelling no PDF.

### Pré-requisitos

- Node.js 18+
- Puppeteer: `npm install puppeteer`

O Puppeteer baixa automaticamente uma versão do Chromium (várias centenas de MB).

### Uso

```bash
# Padrão: lê de docs/arquitetura/domain-storytelling/, salva em docs/entrega/assets/
node scripts/export-egn-to-svg.js

# Diretórios customizados
node scripts/export-egn-to-svg.js --egn-dir path/to/egn --out-dir path/to/output
```

O script encerra com código 1 se o diretório ou arquivos `.egn` não existirem.

### Como funciona

Abre o egon.io em headless Chrome, carrega cada `.egn` pelo input de upload e extrai o SVG do DOM. Se a extração falhar, salva um screenshot PNG como fallback.

### Saída

Gera um `.svg` (ou `.png` em fallback) por `.egn` no diretório de saída, com o mesmo nome base.

### Alternativa manual

Se Puppeteer não estiver disponível, abrir cada `.egn` em https://egon.io, File → Export → SVG, salvar em `docs/entrega/assets/`.

## codeql_quality.sh

Roda o **CodeQL "Code Quality" suite** localmente — as mesmas queries que o GitHub Code Quality (preview) usa. Útil para reproduzir e triar os findings sem a UI do GitHub: o report de Code Quality não tem API pública, e o endpoint de code scanning exige GitHub Advanced Security (indisponível no repo privado). O CodeQL CLI é gratuito para analisar o próprio código.

```bash
make codeql-quality            # ou: bash scripts/codeql_quality.sh
```

Primeira execução baixa o bundle do CodeQL (CLI + query packs, ~1GB) em `$CODEQL_DIR` (default `~/.codeql`). Reexecuções só recriam a database Python e rodam a suite (~1-2 min). Saída: o breakdown da política do projeto no stdout + SARIF completo em `$CODEQL_SARIF` (default `$TMPDIR/pytstop-codeql-quality.sarif`). On-demand — não entra em `make check`/CI por ser pesado.

Para reproduzir o mesmo conjunto de regras ao longo do tempo (a suite vem dentro do bundle), pine a versão: `CODEQL_BUNDLE_TAG=codeql-bundle-v2.18.4 make codeql-quality` (default `latest`).

### Gate de qualidade

Depois de rodar a suite, o script aplica a política do projeto via `codeql_quality.py` e **atua como gate**: sai com código `!= 0` se sobrar qualquer finding não tratado (ver a seção "Code Quality (CodeQL)" no `MEMORY.md` da raiz). Um finding é considerado tratado quando:

- o path está em `paths-ignore` de `.github/codeql/codeql-config.yml`, ou
- a regra está desligada em `query-filters` da mesma config, ou
- a linha do finding (ou a imediatamente acima) tem um comentário de supressão `# codeql[<regra>]` — opcionalmente com uma razão após ` -- `.

O `codeql database analyze` do CLI não aplica supressão inline (só o code scanning do GitHub o faz), então o gate lê os comentários `# codeql[...]` localmente para reproduzir o mesmo comportamento. Use a supressão por comentário para FP pontuais e a config para regras desligadas wholesale.

**Limites da supressão** (de propósito): ela é **escopada por regra + linha** — uma regressão da mesma regra que cair exatamente na linha já suprimida não re-aciona o gate (a supressão é pontual, não global). E a varredura é **textual**: mantenha o `# codeql[<regra>]` como comentário no fim da linha; um marcador dentro de um literal de string na linha de um finding também o suprimiria.

> [↑ Raiz do projeto](../README.md)
