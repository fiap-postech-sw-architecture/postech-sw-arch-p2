from __future__ import annotations

from src.compartilhado.dominio.exceptions import EntidadeNaoEncontradaException


class ServicoNaoEncontradoException(EntidadeNaoEncontradaException):
    def __init__(self, mensagem: str = "Servico nao encontrado") -> None:
        super().__init__(mensagem=mensagem)
