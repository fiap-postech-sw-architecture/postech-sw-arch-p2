from __future__ import annotations

import sys
from importlib import import_module, reload
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from nicegui.testing import Screen

# Marca como lento — Screen levanta browser headless.
pytestmark = pytest.mark.lento


def _registrar_pagina_login() -> None:
    modulo = sys.modules.get("ui.paginas.login")
    if modulo is None:
        import_module("ui.paginas.login")
    else:
        reload(modulo)


def test_login_mostra_campos_email_e_senha(screen: Screen) -> None:
    _registrar_pagina_login()

    screen.open("/login")
    screen.should_contain("Entrar")
    screen.should_contain("E-mail")
    screen.should_contain("Senha")
    screen.close()


def test_login_mostra_atalhos_dos_3_papeis(screen: Screen) -> None:
    _registrar_pagina_login()

    screen.open("/login")
    screen.should_contain("Admin")
    screen.should_contain("Atendente")
    screen.should_contain("Mecanico")
    screen.close()
