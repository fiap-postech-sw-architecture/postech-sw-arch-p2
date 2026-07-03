"""Helpers compartilhados das paginas de listagem."""

from __future__ import annotations

from typing import Any

from nicegui import ui


def rodape_contagem(dados: dict[str, Any]) -> None:
    """Rodape "Mostrando X de Y" quando a listagem veio truncada pelo limit.

    O backend ja devolve ``total`` junto com ``items``; sem este rodape a
    pagina aparentava conter TODOS os registros mesmo com o default de 20.
    Paginacao real fica como melhoria futura — aqui so tornamos o corte
    visivel.
    """
    itens = dados.get("items", [])
    try:
        total = int(dados.get("total") or 0)
    except TypeError, ValueError:
        return
    if total > len(itens):
        ui.label(f"Mostrando {len(itens)} de {total} registros.").classes(
            "text-xs text-gray-500"
        )
