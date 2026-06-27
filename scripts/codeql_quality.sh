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
#   CODEQL_BUNDLE_TAG=codeql-bundle-v2.18.4 make codeql-quality   # pina a versao
#
# Saida: aplica a politica do projeto (scripts/codeql_quality.py) e atua como
# GATE -- sai != 0 se sobrar QUALQUER finding nao tratado; SARIF completo em
# $CODEQL_SARIF.
set -euo pipefail

CODEQL_DIR="${CODEQL_DIR:-$HOME/.codeql}"
CODEQL="$CODEQL_DIR/codeql/codeql"
# Versao do bundle. Default `latest`; pine para reproduzir o MESMO conjunto de
# regras ao longo do tempo (a suite vem dentro do bundle), ex.:
# CODEQL_BUNDLE_TAG=codeql-bundle-v2.18.4.
CODEQL_BUNDLE_TAG="${CODEQL_BUNDLE_TAG:-latest}"
_tmp="${TMPDIR:-/tmp}"; _tmp="${_tmp%/}"  # macOS: $TMPDIR termina em '/' -> evita '//'
DB="${CODEQL_DB:-$_tmp/pytstop-codeql-db}"
SARIF="${CODEQL_SARIF:-$_tmp/pytstop-codeql-quality.sarif}"
SUITE="codeql/python-queries:codeql-suites/python-code-quality.qls"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# 1. CLI -- baixa o bundle (CLI + query packs) uma unica vez.
if [ ! -x "$CODEQL" ]; then
  case "$(uname -s)" in
    Darwin) plat=osx64 ;;
    Linux) plat=linux64 ;;
    *) echo "!! plataforma '$(uname -s)' sem bundle CodeQL pronto." >&2; exit 1 ;;
  esac
  echo ">> baixando CodeQL bundle ($CODEQL_BUNDLE_TAG, uma vez, ~1GB) em $CODEQL_DIR ..."
  mkdir -p "$CODEQL_DIR"
  base="https://github.com/github/codeql-action/releases"
  if [ "$CODEQL_BUNDLE_TAG" = "latest" ]; then
    bundle_url="$base/latest/download/codeql-bundle-$plat.tar.gz"
  else
    bundle_url="$base/download/$CODEQL_BUNDLE_TAG/codeql-bundle-$plat.tar.gz"
  fi
  curl -fSL --retry 3 -o "$CODEQL_DIR/bundle.tar.gz" "$bundle_url"
  # `tar xzf` falha em download truncado/corrompido -- mitiga a ausencia de
  # checksum dedicado (a fonte ja e HTTPS do GitHub).
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

# 4. Politica do projeto + gate (sai != 0 se sobrar finding nao tratado).
PY_RUN="python3"; command -v uv >/dev/null 2>&1 && PY_RUN="uv run python"
$PY_RUN "$REPO_ROOT/scripts/codeql_quality.py" "$SARIF" "$REPO_ROOT/.github/codeql/codeql-config.yml" "$REPO_ROOT"
