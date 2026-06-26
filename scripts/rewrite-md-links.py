"""Rewrite relative markdown links to absolute GitHub URLs on main, for PDF export.

Usage:
    python scripts/rewrite-md-links.py INPUT.md OUTPUT.md \
        --repo fiap-postech-sw-architecture/postech-sw-arch-p2 \
        --branch main \
        --base-dir docs/entrega

INPUT.md is the source markdown. --base-dir is the directory of the source file
(used to resolve relative paths). External (https://) links pass through unchanged.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def rewrite(text: str, repo: str, branch: str, base_dir: Path) -> str:
    repo_root = base_dir.resolve()
    while repo_root.parent != repo_root and not (repo_root / ".git").exists():
        repo_root = repo_root.parent

    def repl(m: re.Match[str]) -> str:
        label, href = m.group(1), m.group(2)
        if not href or href.startswith(("http://", "https://", "mailto:", "#")):
            return m.group(0)
        anchor = ""
        if "#" in href:
            href, anchor = href.split("#", 1)
            anchor = f"#{anchor}"
        if not href:
            return m.group(0)
        target = (base_dir / href).resolve()
        try:
            rel = target.relative_to(repo_root)
        except ValueError:
            return m.group(0)
        url = f"https://github.com/{repo}/blob/{branch}/{rel}{anchor}"
        return f"[{label}]({url})"

    return LINK_RE.sub(repl, text)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--base-dir", required=True)
    args = p.parse_args()
    src = Path(args.input).read_text(encoding="utf-8")
    out = rewrite(src, args.repo, args.branch, Path(args.base_dir).resolve())
    Path(args.output).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
