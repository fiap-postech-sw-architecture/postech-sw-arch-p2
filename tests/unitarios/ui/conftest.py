"""Fixtures compartilhadas dos testes da UI."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_ui_storage() -> None:
    """Isola o storage entre testes instalando um StateStore limpo."""
    from ui.estado import StateStore, configurar_store

    configurar_store(StateStore())
