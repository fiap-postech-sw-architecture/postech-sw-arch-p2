#!/usr/bin/env bash
# Roda o CodeQL "Code Quality" suite localmente -- as MESMAS queries do
# GitHub Code Quality (preview). Util para reproduzir/triar os findings sem
# depender da UI do GitHub: o report de Code Quality nao tem API publica, e o
# endpoint de code scanning exige GitHub Advanced Security (indisponivel no
# repo privado). O CodeQL CLI e gratuito para analisar o proprio codigo.
#
# Primeira execucao baixa o bundle do CodeQL (CLI + query packs, ~1GB) em
# $CODEQL_DIR. Reusos so recriam a database e rodam a suite (~1-2 min).
#
# Uso:
#   make codeql-quality                              # alvo do Makefile
#   bash scripts/codeql_quality.sh                   # direto
#   CODEQL_DIR=~/codeql-tools bash scripts/...        # reusa um CLI ja baixado
#
# Saida: breakdown por regra no stdout + SARIF completo em $CODEQL_SARIF.
set -euo pipefail

CODEQL_DIR="${CODEQL_DIR:-$HOME/.codeql}"
CODEQL="$CODEQL_DIR/codeql/codeql"
DB="${CODEQL_DB:-${TMPDIR:-/tmp}/pytstop-codeql-db}"
SARIF="${CODEQL_SARIF:-${TMPDIR:-/tmp}/pytstop-codeql-quality.sarif}"
SUITE="codeql/python-queries:codeql-suites/python-code-quality.qls"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# 1. CLI -- baixa o bundle (CLI + query packs) uma unica vez.
if [ ! -x "$CODEQL" ]; then
  case "$(uname -s)" in
    Darwin) plat=osx64 ;;
    Linux) plat=linux64 ;;
    *) echo "!! plataforma '$(uname -s)' sem bundle CodeQL pronto." >&2; exit 1 ;;
  esac
  echo ">> baixando CodeQL bundle (uma vez, ~1GB) em $CODEQL_DIR ..."
  mkdir -p "$CODEQL_DIR"
  curl -fSL --retry 3 -o "$CODEQL_DIR/bundle.tar.gz" \
    "https://github.com/github/codeql-action/releases/latest/download/codeql-bundle-$plat.tar.gz"
  tar xzf "$CODEQL_DIR/bundle.tar.gz" -C "$CODEQL_DIR"
  rm -f "$CODEQL_DIR/bundle.tar.gz"
fi
echo ">> CodeQL $("$CODEQL" version --format=terse 2>/dev/null || echo '?')"

# 2. Database Python (extracao do AST -- linguagem interpretada, sem build).
echo ">> criando database Python em $DB ..."
"$CODEQL" database create "$DB" --language=python --source-root="$REPO_ROOT" --overwrite

# 3. Roda a suite de qualidade.
echo ">> analisando com $SUITE ..."
"$CODEQL" database analyze "$DB" "$SUITE" \
  --format=sarif-latest --output="$SARIF" --threads=0

# 4. Breakdown por regra (stdout).
python3 - "$SARIF" <<'PY'
import json
import sys
from collections import Counter

data = json.load(open(sys.argv[1]))
results = data["runs"][0].get("results", [])
counts = Counter(r.get("ruleId", "?") for r in results)
print(f"\n=== CodeQL Code Quality: {sum(counts.values())} findings ===")
for rule, n in counts.most_common():
    print(f"  {n:>4}  {rule}")
print(f"\nSARIF completo: {sys.argv[1]}")
PY
