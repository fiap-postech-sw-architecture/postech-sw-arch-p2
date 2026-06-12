"""Redireciona para /login quando o usuario nao esta autenticado."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

from nicegui import ui

from ui.estado import obter_store

if TYPE_CHECKING:
    from collections.abc import Callable


def exige_autenticacao[**P, R](func: Callable[P, R]) -> Callable[P, R | None]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
        if not obter_store().esta_autenticado():
            ui.navigate.to("/login")
            return None
        return func(*args, **kwargs)

    return wrapper
