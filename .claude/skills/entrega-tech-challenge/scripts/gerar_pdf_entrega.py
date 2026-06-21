#!/usr/bin/env python3
"""Gera o PDF de entrega (FIAP Pos Tech) a partir de um markdown de entrega.

Pipeline (mesma receita refinada na fase 2, generalizada para qualquer fase):

  1. Reescreve links relativos do markdown para URLs absolutas do GitHub
     (blob/<branch>), para que cliques funcionem no PDF. Links externos
     (http/https/mailto/#ancora) passam intactos.
  2. Renderiza CADA bloco ```mermaid``` para PNG via mermaid-cli (pandoc nao
     renderiza mermaid sozinho) e troca o bloco pela imagem.
  3. pandoc + weasyprint produzem o PDF.

O markdown de origem NAO e modificado: tudo acontece num intermediario em /tmp.
O PDF sai FORA do repo por padrao (artefato de build, nao versionado).

Uso:
    python gerar_pdf_entrega.py docs/entrega/fase2/entrega-fase-2.md
    python gerar_pdf_entrega.py <md> --output ~/saida.pdf --repo owner/repo --branch main

Pre-requisitos: python3, pandoc, weasyprint, npx (mermaid-cli baixado on-demand).
Sem --repo, tenta detectar via `gh repo view` e depois `git remote`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.S)


def _erro(msg: str) -> None:
    print(f"erro: {msg}", file=sys.stderr)
    raise SystemExit(1)


def detectar_repo(base_dir: Path) -> str | None:
    """owner/repo via gh; fallback no remote origin do git."""
    try:
        out = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        nome = out.stdout.strip()
        if nome:
            return nome
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    # git@github.com:owner/repo.git  ou  https://github.com/owner/repo(.git)
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def achar_repo_root(base_dir: Path) -> Path:
    root = base_dir.resolve()
    while root.parent != root and not (root / ".git").exists():
        root = root.parent
    return root


def reescrever_links(texto: str, repo: str, branch: str, base_dir: Path) -> str:
    repo_root = achar_repo_root(base_dir)

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
        alvo = (base_dir / href).resolve()
        try:
            rel = alvo.relative_to(repo_root)
        except ValueError:
            return m.group(0)
        return f"[{label}](https://github.com/{repo}/blob/{branch}/{rel}{anchor})"

    return LINK_RE.sub(repl, texto)


def renderizar_mermaid(texto: str, tmp: Path) -> str:
    """Troca cada bloco ```mermaid``` por um PNG renderizado. Sem blocos, no-op."""
    blocos = list(MERMAID_RE.finditer(texto))
    if not blocos:
        return texto
    if shutil.which("npx") is None:
        _erro("npx ausente — necessario para renderizar mermaid (mermaid-cli).")
    for i, m in enumerate(blocos):
        mmd = tmp / f"diagrama-{i}.mmd"
        png = tmp / f"diagrama-{i}.png"
        mmd.write_text(m.group(1), encoding="utf-8")
        subprocess.run(
            ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", str(mmd),
             "-o", str(png), "-w", "1400", "-b", "white"],
            check=True,
        )
        texto = texto.replace(
            m.group(0), f"![Diagrama de arquitetura]({png})", 1
        )
    return texto


def main() -> int:
    p = argparse.ArgumentParser(description="Gera o PDF de entrega da fase.")
    p.add_argument("markdown", help="markdown de entrega (ex.: docs/entrega/faseN/entrega-fase-N.md)")
    p.add_argument("--output", help="caminho do PDF (default: ~/<nome>.pdf, fora do repo)")
    p.add_argument("--repo", help="owner/repo (default: auto via gh/git)")
    p.add_argument("--branch", default="main")
    args = p.parse_args()

    for bin_ in ("pandoc", "weasyprint"):
        if shutil.which(bin_) is None:
            _erro(f"{bin_} ausente. Instale (ex.: brew install {bin_}).")

    src = Path(args.markdown).resolve()
    if not src.is_file():
        _erro(f"markdown nao encontrado: {src}")
    base_dir = src.parent

    repo = args.repo or detectar_repo(base_dir)
    if not repo:
        _erro("nao consegui detectar o repo; passe --repo owner/repo.")
    print(f">> repo={repo} branch={args.branch} fonte={src.name}")

    out = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.home() / f"{src.stem}.pdf"
    )

    tmp = Path("/tmp") / f"entrega-pdf-{src.stem}"
    tmp.mkdir(parents=True, exist_ok=True)

    texto = src.read_text(encoding="utf-8")
    texto = reescrever_links(texto, repo, args.branch, base_dir)
    texto = renderizar_mermaid(texto, tmp)
    md_abs = tmp / f"{src.stem}-abs.md"
    md_abs.write_text(texto, encoding="utf-8")

    subprocess.run(
        ["pandoc", str(md_abs), "-o", str(out),
         "--pdf-engine=weasyprint", "-V", "lang=pt-BR",
         "--metadata", f"title={src.stem}"],
        check=True,
    )
    print(f">> PDF gerado em {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
