"""Pagina de login com atalhos para os 3 papeis seed."""

from __future__ import annotations

from http import HTTPStatus

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

        # Probe de seed + atalhos: SO no modo dev (UI_ATALHOS_DEV, default
        # true). No cloud (production) os usuarios seed nao existem por
        # design — o probe acusaria "seed nao encontrado" (ruido pra banca)
        # e os botoes de atalho falhariam o login.
        if CONFIG.atalhos_dev:
            alerta_seed = ui.column().classes("w-full")
            _checar_usuarios_seed(alerta_seed)

        ui.button(
            "Entrar",
            on_click=lambda: _entrar(email_input.value, senha_input.value),
        ).classes("w-full")

        if CONFIG.atalhos_dev:
            ui.separator()
            ui.label("Atalhos (dev)").classes("text-sm text-gray-500")
            with ui.row().classes("gap-2 w-full justify-center"):
                for papel in ("admin", "atendente", "mecanico"):
                    ui.button(
                        papel.capitalize(),
                        on_click=lambda p=papel: _entrar_como_seed(p),
                    ).classes("flex-1")

        # Rodape com SHA do commit que gerou a imagem -- bate com o que sai
        # nos logs (`>>> pytstop ui | commit XXXX...`) e com o LABEL OCI
        # `org.opencontainers.image.revision`. Util pro examinador validar
        # versao sem precisar olhar logs. So renderiza se a env var existir
        # (vazio em dev local sem build).
        if CONFIG.git_sha:
            ui.label(f"v{CONFIG.git_sha[:12]}").classes("text-xs text-gray-400 mt-4")


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


# Cache de processo do probe de usuarios seed. O probe faz um POST /login com
# as credenciais do admin seed — repetir a cada render de /login gastava rate
# limit e poluia o log de autenticacao do backend. ``None`` = ainda nao
# sondado; depois disso guarda o status HTTP retornado (a existencia do seed
# nao muda durante a vida do processo — quem rodar `make seed-users` reinicia
# ou recarrega a UI).
_probe_seed_feito = False
_probe_seed_status: int | None = None


def _status_admin_seed() -> int | None:
    """Status do login-probe do admin seed, cacheado 1x por processo.

    Retorna o status HTTP do probe ou ``None`` quando o backend esta
    inacessivel. Probe offline (``None``) NAO e cacheado: assim que o backend
    voltar, o proximo render sonda de novo — cachear a falha esconderia o
    aviso de seed ausente pra sempre.
    """
    global _probe_seed_feito, _probe_seed_status  # noqa: PLW0603  # cache de processo
    if _probe_seed_feito:
        return _probe_seed_status
    from ui.app import obter_api

    usuario_admin = CONFIG.usuarios_seed["admin"]
    status = obter_api().tentar_login_sem_salvar(
        email=usuario_admin.email, senha=usuario_admin.senha
    )
    if status is not None:
        _probe_seed_feito = True
        _probe_seed_status = status
    return status


def _checar_usuarios_seed(alerta: ui.column) -> None:
    """Detecta se o usuario admin seed existe no banco.

    Usa ``ClienteApi.tentar_login_sem_salvar`` (que nao altera a sessao)
    para testar se o admin seed existe — 1x por processo, via
    ``_status_admin_seed``. Mostra aviso APENAS se backend responder 401 —
    outros cenarios (backend offline, 5xx) sao silenciosos aqui porque
    ``_checar_backend`` ja indica o problema.
    """
    if _status_admin_seed() != HTTPStatus.UNAUTHORIZED:
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

    # Validacao no cliente: evita POST fadado ao 401/422 quando o usuario
    # clica "Entrar" com campos vazios.
    email = (email or "").strip()
    if not email or not senha:
        ui.notify("Informe e-mail e senha.", type="warning")
        return
    try:
        obter_api().login(email=email, senha=senha)
        ui.navigate.to("/")
    except ApiError as exc:
        ui.notify(f"Falha no login: {exc}", type="negative")


def _entrar_como_seed(papel: Papel) -> None:
    usuario = CONFIG.usuarios_seed[papel]
    _entrar(usuario.email, usuario.senha)
