#!/usr/bin/env bash
# Gera o PDF de submissao da fase 2 FORA do repo, a partir de
# docs/entrega/fase2/entrega-fase-2.md (mesmo fluxo da fase 1):
#   1. rewrite-md-links.py troca links relativos por URLs absolutas do GitHub;
#   2. o bloco Mermaid (que pandoc nao renderiza) vira PNG via mermaid-cli
#      e substitui o bloco no markdown intermediario;
#   3. pandoc + weasyprint produzem o PDF.
# Requisitos: python3, pandoc, weasyprint, npx (mermaid-cli baixado on-demand).
# Uso: bash scripts/build-entrega-pdf.sh   (da raiz do repo)
set -euo pipefail

SRC=docs/entrega/fase2/entrega-fase-2.md
TMP_MD=/tmp/entrega-fase-2-abs.md
TMP_MMD=/tmp/diagrama-fase-2.mmd
TMP_PNG=/tmp/diagrama-fase-2.png
OUT="${HOME}/git/fiap/postech-sw-architecture/documento-entrega-fase-2.pdf"

python3 scripts/rewrite-md-links.py "$SRC" "$TMP_MD" \
  --repo jbamaral/postech-sw-arch-p2 --branch main --base-dir docs/entrega/fase2

python3 - "$TMP_MD" "$TMP_MMD" "$TMP_PNG" <<'EOF'
import re, sys
md, mmd, png = sys.argv[1:4]
src = open(md, encoding="utf-8").read()
m = re.search(r"```mermaid\n(.*?)```", src, re.S)
if m is None:
    sys.exit("erro: bloco ```mermaid``` nao encontrado no markdown de entrega")
open(mmd, "w", encoding="utf-8").write(m.group(1))
src = src.replace(m.group(0), f"![Diagrama de arquitetura da fase 2]({png})")
open(md, "w", encoding="utf-8").write(src)
EOF

npx -y @mermaid-js/mermaid-cli -i "$TMP_MMD" -o "$TMP_PNG" -w 1400 -b white

pandoc "$TMP_MD" -o "$OUT" --pdf-engine=weasyprint -V lang=pt-BR \
  --metadata title="PytStop — Entrega Fase 2"

echo ">> PDF gerado em $OUT"
