"""Ponto de entrada da UI NiceGUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from ui.cliente_api import ClienteApi, criar_http_client
from ui.config import CONFIG
from ui.estado import StateStore, configurar_store

if TYPE_CHECKING:
    import httpx


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


def _configurar_estado() -> None:
    configurar_store(StateStore(user_storage=_NiceguiStorageAdapter()))


# httpx.Client compartilhado do processo: thread-safe, reusa conexoes TCP
# entre requests/handlers em vez de abrir e vazar um pool por chamada de
# ``obter_api()``. Lazy pra testes importarem o modulo sem abrir client.
_http_client: httpx.Client | None = None


def _obter_http_client() -> httpx.Client:
    global _http_client  # noqa: PLW0603  # singleton lazy do processo
    if _http_client is None:
        _http_client = criar_http_client(CONFIG.backend_url)
    return _http_client


def _fechar_http_client() -> None:
    """Fecha o client compartilhado no shutdown do NiceGUI."""
    global _http_client  # noqa: PLW0603  # singleton lazy do processo
    if _http_client is not None:
        _http_client.close()
        _http_client = None


def obter_api() -> ClienteApi:
    """Factory do cliente HTTP — instancia nova, client httpx compartilhado.

    Sem ``@cache`` no ClienteApi: o decorator congelaria a primeira instancia
    (incluindo o ``StateStore`` resolvido via fallback no ``__init__``) e
    prenderia um store errado se ``obter_api()`` rodasse antes de
    ``_configurar_estado()`` (cenario plausivel em testes futuros que
    importem a factory direto). Construir ``ClienteApi`` e barato; o que era
    caro — o pool de conexoes do ``httpx.Client`` — agora e compartilhado
    (``_obter_http_client``) e fechado no shutdown do app.
    """
    return ClienteApi(base_url=CONFIG.backend_url, http_client=_obter_http_client())


def executar() -> None:
    _configurar_estado()
    app.on_shutdown(_fechar_http_client)
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
