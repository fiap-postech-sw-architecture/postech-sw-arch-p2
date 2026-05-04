from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

# Sem o extra ``ui`` instalado, ``import ui.paginas.login`` quebra a coleta
# do modulo com ``ModuleNotFoundError`` (nicegui ausente). ``importorskip``
# alinha o fallback com o conftest UI raiz, que ja pula a fixture ``screen``
# quando selenium/pytest-selenium nao estao disponiveis.
pytest.importorskip("nicegui")

import ui.paginas.login as _modulo_login

if TYPE_CHECKING:
    from nicegui.testing import Screen

# Lento (Screen levanta browser headless) e ``module_under_test`` para que o
# fixture ``screen`` do nicegui.testing recarregue o modulo dentro do
# auto-index client recem-resetado e re-execute o decorator ``@ui.page``,
# em vez de manipular ``sys.modules`` na mao.
pytestmark = [
    pytest.mark.lento,
    pytest.mark.module_under_test(_modulo_login),
]


def test_login_mostra_campos_email_e_senha(screen: Screen) -> None:
    screen.open("/login")
    screen.should_contain("Entrar")
    screen.should_contain("E-mail")
    screen.should_contain("Senha")
    screen.close()


def test_login_mostra_atalhos_dos_3_papeis(screen: Screen) -> None:
    screen.open("/login")
    screen.should_contain("Admin")
    screen.should_contain("Atendente")
    screen.should_contain("Mecanico")
    screen.close()
