"""Pagina de catalogo de servicos."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.dialogo_confirmacao import confirmar

if TYPE_CHECKING:
    from collections.abc import Callable


def _formatar_preco_servico(preco_raw: Any) -> str:
    """Formata preco de servico no padrao ``R$ X.XX``.

    Backend serializa ``Decimal`` como string JSON (ex.: ``"280.00"``). Usar
    direto em f-string com ``:.2f`` levanta ``TypeError`` — por isso o cast
    explicito para ``float``. Aceita ``None``/``""`` como zero (defensivo).
    """
    return f"R$ {float(preco_raw or 0):.2f}"


@ui.page("/catalogo")
@exige_autenticacao
def pagina_catalogo() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Catalogo de Servicos").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar(refresh)

        ui.button(
            "Novo servico",
            icon="add",
            on_click=lambda: _dialog_servico(None, refresh),
        ).classes("bg-blue-600 text-white")
        refresh()


def _renderizar(on_refresh: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().listar_servicos()
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for servico in dados.get("items", []):
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label(servico["nome"]).classes("font-bold flex-1")
                ui.label(_formatar_preco_servico(servico.get("preco", 0)))
                ui.button(
                    icon="edit",
                    on_click=lambda s=servico: _dialog_servico(s, on_refresh),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda s=servico: _confirmar_desativar(s, on_refresh),
                ).props("flat dense")
            if servico.get("descricao"):
                ui.label(servico["descricao"]).classes("text-sm text-gray-600")


def _confirmar_desativar(
    servico: dict[str, Any], on_refresh: Callable[[], None]
) -> None:
    servico_id = str(servico["id"])
    confirmar(
        titulo="Desativar servico",
        mensagem=f"Desativar {servico['nome']}?",
        perigoso=True,
        on_confirmar=lambda: _desativar(servico_id, on_refresh),
    )


def _dialog_servico(
    servico: dict[str, Any] | None, on_sucesso: Callable[[], None]
) -> None:
    from ui.app import obter_api

    titulo = "Editar servico" if servico else "Novo servico"
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(titulo).classes("text-lg font-bold")
        nome = ui.input("Nome", value=(servico or {}).get("nome", "")).classes("w-full")
        descricao = ui.textarea(
            "Descricao", value=(servico or {}).get("descricao", "")
        ).classes("w-full")
        preco = ui.number(
            "Preco",
            # Backend exige preco > 0 (Field(gt=0)); 0.01 reflete o minimo real.
            value=float((servico or {}).get("preco", 0.01)),
            min=0.01,
            step=0.01,
        ).classes("w-full")

        def salvar() -> None:
            body = {
                "nome": nome.value,
                "descricao": descricao.value,
                "preco": preco.value,
            }
            try:
                if servico:
                    obter_api().atualizar_servico(servico["id"], body)
                else:
                    obter_api().criar_servico(body)
                dialog.close()
                ui.notify("Salvo", type="positive")
                on_sucesso()
            except ApiError as exc:
                ui.notify(f"Erro: {exc}", type="negative")

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    dialog.open()


def _desativar(servico_id: str, on_sucesso: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        obter_api().desativar_servico(servico_id)
        ui.notify("Servico desativado", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
