"""Fixtures compartilhadas dos testes da UI."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import pytest

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
