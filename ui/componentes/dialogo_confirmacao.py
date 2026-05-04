"""Dialog generico de confirmacao pra deletes e cancelamentos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import context, ui

if TYPE_CHECKING:
    from collections.abc import Callable


def confirmar(  # noqa: PLR0913  # 6 kwargs todos opcionais por design
    *,
    titulo: str,
    mensagem: str,
    on_confirmar: Callable[[], None],
    confirmar_label: str = "Confirmar",
    cancelar_label: str = "Cancelar",
    perigoso: bool = False,
) -> None:
    """Abre um dialog modal pedindo confirmacao.

    Acoes destrutivas (``perigoso=True``) usam ``color=negative`` do Quasar
    em vez de classes Tailwind — o tema do q-btn sobrescrevia ``bg-red-600``
    e o botao ficava azul, perdendo o sinal visual de "isso apaga coisa".
    """
    # ``context.client.layout`` ancora o dialog na raiz do client. Sem isso, se
    # ``confirmar`` for chamado de dentro de um ui.menu_item, o dialog vira
    # filho do q-menu e desmonta junto quando o auto_close fecha o menu.
    with context.client.layout:
        with ui.dialog() as dialog, ui.card():
            ui.label(titulo).classes("text-lg font-bold")
            ui.label(mensagem)
            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button(cancelar_label, on_click=dialog.close).props("flat")
                btn = ui.button(
                    confirmar_label,
                    on_click=lambda: _confirmar(dialog, on_confirmar),
                )
                if perigoso:
                    btn.props("color=negative")
                else:
                    btn.props("color=primary")
        # ui.dialog so esconde no close (value=False); sem delete o node fica
        # acumulando no layout a cada nova chamada de confirmar.
        dialog.on("hide", dialog.delete)
        dialog.open()


def _confirmar(dialog: ui.dialog, callback: Callable[[], None]) -> None:
    dialog.close()
    callback()
