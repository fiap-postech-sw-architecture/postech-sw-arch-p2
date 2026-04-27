from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from nicegui.testing import Screen

# Marca como lento — Screen levanta browser headless.
pytestmark = pytest.mark.lento


def test_login_mostra_campos_email_e_senha(screen: Screen) -> None:
    import ui.paginas.login  # noqa: F401 — registra a pagina

    screen.open("/login")
    screen.should_contain("Entrar")
    screen.should_contain("E-mail")
    screen.should_contain("Senha")


def test_login_mostra_atalhos_dos_3_papeis(screen: Screen) -> None:
    import ui.paginas.login  # noqa: F401

    screen.open("/login")
    screen.should_contain("Admin")
    screen.should_contain("Atendente")
    screen.should_contain("Mecanico")
