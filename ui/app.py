"""Ponto de entrada da UI NiceGUI."""

from __future__ import annotations

from nicegui import app, ui

# Registro de paginas: o decorator @ui.page executa ao importar.
# `import X as _` evita rebindar o nome `ui` (ja importado de nicegui).
import ui.paginas.acompanhamento as _pagina_acompanhamento  # noqa: F401
import ui.paginas.catalogo as _pagina_catalogo  # noqa: F401
import ui.paginas.clientes as _pagina_clientes  # noqa: F401
import ui.paginas.dashboard as _pagina_dashboard  # noqa: F401
import ui.paginas.estoque as _pagina_estoque  # noqa: F401
import ui.paginas.login as _pagina_login  # noqa: F401
import ui.paginas.ordens_servico as _pagina_ordens_servico  # noqa: F401
from ui.cliente_api import ClienteApi
from ui.config import CONFIG
from ui.estado import StateStore, configurar_store


class _NiceguiStorageAdapter:
    """Proxy lazy para ``nicegui.app.storage.user``.

    O storage e resolvido por chamada (nao capturado no __init__) porque
    o cookie criptografado depende do request context — congelar a
    referencia no startup quebraria isolamento entre clientes.
    """

    def get(self, key: str, default: object = None) -> object:
        return app.storage.user.get(key, default)

    def __setitem__(self, key: str, value: object) -> None:
        app.storage.user[key] = value

    def clear(self) -> None:
        app.storage.user.clear()


def _configurar_estado() -> None:
    configurar_store(StateStore(user_storage=_NiceguiStorageAdapter()))


def obter_api() -> ClienteApi:
    """Factory do cliente HTTP — uma instancia nova por chamada.

    Sem ``@cache``: o decorator congelaria a primeira instancia (incluindo
    o ``StateStore`` resolvido via fallback no ``__init__``) e prenderia
    um store errado se ``obter_api()`` rodasse antes de
    ``_configurar_estado()`` (cenario plausivel em testes futuros que
    importem a factory direto). Construir ``ClienteApi`` e barato — nao
    abre conexao HTTP — entao o custo do cache nao se paga (issue #85).
    """
    return ClienteApi(base_url=CONFIG.backend_url)


def executar() -> None:
    _configurar_estado()
    ui.run(
        title="PytStop UI",
        port=CONFIG.ui_port,
        storage_secret=CONFIG.storage_secret,
        # reload=False: NiceGUI reload forks um subprocesso que reimporta a
        # entry; em `python -m ui` isso nao funciona direito (ver commit 135fcb7).
        # Hot-reload em dev pode ser feito via supervisor externo.
        reload=False,
        show=False,
        favicon="🔧",
    )
