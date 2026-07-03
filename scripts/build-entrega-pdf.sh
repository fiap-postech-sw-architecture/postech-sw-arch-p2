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

for f in "$SRC" "$SEGURANCA" "$EXTRAS" scripts/rewrite-md-links.py \
  docs/entrega/fase2/evidencias/b1-ci-cd-verde.png \
  docs/entrega/fase2/evidencias/b2-hpa-escalando.png \
  docs/entrega/fase2/evidencias/b3a-jaeger-busca.png \
  docs/entrega/fase2/evidencias/b3b-jaeger-trace.png \
  docs/entrega/fase2/evidencias/b4-mailpit-emails.png \
  docs/entrega/fase2/evidencias/b5-prometheus-outbox.png \
  docs/entrega/fase2/evidencias/b6-sonarqube-quality-gate.png \
  docs/entrega/fase2/evidencias/b6b-sonarqube-hotspots-zerados.png; do
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
  cat <<ANEXOB
> Capturas da demonstração no cluster kind (\`make cd-local\`), na mesma sequência
> do roteiro do vídeo. Fontes versionadas em \`docs/entrega/fase2/evidencias/\`.

## B1 — Pipeline verde na \`main\`

![CI, CD, Security, CodeQL e full-test verdes na main](${PWD}/docs/entrega/fase2/evidencias/b1-ci-cd-verde.png)

## B2 — HPA escalando 1→5 sob carga

![kubectl: HPA pytstop-api com 5 replicas sob carga](${PWD}/docs/entrega/fase2/evidencias/b2-hpa-escalando.png)

## B3 — Traces no Jaeger

![Busca no Jaeger: traces das transicoes de OS](${PWD}/docs/entrega/fase2/evidencias/b3a-jaeger-busca.png)

![Trace da aprovacao com 18 spans fastapi+sqlalchemy](${PWD}/docs/entrega/fase2/evidencias/b3b-jaeger-trace.png)

## B4 — E-mails no Mailpit (um por transição de OS)

![Mailpit com 15 e-mails de transicao](${PWD}/docs/entrega/fase2/evidencias/b4-mailpit-emails.png)

## B5 — Métricas do outbox no Prometheus

![outbox_entregue_total=15 e outbox_pendentes=0](${PWD}/docs/entrega/fase2/evidencias/b5-prometheus-outbox.png)

## B6 — SonarQube: scan de fechamento, antes e depois

**Antes** — primeira análise da HEAD final: Quality Gate Passed com **3 security
hotspots** a revisar.

![Antes: Quality Gate Passed, 3 hotspots a revisar](${PWD}/docs/entrega/fase2/evidencias/b6-sonarqube-quality-gate.png)

**Depois** — hotspots tratados no fluxo da ferramenta (1 corrigido no código —
regex de e-mail sem backtracking polinomial, S5852; 2 revisados como seguros —
OTLP intra-cluster), universo de cobertura alinhado ao gate e reanálise:
**0 hotspots**, gate mantido Passed, coverage 95,3%. Detalhes na seção
SonarQube do Anexo A.

![Depois: 0 hotspots a revisar, Quality Gate Passed](${PWD}/docs/entrega/fase2/evidencias/b6b-sonarqube-hotspots-zerados.png)
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
