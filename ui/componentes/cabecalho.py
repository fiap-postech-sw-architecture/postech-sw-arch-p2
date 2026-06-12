"""Cabecalho fixo da UI: nav, role switcher, identidade e logout."""

from __future__ import annotations

from nicegui import ui

from ui.config import CONFIG, Papel
from ui.estado import obter_store

_CORES_PAPEL: dict[Papel, str] = {
    "admin": "bg-red-600",
    "atendente": "bg-blue-600",
    "mecanico": "bg-green-600",
}

_NAV_ITEMS: list[tuple[str, str]] = [
    ("Dashboard", "/"),
    ("Clientes", "/clientes"),
    ("Catalogo", "/catalogo"),
    ("Estoque", "/estoque"),
    ("OS", "/ordens-servico"),
    ("Acompanhamento", "/acompanhamento"),
]


class CabecalhoApp:
    """Renderiza o cabecalho fixo. Chame no topo de cada @ui.page."""

    def __init__(self) -> None:
        store = obter_store()
        papel = store.papel_atual()
        with (
            ui.header().classes("bg-gray-800 text-white shadow"),
            ui.row().classes("items-center w-full gap-4 px-4"),
        ):
            ui.label("PytStop").classes("text-xl font-bold")
            with ui.row().classes("gap-2"):
                for label, path in _NAV_ITEMS:
                    ui.link(label, path).classes("text-white no-underline px-2")

            ui.space()

            if papel:
                self._renderizar_switcher(papel, store.email_atual() or "")
            else:
                ui.link("Login", "/login").classes("text-white")

    def _renderizar_switcher(self, papel_atual: Papel, email: str) -> None:
        ui.badge(papel_atual, color=None).classes(
            f"{_CORES_PAPEL[papel_atual]} text-white px-3 py-1"
        )
        ui.label(email).classes("text-sm text-gray-300")
        papeis = list(CONFIG.usuarios_seed.keys())
        # Quasar q-select no header escuro: `dark` flipa a paleta pra texto
        # claro em fundo escuro (label, input, arrow). `outlined dense`
        # mantem o controle compacto e com borda visivel. Sem `dark` o label
        # "Trocar papel" e o valor atual ficam quase invisiveis no bg-gray-800.
        select = (
            ui.select(
                papeis,
                value=papel_atual,
                label="Trocar papel",
            )
            .props("dark outlined dense")
            .classes("w-40")
        )
        select.on_value_change(lambda e: self._trocar_papel(e.value))
        ui.button("Logout", on_click=self._logout).classes("bg-gray-600")

    def _trocar_papel(self, novo_papel: Papel) -> None:
        from ui.app import obter_api
        from ui.cliente_api import ApiError

        api = obter_api()
        api.logout()
        usuario = CONFIG.usuarios_seed[novo_papel]
        try:
            api.login(email=usuario.email, senha=usuario.senha)
            ui.navigate.reload()
        except ApiError as exc:
            ui.notify(f"Falha ao trocar papel: {exc}", type="negative")

    def _logout(self) -> None:
        from ui.app import obter_api

        obter_api().logout()
        ui.navigate.to("/login")
