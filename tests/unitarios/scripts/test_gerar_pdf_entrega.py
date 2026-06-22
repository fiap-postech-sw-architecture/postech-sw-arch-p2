"""Testes unitarios para o script de geracao do PDF de entrega.

Alvo: `.claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py`.

O script vive fora da arvore de pacotes (sob `.claude/skills/...`), entao e
carregado por caminho via importlib em vez de `import` normal. Cobre as funcoes
puras (reescrita de links relativos -> URL absoluta do GitHub, descoberta do
repo root, deteccao owner/repo) e — com `subprocess`/`shutil.which` mockados —
os branches de renderizacao mermaid e do `main` (pre-requisitos ausentes +
happy path). Nenhum binario externo (pandoc/npx/weasyprint) e exercido.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / ".claude/skills/entrega-tech-challenge/scripts/gerar_pdf_entrega.py"
)


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gerar_pdf_entrega", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _carregar()


# --------------------------------------------------------------------------- #
# achar_repo_root
# --------------------------------------------------------------------------- #
class TestAcharRepoRoot:
    def test_sobe_ate_o_diretorio_com_dot_git(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        fundo = tmp_path / "docs" / "entrega"
        fundo.mkdir(parents=True)
        assert mod.achar_repo_root(fundo) == tmp_path

    def test_sem_dot_git_chega_na_raiz_do_filesystem(self, tmp_path: Path) -> None:
        # Sem nenhum .git acima, o loop para quando parent == self (raiz).
        root = mod.achar_repo_root(tmp_path)
        assert root == Path(root.anchor)


# --------------------------------------------------------------------------- #
# reescrever_links
# --------------------------------------------------------------------------- #
class TestReescreverLinks:
    @pytest.fixture
    def base(self, tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        return docs

    def test_link_relativo_vira_url_absoluta_do_github(self, base: Path) -> None:
        out = mod.reescrever_links("[alvo](alvo.md)", "o/r", "main", base)
        assert out == "[alvo](https://github.com/o/r/blob/main/docs/alvo.md)"

    def test_preserva_ancora(self, base: Path) -> None:
        out = mod.reescrever_links("[s](alvo.md#sec)", "o/r", "main", base)
        assert out == "[s](https://github.com/o/r/blob/main/docs/alvo.md#sec)"

    def test_respeita_branch(self, base: Path) -> None:
        out = mod.reescrever_links("[a](alvo.md)", "o/r", "dev", base)
        assert "/blob/dev/" in out

    @pytest.mark.parametrize(
        "href",
        ["https://x.com", "http://x.com", "mailto:a@b.com", "#secao-interna"],
    )
    def test_links_externos_e_ancoras_passam_intactos(
        self, base: Path, href: str
    ) -> None:
        texto = f"[x]({href})"
        assert mod.reescrever_links(texto, "o/r", "main", base) == texto

    def test_href_vazio_passa_intacto(self, base: Path) -> None:
        assert mod.reescrever_links("[x]()", "o/r", "main", base) == "[x]()"

    def test_alvo_fora_do_repo_nao_e_reescrito(self, base: Path) -> None:
        # ../../fora.md a partir de <repo>/docs sai do repo_root -> intacto.
        texto = "[fora](../../fora.md)"
        assert mod.reescrever_links(texto, "o/r", "main", base) == texto

    def test_texto_sem_links_e_inalterado(self, base: Path) -> None:
        texto = "prosa sem nenhum link aqui"
        assert mod.reescrever_links(texto, "o/r", "main", base) == texto


# --------------------------------------------------------------------------- #
# detectar_repo
# --------------------------------------------------------------------------- #
class TestDetectarRepo:
    def test_usa_gh_quando_disponivel(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            run.return_value = MagicMock(stdout="owner/repo\n")
            assert mod.detectar_repo(tmp_path) == "owner/repo"
        run.assert_called_once()  # nao caiu no fallback do git

    def test_fallback_git_ssh_quando_gh_vazio(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            run.side_effect = [
                MagicMock(stdout=""),  # gh devolve vazio
                MagicMock(stdout="git@github.com:o/r.git\n"),
            ]
            assert mod.detectar_repo(tmp_path) == "o/r"

    def test_fallback_git_https_quando_gh_falha(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            run.side_effect = [
                subprocess.CalledProcessError(1, "gh"),
                MagicMock(stdout="https://github.com/o/r"),
            ]
            assert mod.detectar_repo(tmp_path) == "o/r"

    def test_remote_nao_github_devolve_none(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            run.side_effect = [
                subprocess.CalledProcessError(1, "gh"),
                MagicMock(stdout="https://gitlab.com/o/r.git"),
            ]
            assert mod.detectar_repo(tmp_path) is None

    def test_sem_gh_nem_git_devolve_none(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            run.side_effect = [FileNotFoundError, FileNotFoundError]
            assert mod.detectar_repo(tmp_path) is None


# --------------------------------------------------------------------------- #
# renderizar_mermaid
# --------------------------------------------------------------------------- #
class TestRenderizarMermaid:
    def test_sem_blocos_e_no_op_sem_chamar_subprocess(self, tmp_path: Path) -> None:
        with patch.object(mod.subprocess, "run") as run:
            out = mod.renderizar_mermaid("texto puro", tmp_path)
        assert out == "texto puro"
        run.assert_not_called()

    def test_troca_bloco_por_imagem_e_grava_mmd(self, tmp_path: Path) -> None:
        texto = "a\n```mermaid\ngraph TD\nA-->B\n```\nb"
        with (
            patch.object(mod.shutil, "which", return_value="/usr/bin/npx"),
            patch.object(mod.subprocess, "run") as run,
        ):
            out = mod.renderizar_mermaid(texto, tmp_path)
        assert "```mermaid" not in out
        assert "![Diagrama de arquitetura]" in out
        assert (tmp_path / "diagrama-0.mmd").read_text() == "graph TD\nA-->B\n"
        run.assert_called_once()
        assert "@mermaid-js/mermaid-cli" in run.call_args.args[0]

    def test_npx_ausente_aborta(self, tmp_path: Path) -> None:
        texto = "```mermaid\ngraph TD\nA-->B\n```"
        with (
            patch.object(mod.shutil, "which", return_value=None),
            pytest.raises(SystemExit),
        ):
            mod.renderizar_mermaid(texto, tmp_path)


# --------------------------------------------------------------------------- #
# _erro
# --------------------------------------------------------------------------- #
def test_erro_sai_com_codigo_1(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        mod._erro("falhou")
    assert exc.value.code == 1
    assert "falhou" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
class TestMain:
    def test_aborta_quando_prerequisito_ausente(self, tmp_path: Path) -> None:
        md = tmp_path / "e.md"
        md.write_text("x")
        with (
            patch.object(mod.shutil, "which", return_value=None),
            patch.object(mod.sys, "argv", ["prog", str(md)]),
            pytest.raises(SystemExit),
        ):
            mod.main()

    def test_aborta_quando_markdown_inexistente(self, tmp_path: Path) -> None:
        ausente = tmp_path / "nao-existe.md"
        with (
            patch.object(mod.shutil, "which", return_value="/bin/x"),
            patch.object(mod.sys, "argv", ["prog", str(ausente)]),
            pytest.raises(SystemExit),
        ):
            mod.main()

    def test_aborta_quando_repo_nao_detectado(self, tmp_path: Path) -> None:
        md = tmp_path / "e.md"
        md.write_text("x")
        with (
            patch.object(mod.shutil, "which", return_value="/bin/x"),
            patch.object(mod, "detectar_repo", return_value=None),
            patch.object(mod.sys, "argv", ["prog", str(md)]),
            pytest.raises(SystemExit),
        ):
            mod.main()

    def test_happy_path_reescreve_link_e_chama_pandoc(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        md = docs / "entrega.md"
        md.write_text("[peer](peer.md)\n")
        work = tmp_path / "work"
        work.mkdir()
        out_pdf = tmp_path / "out.pdf"
        with (
            patch.object(mod.shutil, "which", return_value="/bin/x"),
            patch.object(mod.tempfile, "mkdtemp", return_value=str(work)),
            patch.object(mod.subprocess, "run") as run,
            patch.object(
                mod.sys,
                "argv",
                ["prog", str(md), "--repo", "o/r", "--output", str(out_pdf)],
            ),
        ):
            assert mod.main() == 0
        md_abs = (work / "entrega-abs.md").read_text()
        assert "https://github.com/o/r/blob/main/docs/peer.md" in md_abs
        chamadas = [c.args[0][0] for c in run.call_args_list]
        assert "pandoc" in chamadas
