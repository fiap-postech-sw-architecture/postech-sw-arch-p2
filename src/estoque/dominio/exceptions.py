from __future__ import annotations

from src.compartilhado.dominio.exceptions import EntidadeNaoEncontradaException


class ItemEstoqueNaoEncontradoException(EntidadeNaoEncontradaException):
    def __init__(self, mensagem: str = "Item de estoque nao encontrado") -> None:
        super().__init__(mensagem=mensagem)
