"""Aplica a politica de Code Quality do projeto sobre o SARIF do CodeQL.

Le `.github/codeql/codeql-config.yml` (`paths-ignore` + `query-filters`) e varre
o codigo-fonte por comentarios de supressao `# codeql[<regra>]` na linha do
finding (ou na linha anterior). Imprime o breakdown e sai com codigo != 0 se
sobrar QUALQUER finding nao tratado -- e o gate de Code Quality (ver MEMORY.md).

Por que o script honra os comentarios (e nao o CodeQL): o `codeql database
analyze` do CLI nao aplica supressao inline por padrao (so o code scanning do
GitHub o faz). Para ter o mesmo "suprime via comentario" localmente, o gate le
os `# codeql[...]` aqui. As regras desligadas wholesale ficam em
`query-filters` da config; os FP pontuais, no comentario + razao no codigo.

Uso: python scripts/codeql_quality.py <sarif> <config.yml> <repo-root>
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

_SUPPRESS_RE = re.compile(r"#\s*codeql\[([^\]]*)\]")
_ARGV_ESPERADO = 4  # prog + sarif + config + repo-root


def carregar_politica(config_path: str) -> tuple[list[str], set[str]]:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    paths_ignore = [str(p).strip("/") + "/" for p in cfg.get("paths-ignore", [])]
    regras_off: set[str] = set()
    for filtro in cfg.get("query-filters", []):
        exclude = filtro.get("exclude") if isinstance(filtro, dict) else None
        if exclude and exclude.get("id"):
            ids = exclude["id"]
            regras_off.update(ids if isinstance(ids, list) else [ids])
    return paths_ignore, regras_off


def suprimido_por_comentario(repo_root: str, path: str, line: int, rule: str) -> bool:
    arquivo = Path(repo_root) / path
    if not arquivo.is_file():
        return False
    linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
    # Aceita o comentario na mesma linha do finding ou na linha imediatamente
    # acima (evita estourar o limite de 88 chars em assinaturas longas).
    for numero in (line, line - 1):
        if 1 <= numero <= len(linhas):
            for marca in _SUPPRESS_RE.finditer(linhas[numero - 1]):
                regras = [r.strip() for r in marca.group(1).split(",") if r.strip()]
                if not regras or rule in regras:  # `# codeql[]` cru suprime tudo
                    return True
    return False


def main() -> int:
    if len(sys.argv) != _ARGV_ESPERADO:
        sys.stderr.write(__doc__ or "")
        return 2
    sarif_path, config_path, repo_root = sys.argv[1], sys.argv[2], sys.argv[3]
    paths_ignore, regras_off = carregar_politica(config_path)
    data = json.loads(Path(sarif_path).read_text(encoding="utf-8"))
    resultados = data["runs"][0].get("results", [])

    ativos: list[tuple[str, str, int]] = []
    tratados: Counter[str] = Counter()
    for resultado in resultados:
        rule = resultado.get("ruleId", "?")
        loc = resultado["locations"][0]["physicalLocation"]
        path = loc["artifactLocation"]["uri"]
        line = loc.get("region", {}).get("startLine", 0)
        if any(path.startswith(prefixo) for prefixo in paths_ignore):
            tratados["paths-ignore"] += 1
        elif rule in regras_off:
            tratados["regra-off"] += 1
        elif suprimido_por_comentario(repo_root, path, line, rule):
            tratados["comentario"] += 1
        else:
            ativos.append((rule, path, line))

    print("=== CodeQL Code Quality ===")
    print(
        f"  brutos: {len(resultados)} | tratados: "
        f"paths-ignore={tratados['paths-ignore']} "
        f"regra-off={tratados['regra-off']} comentario={tratados['comentario']}"
    )
    print(f"  ATIVOS (nao tratados): {len(ativos)}")
    for rule, n in Counter(r for r, _, _ in ativos).most_common():
        print(f"    {n:>3}  {rule}")
        for regra_ativa, path, line in ativos:
            if regra_ativa == rule:
                print(f"         {path}:{line}")

    if ativos:
        print(
            "\n!! Gate FALHOU: findings nao tratados acima. Para cada um: corrija, "
            "ou\n   suprima na linha com `# codeql[<regra>]` + razao, ou desabilite a "
            "regra\n   em .github/codeql/codeql-config.yml (se nao fizer sentido)."
        )
        return 1
    print("\nOK: 0 findings nao tratados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
