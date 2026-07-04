"""Pagina de gestao de itens de estoque."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from ui.auth_guard import exige_autenticacao
from ui.cliente_api import ApiError, NaoAutenticadoError
from ui.componentes.cabecalho import CabecalhoApp
from ui.componentes.dialogo_confirmacao import confirmar
from ui.componentes.listagem import rodape_contagem
from ui.componentes.notificacoes import notificar_erro_api
from ui.formatacao import formatar_dinheiro_br

if TYPE_CHECKING:
    from collections.abc import Callable


_LIMITE_BAIXO = 5


def _quantidade_estoque_valida(valor: Any) -> int | None:  # noqa: ANN401  # ui.number
    """Normaliza ``ui.number().value`` de quantidade de estoque em int >= 0.

    Mesmo padrao de ``_quantidade_valida`` (ordens_servico), mas aceitando
    zero (estoque zerado e estado legitimo). Campo vazio/invalido retorna
    ``None`` pra caller notificar — antes ``int(value or 0)`` zerava o
    estoque silenciosamente quando o usuario apagava o campo e salvava.
    """
    if valor is None or valor == "":
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


@ui.page("/estoque")
@exige_autenticacao
def pagina_estoque() -> None:
    CabecalhoApp()

    with ui.column().classes("p-8 gap-4 w-full"):
        ui.label("Estoque").classes("text-2xl font-bold")

        container = ui.column().classes("w-full")

        def refresh() -> None:
            container.clear()
            with container:
                _renderizar(refresh)

        ui.button(
            "Novo item",
            icon="add",
            on_click=lambda: _dialog_item(None, refresh),
        ).classes("bg-blue-600 text-white")
        refresh()


def _renderizar(on_refresh: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        dados = obter_api().listar_estoque()
    except NaoAutenticadoError:
        ui.navigate.to("/login")
        return
    except ApiError as exc:
        ui.label(f"Erro: {exc}").classes("text-red-600")
        return

    for item in dados.get("items", []):
        quantidade = int(item.get("quantidade", 0))
        classes = "w-full"
        if quantidade <= _LIMITE_BAIXO:
            classes += " bg-yellow-50"
        with ui.card().classes(classes):
            with ui.row().classes("items-center gap-4 w-full"):
                ui.label(item["nome"]).classes("font-bold flex-1")
                ui.label(formatar_dinheiro_br(item.get("preco_unitario"))).classes(
                    "text-sm"
                )
                _controle_quantidade(item, on_refresh)
                ui.button(
                    icon="edit",
                    on_click=lambda i=item: _dialog_item(i, on_refresh),
                ).props("flat dense")
                ui.button(
                    icon="delete",
                    on_click=lambda i=item: _confirmar_desativar(i, on_refresh),
                ).props("flat dense")
            if item.get("descricao"):
                ui.label(item["descricao"]).classes("text-xs text-gray-600")
            if quantidade <= _LIMITE_BAIXO:
                ui.label("Estoque baixo").classes("text-xs text-yellow-800")
    rodape_contagem(dados)


def _controle_quantidade(item: dict[str, Any], on_refresh: Callable[[], None]) -> None:
    item_id = str(item["id"])
    qty_input = ui.number(
        "Qtd",
        value=int(item.get("quantidade", 0)),
        min=0,
        step=1,
    ).classes("w-24")

    def salvar_quantidade() -> None:
        qtd = _quantidade_estoque_valida(qty_input.value)
        if qtd is None:
            ui.notify("Informe uma quantidade valida (>= 0).", type="warning")
            return
        _ajustar(item_id, qtd, on_refresh)

    ui.button(icon="save", on_click=salvar_quantidade).props("flat dense")


def _ajustar(
    item_id: str, nova_quantidade: int, on_refresh: Callable[[], None]
) -> None:
    from ui.app import obter_api

    try:
        obter_api().ajustar_quantidade(item_id, nova_quantidade)
        ui.notify("Quantidade atualizada", type="positive")
        on_refresh()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")


def _confirmar_desativar(item: dict[str, Any], on_refresh: Callable[[], None]) -> None:
    item_id = str(item["id"])
    confirmar(
        titulo="Desativar item",
        mensagem=f"Desativar {item['nome']}?",
        perigoso=True,
        on_confirmar=lambda: _desativar(item_id, on_refresh),
    )


def _dialog_item(item: dict[str, Any] | None, on_sucesso: Callable[[], None]) -> None:
    from ui.app import obter_api

    titulo = "Editar item" if item else "Novo item"
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(titulo).classes("text-lg font-bold")
        nome = ui.input("Nome", value=(item or {}).get("nome", "")).classes("w-full")
        descricao = ui.input(
            "Descricao", value=(item or {}).get("descricao", "")
        ).classes("w-full")
        preco = ui.number(
            "Preco unitario",
            # Backend exige preco_unitario > 0; 0.01 e o minimo real — antes o
            # default 0 de "Novo item" ja nascia invalido (422 garantido).
            value=float((item or {}).get("preco_unitario") or 0.01),
            min=0.01,
            step=0.01,
        ).classes("w-full")
        qty_field = None
        if item is None:
            qty_field = ui.number(
                "Quantidade inicial",
                value=0,
                min=0,
                step=1,
            ).classes("w-full")

        def salvar() -> None:
            # Backend exige descricao min_length=1 e preco_unitario > 0.
            body: dict[str, Any] = {
                "nome": nome.value,
                "descricao": descricao.value,
                "preco_unitario": preco.value,
            }
            if qty_field is not None:
                qtd = _quantidade_estoque_valida(qty_field.value)
                if qtd is None:
                    ui.notify(
                        "Informe uma quantidade inicial valida (>= 0).",
                        type="warning",
                    )
                    return
                body["quantidade"] = qtd
            try:
                if item:
                    obter_api().atualizar_item_estoque(item["id"], body)
                else:
                    obter_api().criar_item_estoque(body)
                dialog.close()
                ui.notify("Salvo", type="positive")
                on_sucesso()
            except ApiError as exc:
                notificar_erro_api(exc)

        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")
            ui.button("Salvar", on_click=salvar).classes("bg-blue-600 text-white")
    # Sem delete o dialog acumula no layout a cada abertura.
    dialog.on("hide", dialog.delete)
    dialog.open()


def _desativar(item_id: str, on_sucesso: Callable[[], None]) -> None:
    from ui.app import obter_api

    try:
        obter_api().desativar_item_estoque(item_id)
        ui.notify("Item desativado", type="positive")
        on_sucesso()
    except ApiError as exc:
        ui.notify(f"Erro: {exc}", type="negative")
