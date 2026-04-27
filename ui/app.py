"""Ponto de entrada da UI NiceGUI."""

from __future__ import annotations

from functools import cache

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
    """Adapta ``nicegui.app.storage`` ao ``_StorageProtocol`` do StateStore.

    Resiliente a ``app.storage.tab`` indisponivel: NiceGUI levanta
    ``RuntimeError`` ao acessar ``storage.tab`` sem client websocket
    conectado (ex.: render server-side de ``@ui.page`` antes do browser
    abrir o socket). Como o historico HTTP e best-effort observability
    (so faz sentido com tab viva pra exibir o drawer), tratamos como
    no-op nesse cenario em vez de propagar 500.
    """

    def __init__(self, scope: str) -> None:
        self._scope = scope

    def _backend(self) -> dict[str, object] | None:
        """Retorna o storage subjacente, ou ``None`` se indisponivel.

        ``None`` so acontece pra ``scope == "tab"`` quando nao ha client
        conectado. ``user`` storage usa cookie e funciona server-side.
        """
        if self._scope == "user":
            return app.storage.user
        if self._scope == "tab":
            try:
                return app.storage.tab
            except RuntimeError:
                # Captura ampla porque NiceGUI 2.x nao expoe um tipo
                # especifico aqui — `app.storage.tab` levanta apenas um
                # `RuntimeError` generico com a mensagem
                # "app.storage.tab can only be used with a client connection".
                # Se NiceGUI passar a expor um typed exception (ex.: a
                # `NoClientConnectedError`), apertar o except. Enquanto isso,
                # qualquer outro RuntimeError sera tratado como "tab
                # indisponivel" e perdera o registro — aceitavel porque o
                # historico HTTP e best-effort observability per-tab.
                return None
        raise ValueError(self._scope)

    def get(self, key: str, default: object = None) -> object:
        backend = self._backend()
        if backend is None:
            return default
        return backend.get(key, default)

    def __setitem__(self, key: str, value: object) -> None:
        backend = self._backend()
        if backend is None:
            return  # storage indisponivel; descarta silenciosamente
        backend[key] = value

    def clear(self) -> None:
        backend = self._backend()
        if backend is None:
            return
        backend.clear()


def _configurar_estado() -> None:
    configurar_store(
        StateStore(
            user_storage=_NiceguiStorageAdapter("user"),
            tab_storage=_NiceguiStorageAdapter("tab"),
            max_entradas_historico=CONFIG.painel_max_entradas,
        )
    )


@cache
def obter_api() -> ClienteApi:
    """Factory do cliente HTTP — cacheado: uma instancia por processo UI."""
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
