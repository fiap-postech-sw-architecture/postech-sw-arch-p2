"""Dropdown generico populado via endpoint de listagem com cache TTL."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from nicegui import ui

from ui.cliente_api import ApiError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class CacheRecursos:
    ttl_seg: int
    fetcher: Callable[[], list[dict[str, Any]]]
    _cache: list[dict[str, Any]] | None = None
    _expira_em: float = 0.0

    def obter(self) -> list[dict[str, Any]]:
        if self._cache is not None and time.monotonic() < self._expira_em:
            return self._cache
        self._cache = self.fetcher()
        self._expira_em = time.monotonic() + self.ttl_seg
        return self._cache

    def invalidar(self) -> None:
        self._cache = None
        self._expira_em = 0.0


class PickerRecurso:
    """Dropdown pra escolher um recurso por id.

    Uso:
        picker = PickerRecurso(
            rotulo="Cliente",
            fetcher=lambda: api.get("/api/v1/clientes", params={"limit": 100})["items"],
            campo_label="nome",
        )
        # picker.valor() retorna o id selecionado (UUID str) ou None
    """

    def __init__(
        self,
        *,
        rotulo: str,
        fetcher: Callable[[], list[dict[str, Any]]],
        campo_label: str = "nome",
        campo_id: str = "id",
        ttl_seg: int = 30,
    ) -> None:
        self._campo_id = campo_id
        self._campo_label = campo_label
        self._rotulo = rotulo
        self._cache = CacheRecursos(ttl_seg=ttl_seg, fetcher=fetcher)
        options = self._obter_opcoes()
        with ui.row().classes("items-end gap-2"):
            self._select = ui.select(
                options=options,
                label=rotulo,
                with_input=True,
                clearable=True,
            ).classes("min-w-60")
            ui.button(icon="refresh", on_click=self._refresh).props("flat dense")

    def _obter_opcoes(self) -> dict[str, str]:
        try:
            itens = self._cache.obter()
        except ApiError as exc:
            logger.warning(
                "PickerRecurso falhou ao listar %s: %s (%s)",
                self._rotulo,
                exc,
                type(exc).__name__,
            )
            ui.notify(
                f"Falha ao listar {self._rotulo}: {exc}",
                type="negative",
            )
            return {}
        return {str(i[self._campo_id]): str(i[self._campo_label]) for i in itens}

    def _refresh(self) -> None:
        self._cache.invalidar()
        self._select.options = self._obter_opcoes()
        self._select.update()

    def valor(self) -> str | None:
        return cast("str | None", self._select.value)

    def set_disabled(self, disabled: bool) -> None:
        self._select.props(f"disable={str(disabled).lower()}")

    def on_change(self, callback: Callable[[], None]) -> None:
        """Registra callback para mudanca de selecao.

        Chamador recebe notificacao sem o evento cru do NiceGUI —
        mantem o Picker desacoplado da API de eventos do framework.
        """
        self._select.on_value_change(lambda _e: callback())
