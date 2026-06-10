#!/usr/bin/env bash
# Verify every in-scope doc has the breadcrumb header.
# Usage: bash scripts/lint-doc-anchors.sh <file> [<file>...]
set -euo pipefail

[[ $# -eq 0 ]] && { echo "Uso: $0 <arquivo> [<arquivo>...]" >&2; exit 1; }

fail=0
for f in "$@"; do
  case "$f" in
    README.md|./README.md|CONTRIBUTING.md|./CONTRIBUTING.md)
      continue ;;
  esac
  if ! awk 'NR>=2 && NR<=6 && /^> \[↑ Raiz/' "$f" | grep -q .; then
    echo "MISSING TOP BREADCRUMB: $f" >&2
    fail=1
  fi
  last_nonempty=$(awk 'NF{l=$0} END{print l}' "$f")
  case "$last_nonempty" in
    "> [↑ Raiz"*) : ;;
    *)
      echo "MISSING BOTTOM BREADCRUMB: $f (last line was: $last_nonempty)" >&2
      fail=1
      ;;
  esac
done
exit "$fail"
