"""Fixtures compartilhadas dos testes da UI."""

from __future__ import annotations

import sys
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_NICEGUI_STORAGE_DIR = Path(".nicegui")
_BROWSER_TESTING_DISPONIVEL = (
    find_spec("selenium") is not None and find_spec("pytest_selenium") is not None
)

# O plugin Screen do NiceGUI e carregado pelo conftest raiz quando o stack de
# browser esta disponivel. A fixture `chrome_options` vem de pytest-selenium.
# Para rodar testes marcados `lento` que usam `screen`, use `make test-lento`
# ou `uv run --extra test --extra ui pytest -m lento`.
if not _BROWSER_TESTING_DISPONIVEL:

    @pytest.fixture
    def screen() -> None:
        pytest.skip(
            "selenium/pytest-selenium nao instalados; fixture 'screen' indisponivel"
        )


@pytest.fixture(autouse=True)
def _preservar_storage_nicegui() -> None:
    snapshots = {
        path: path.read_bytes()
        for path in _NICEGUI_STORAGE_DIR.glob("storage-user-*.json")
    }
    yield
    if not snapshots:
        return
    _NICEGUI_STORAGE_DIR.mkdir(exist_ok=True)
    for path, content in snapshots.items():
        path.write_bytes(content)


@pytest.fixture(autouse=True)
def _reset_ui_storage() -> None:
    """Isola o storage entre testes instalando um StateStore limpo."""
    from ui.estado import StateStore, configurar_store

    configurar_store(StateStore())


@pytest.fixture(autouse=True)
def _preservar_sys_modules_ui() -> Iterator[None]:
    """Restaura os modulos ``ui*`` que o Screen do NiceGUI 3 corrompe.

    O fixture ``screen`` (via ``main_file``) reimporta o app e deixa em
    ``sys.modules["ui"]`` um stub sem ``__file__`` no lugar do pacote do
    projeto; qualquer ``monkeypatch.setattr("ui...")`` de teste seguinte na
    MESMA sessao falha com AttributeError. O CI nao ve (roda ``-m "not
    lento"``); numa sessao local mista (rapidos + lentos), sem este guard,
    13 testes quebram.

    Nota: restaurar os modulos originais desfaz a evicao que o plugin do
    NiceGUI usa para re-registrar rotas ``@ui.page`` -- nova cobertura de
    Screen deve continuar DENTRO do unico teste consolidado (ver
    test_login.py), nao em testes de browser adicionais.
    """
    snapshot = {
        nome: modulo
        for nome, modulo in sys.modules.items()
        if nome == "ui" or nome.startswith("ui.")
    }
    yield
    for nome, modulo in snapshot.items():
        if sys.modules.get(nome) is not modulo:
            sys.modules[nome] = modulo
