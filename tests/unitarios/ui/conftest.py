"""Fixtures compartilhadas dos testes da UI."""

from __future__ import annotations

from importlib.util import find_spec

import pytest

# Carrega o plugin Screen do NiceGUI apenas quando selenium estiver disponivel.
# Isso permite rodar `pytest -m "not lento"` sem instalar browser drivers.
# Para rodar testes marcados `lento` que usam a fixture `screen`, instale
# selenium manualmente: `uv pip install selenium` ou adicione ao extra `ui`.
if find_spec("selenium") is not None:
    pytest_plugins = ["nicegui.testing.plugin"]


@pytest.fixture(autouse=True)
def _reset_ui_storage() -> None:
    """Isola o storage entre testes instalando um StateStore limpo."""
    from ui.estado import StateStore, configurar_store

    configurar_store(StateStore())
