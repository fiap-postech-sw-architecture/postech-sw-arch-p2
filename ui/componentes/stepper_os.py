"""Visualizacao horizontal do ciclo de vida da OS."""

from __future__ import annotations

from nicegui import ui

from src.ordem_servico.dominio.status import StatusOrdem

# Ordem visual do happy path.
_HAPPY_PATH: list[StatusOrdem] = [
    StatusOrdem.RECEBIDA,
    StatusOrdem.EM_DIAGNOSTICO,
    StatusOrdem.AGUARDANDO_APROVACAO,
    StatusOrdem.EM_EXECUCAO,
    StatusOrdem.FINALIZADA,
    StatusOrdem.ENTREGUE,
]

_ROTULOS: dict[StatusOrdem, str] = {
    StatusOrdem.RECEBIDA: "Recebida",
    StatusOrdem.EM_DIAGNOSTICO: "Em Diag.",
    StatusOrdem.AGUARDANDO_APROVACAO: "Ag. Aprov.",
    StatusOrdem.EM_EXECUCAO: "Em Execucao",
    StatusOrdem.FINALIZADA: "Finalizada",
    StatusOrdem.ENTREGUE: "Entregue",
    StatusOrdem.CANCELADA: "Cancelada",
    StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR: "Ag. Aprov. Comp.",
}


class StepperOs:
    """Renderiza o stepper horizontal do ciclo de vida.

    status_atual: o estado corrente da OS.
    """

    def __init__(self, status_atual: StatusOrdem) -> None:
        with ui.row().classes("items-center gap-2 w-full"):
            for i, estado in enumerate(_HAPPY_PATH):
                self._render_etapa(estado, status_atual)
                if i < len(_HAPPY_PATH) - 1:
                    ui.label("→").classes("text-gray-400")

            if status_atual == StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR:
                ui.label("↕").classes("text-blue-500 mx-2")
                self._render_etapa(status_atual, status_atual)

            if status_atual == StatusOrdem.CANCELADA:
                ui.label("⇢").classes("text-red-500 mx-2")
                self._render_etapa(status_atual, status_atual)

    def _render_etapa(self, estado: StatusOrdem, status_atual: StatusOrdem) -> None:
        rotulo = _ROTULOS.get(estado, estado.value)
        atual = estado == status_atual
        passado = _eh_passado(estado, status_atual)
        if estado == StatusOrdem.CANCELADA and status_atual == StatusOrdem.CANCELADA:
            classes = "bg-red-500 text-white"
        elif estado == StatusOrdem.ENTREGUE and status_atual == StatusOrdem.ENTREGUE:
            classes = "bg-green-600 text-white"
        elif atual:
            classes = "bg-blue-600 text-white font-bold"
        elif passado:
            classes = "bg-gray-300 text-gray-700"
        else:
            classes = "border border-gray-300 text-gray-400"
        ui.label(rotulo).classes(f"px-3 py-1 rounded {classes}")


def _eh_passado(estado: StatusOrdem, atual: StatusOrdem) -> bool:
    try:
        return _HAPPY_PATH.index(estado) < _HAPPY_PATH.index(atual)
    except ValueError:
        return False
