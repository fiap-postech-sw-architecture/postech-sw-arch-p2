"""Pagina de login com atalhos para os 3 papeis seed."""

from __future__ import annotations

from nicegui import ui

from ui.cliente_api import ApiError, BackendInacessivelError
from ui.config import CONFIG, Papel
from ui.estado import obter_store


@ui.page("/login")
def pagina_login() -> None:
    store = obter_store()
    if store.esta_autenticado():
        ui.navigate.to("/")
        return

    with ui.column().classes("absolute-center items-center gap-4 w-96"):
        ui.label("PytStop").classes("text-3xl font-bold")
        ui.label("UI de Simulacao").classes("text-gray-500")

        email_input = ui.input("E-mail").classes("w-full")
        senha_input = ui.input("Senha", password=True).classes("w-full")

        status_backend = ui.label("").classes("text-sm")
        _checar_backend(status_backend)

        alerta_seed = ui.column().classes("w-full")
        _checar_usuarios_seed(alerta_seed)

        ui.button(
            "Entrar",
            on_click=lambda: _entrar(email_input.value, senha_input.value),
        ).classes("w-full")

        ui.separator()
        ui.label("Atalhos (dev)").classes("text-sm text-gray-500")
        with ui.row().classes("gap-2 w-full justify-center"):
            for papel in ("admin", "atendente", "mecanico"):
                ui.button(
                    papel.capitalize(),
                    on_click=lambda p=papel: _entrar_como_seed(p),
                ).classes("flex-1")


def _checar_backend(label: ui.label) -> None:
    from ui.app import obter_api

    try:
        obter_api().get("/api/v1/saude")
        label.set_text("Backend online")
        label.classes(replace="text-sm text-green-600")
    except BackendInacessivelError:
        label.set_text(f"Backend offline em {CONFIG.backend_url}")
        label.classes(replace="text-sm text-red-600")
    except ApiError:
        label.set_text("Backend indisponivel")
        label.classes(replace="text-sm text-orange-600")


def _checar_usuarios_seed(alerta: ui.column) -> None:
    """Detecta se o usuario admin seed existe no banco.

    Usa ``ClienteApi.tentar_login_sem_salvar`` (que nao altera a sessao)
    para testar se o admin seed existe. Mostra aviso APENAS se backend
    responder 401 — outros cenarios (backend offline, 5xx) sao silenciosos
    aqui porque ``_checar_backend`` ja indica o problema.
    """
    from ui.app import obter_api

    usuario_admin = CONFIG.usuarios_seed["admin"]
    status = obter_api().tentar_login_sem_salvar(
        email=usuario_admin.email, senha=usuario_admin.senha
    )
    if status != 401:
        return

    alerta.clear()
    with alerta:
        ui.label(
            "Usuarios seed nao encontrados no banco. "
            "Rode 'make seed-users' (ou 'make seed-users-docker') "
            "antes de continuar."
        ).classes("text-orange-600 text-sm")


def _entrar(email: str, senha: str) -> None:
    from ui.app import obter_api

    try:
        obter_api().login(email=email, senha=senha)
        ui.navigate.to("/")
    except ApiError as exc:
        ui.notify(f"Falha no login: {exc}", type="negative")


def _entrar_como_seed(papel: Papel) -> None:
    usuario = CONFIG.usuarios_seed[papel]
    _entrar(usuario.email, usuario.senha)
