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
python scripts/rewrite-md-links.py docs/entrega/entrega-fase-1.md /tmp/absolute.md \
  --repo fiap-postech-sw-architecture/postech-sw-arch-p1 \
  --branch main \
  --base-dir docs/entrega
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

> [↑ Raiz do projeto](../README.md)
