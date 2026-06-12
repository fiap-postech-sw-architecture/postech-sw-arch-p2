"""Grid de botoes para transicoes validas do estado atual da OS."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from ui.componentes.maquina_estados import (
    BotaoTransicao,
    Transicao,
    obter_transicoes_validas,
)
from ui.estado import obter_store

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.ordem_servico.dominio.status import StatusOrdem

_MOTIVO_TAMANHO_MINIMO = 10


class BotoesTransicao:
    """Renderiza botoes para transicoes validas do estado atual.

    on_executar: callback(transicao, body) -> None, chamado quando o
    usuario confirma a transicao.
    """

    def __init__(
        self,
        status_atual: StatusOrdem,
        on_executar: Callable[[Transicao, dict[str, str] | None], None],
    ) -> None:
        self._on_executar = on_executar
        papel = obter_store().papel_atual() or "sem-papel"
        botoes = obter_transicoes_validas(status_atual, papel)
        if not botoes:
            ui.label("Estado final — nenhuma transicao disponivel.").classes(
                "text-gray-500 italic"
            )
            return

        with ui.row().classes("gap-2 flex-wrap"):
            for botao in botoes:
                self._render_botao(botao)

    def _render_botao(self, botao: BotaoTransicao) -> None:
        # Usa ``color=...`` do Quasar em vez de classes Tailwind: o tema do
        # q-btn sobrescreve ``bg-*`` (perigoso ficava azul). ``color=negative``
        # / ``color=primary`` sao tokens nativos garantindo o visual correto.
        t = botao.transicao
        btn = ui.button(
            botao.rotulo,
            on_click=lambda b=botao: self._clicar(b),
        )
        if not botao.habilitado:
            btn.props("disable")
            btn.classes("opacity-50")
            btn.tooltip(botao.motivo_bloqueio or "Nao permitido")
        elif t.perigoso:
            btn.props("color=negative")
        else:
            btn.props("color=primary")

    def _clicar(self, botao: BotaoTransicao) -> None:
        if not botao.habilitado:
            return
        t = botao.transicao
        if t.pede_motivo:
            self._abrir_dialog_motivo(t)
        elif t.confirma:
            self._abrir_dialog_confirmacao(t)
        else:
            self._on_executar(t, None)

    def _abrir_dialog_motivo(self, transicao: Transicao) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"{transicao.rotulo}").classes("text-lg font-bold")
            ui.label(f"Informe o motivo (minimo {_MOTIVO_TAMANHO_MINIMO} caracteres):")
            motivo = ui.textarea().classes("w-full")

            def submeter() -> None:
                if len(motivo.value.strip()) < _MOTIVO_TAMANHO_MINIMO:
                    ui.notify(
                        f"Motivo deve ter ao menos {_MOTIVO_TAMANHO_MINIMO} caracteres",
                        type="warning",
                    )
                    return
                dialog.close()
                self._on_executar(transicao, {"motivo": motivo.value.strip()})

            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("Cancelar", on_click=dialog.close).props("flat")
                # Dialogs de motivo so aparecem em transicoes ``pede_motivo``
                # (hoje, apenas cancelamento) — tratamos como acao destrutiva.
                ui.button("Confirmar", on_click=submeter).props("color=negative")
        dialog.open()

    def _abrir_dialog_confirmacao(self, transicao: Transicao) -> None:
        from ui.componentes.dialogo_confirmacao import confirmar

        confirmar(
            titulo=transicao.rotulo,
            mensagem=f"Confirma a acao '{transicao.rotulo}'?",
            perigoso=transicao.perigoso,
            on_confirmar=lambda: self._on_executar(transicao, None),
        )
