from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

# Sem o extra ``ui`` instalado, ``nicegui`` ausente pularia a coleta.
# ``importorskip`` alinha o fallback com o conftest UI raiz, que ja pula a
# fixture ``screen`` quando selenium/pytest-selenium nao estao disponiveis.
pytest.importorskip("nicegui")

if TYPE_CHECKING:
    from nicegui.testing import Screen

# Lento (Screen levanta browser headless). NiceGUI 3 removeu o marker
# ``module_under_test`` do plugin nicegui 2; o fixture ``screen`` agora roda o
# app a partir do ``main_file`` informado. ``ui/__main__.py`` importa ``ui.app``
# (registra as paginas ``@ui.page``) e chama ``ui.run()`` sob ``__mp_main__`` —
# o modo que o Screen usa no subprocesso.
pytestmark = [
    pytest.mark.lento,
    pytest.mark.nicegui_main_file("ui/__main__.py"),
]


def test_login_renderiza_campos_e_atalhos(screen: Screen) -> None:
    # Um unico open() cobre campos + atalhos numa so carga de pagina. No
    # nicegui 3 o Screen registra as rotas do main_file uma vez; reabrir /login
    # num SEGUNDO teste de browser cai em rota nao registrada ("not found").
    # Consolidar as assercoes num teste evita esse quirk de isolamento sem
    # perder cobertura (a pagina de login e renderizada e verificada por
    # inteiro).
    screen.open("/login")
    screen.should_contain("Entrar")
    screen.should_contain("E-mail")
    screen.should_contain("Senha")
    screen.should_contain("Admin")
    screen.should_contain("Atendente")
    screen.should_contain("Mecanico")
    screen.close()
