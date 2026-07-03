"""Regressao do isolamento de ``sys.modules`` nos testes de UI.

O fixture ``screen`` do NiceGUI 3 (``main_file``) substitui o pacote ``ui`` do
projeto por um stub sem ``__file__`` em ``sys.modules`` -- o que quebrava
``monkeypatch.setattr("ui...")`` em 13 testes quando a suite rodava COM os
marcados ``lento`` no mesmo processo (o CI, com ``-m "not lento"``, nunca ve).
O guard e a fixture autouse ``_preservar_sys_modules_ui`` do conftest deste
pacote; este teste falha se o pacote ``ui`` visto pelo processo deixar de ser o
do repositorio.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RAIZ_REPO = Path(__file__).resolve().parents[3]


def test_sys_modules_ui_e_o_pacote_do_projeto() -> None:
    import ui

    modulo = sys.modules["ui"]
    assert modulo is ui
    assert modulo.__file__ is not None, (
        "sys.modules['ui'] virou stub sem __file__ (poluicao do Screen do "
        "NiceGUI); ver _preservar_sys_modules_ui no conftest"
    )
    assert Path(modulo.__file__).resolve() == _RAIZ_REPO / "ui" / "__init__.py"


def test_monkeypatch_por_caminho_ui_funciona(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reproduz o modo de falha original: setattr por caminho string exige que
    # sys.modules['ui'] seja o pacote real com submodulos resolviveis.
    import ui.estado

    sentinela = object()
    monkeypatch.setattr("ui.estado.StateStore", sentinela)
    assert ui.estado.StateStore is sentinela
