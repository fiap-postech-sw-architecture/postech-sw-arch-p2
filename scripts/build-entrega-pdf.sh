#!/usr/bin/env bash
# Gera o PDF de submissao da fase 2 FORA do repo, a partir de
# docs/entrega/fase2/entrega-fase-2.md (mesmo fluxo da fase 1, agora com capa +
# anexos -- issue #123):
#   1. rewrite-md-links.py troca links relativos por URLs absolutas do GitHub
#      (por-arquivo, cada um com seu --base-dir, para os anexos preservarem os
#      proprios links);
#   2. pre-pende a CAPA ABNT (FIAP/15SOAT, integrantes + RM, cidade/ano);
#   3. remove a "## 8. Pendencias..." (checklist interno -- nao vai pro PDF);
#   4. anexa Anexo A (scans de seguranca), B (evidencias visuais) e C
#      (funcionalidades extras);
#   5. o bloco Mermaid (que pandoc nao renderiza) vira PNG via mermaid-cli;
#   6. pandoc + weasyprint produzem o PDF.
# Requisitos: python3, pandoc, weasyprint, npx (mermaid-cli baixado on-demand).
# Regere SOMENTE apos preencher o VIDEO-LINK-FASE-2 (o script avisa se faltar).
# Uso: bash scripts/build-entrega-pdf.sh   (da raiz do repo)
set -euo pipefail

REPO=fiap-postech-sw-architecture/postech-sw-arch-p2
BRANCH=main
SRC=docs/entrega/fase2/entrega-fase-2.md
SEGURANCA=docs/seguranca/scan-fase-2.md
EXTRAS=docs/entrega/fase2/apendice-funcionalidades-extras.md
OUT="${HOME}/git/fiap/postech-sw-architecture/documento-entrega-fase-2.pdf"
CIDADE="São Paulo"
ANO="2026"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
COMBINADO="${TMP}/entrega-completo.md"
TMP_MMD="${TMP}/diagrama.mmd"
TMP_PNG="${TMP}/diagrama.png"

for f in "$SRC" "$SEGURANCA" "$EXTRAS" scripts/rewrite-md-links.py; do
  [ -f "$f" ] || { echo "erro: arquivo obrigatorio ausente: $f" >&2; exit 1; }
done

# Aviso (nao-fatal) se o link do video ainda for placeholder.
if grep -q "VIDEO-LINK-FASE-2" "$SRC"; then
  echo "AVISO: VIDEO-LINK-FASE-2 ainda e placeholder -- preencha antes de submeter (issue #123)." >&2
fi

# 1) Links absolutos por-arquivo (cada um com seu base-dir).
rewrite() {  # <src> <dst> <base-dir>
  python3 scripts/rewrite-md-links.py "$1" "$2" --repo "$REPO" --branch "$BRANCH" --base-dir "$3"
}
rewrite "$SRC"       "${TMP}/body.md"   docs/entrega/fase2
rewrite "$SEGURANCA" "${TMP}/anexoA.md" docs/seguranca
rewrite "$EXTRAS"    "${TMP}/anexoC.md" docs/entrega/fase2

# 2) CAPA ABNT (quebra de pagina apos).
cat > "$COMBINADO" <<CAPA
<div style="text-align:center; min-height:23cm; display:flex; flex-direction:column; justify-content:space-between; break-after:page;">

<div>

**FIAP — Faculdade de Informática e Administração Paulista**

15SOAT — Pós-Graduação em Arquitetura de Software

</div>

<div>

# Tech Challenge — Fase 2

### PytStop — Plataforma de Gestão de Ordens de Serviço

_Documento de Entrega_

</div>

<div>

João Amaral — RM373448 · Allan Aurélio — RM372116 · Carlos Silva — RM374191

Guilherme Sousa — RM373609 · Nicolas Gerbi — RM372644

</div>

<div>

${CIDADE} — ${ANO}

</div>

</div>

CAPA

# 3) Corpo, sem "## 9. Pendencias..." (do cabecalho ate o fim; salvaguarda p/ ## 10).
awk '
  /^## 9\. Pend/ { pular=1 }
  /^## 10\./     { pular=0 }
  !pular         { print }
' "${TMP}/body.md" >> "$COMBINADO"

# 4) Anexos (cada um em pagina nova; pula o H1 de origem pois o anexo ja titula).
{
  printf '\n\n<div style="break-before:page;"></div>\n\n# Anexo A — Scans de Segurança da Fase 2\n\n'
  tail -n +2 "${TMP}/anexoA.md"

  printf '\n\n<div style="break-before:page;"></div>\n\n# Anexo B — Evidências Visuais\n\n'
  cat <<'ANEXOB'
> Capturas da demonstração no cluster kind, na mesma sequência do roteiro do vídeo.
> Gerar com a stack no ar (`make cd-local`) e inserir as imagens antes de submeter.

| # | Evidência | Como capturar |
|---|---|---|
| B1 | Run verde do CD na `main` | GitHub Actions → `full-test (ci)` / `cd` |
| B2 | HPA escalando 1→N | `kubectl -n pytstop get hpa -w` sob carga (roteiro, bloco 5) |
| B3 | Trace no Jaeger | http://localhost:16686 → `pytstop-api` → trace com spans fastapi+sqlalchemy |
| B4 | E-mail no Mailpit | http://localhost:8025 → caixa com um e-mail por transição de OS |
| B5 | Métricas no Prometheus | http://localhost:9090 → `outbox_entregue_total` > 0 e `outbox_pendentes` = 0 |
| B6 | Quality Gate do SonarQube | painel do projeto → Passed + cobertura |
ANEXOB

  printf '\n\n<div style="break-before:page;"></div>\n\n# Anexo C — Funcionalidades Extras da Fase 2\n\n'
  tail -n +2 "${TMP}/anexoC.md"
} >> "$COMBINADO"

# 5) Mermaid -> PNG (o bloco vive na secao 6 do corpo).
python3 - "$COMBINADO" "$TMP_MMD" "$TMP_PNG" <<'EOF'
import re, sys
md, mmd, png = sys.argv[1:4]
src = open(md, encoding="utf-8").read()
m = re.search(r"```mermaid\n(.*?)```", src, re.S)
if m is None:
    sys.exit("erro: bloco ```mermaid``` nao encontrado no markdown combinado")
open(mmd, "w", encoding="utf-8").write(m.group(1))
src = src.replace(m.group(0), f"![Diagrama de arquitetura da fase 2]({png})")
open(md, "w", encoding="utf-8").write(src)
EOF
npx -y @mermaid-js/mermaid-cli -i "$TMP_MMD" -o "$TMP_PNG" -w 1400 -b white

# 6) PDF.
pandoc "$COMBINADO" -o "$OUT" --pdf-engine=weasyprint -V lang=pt-BR \
  --metadata title="PytStop — Entrega Fase 2"

echo ">> PDF gerado em $OUT"
