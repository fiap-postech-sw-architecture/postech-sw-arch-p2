"""Excecoes de dominio do contexto Ordem de Servico."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.dominio.exceptions import EntidadeNaoEncontradaException

if TYPE_CHECKING:
    from uuid import UUID


class OrdemNaoEncontradaException(EntidadeNaoEncontradaException):
    """Levantada quando uma OrdemDeServico nao existe no repositorio.

    O ``ordem_id`` (quando informado) e incluido na mensagem para
    facilitar diagnostico em logs e respostas de API.
    """

    def __init__(
        self,
        ordem_id: UUID | None = None,
        mensagem: str | None = None,
    ) -> None:
        if mensagem is None:
            mensagem = (
                f"Ordem de servico {ordem_id} nao encontrada"
                if ordem_id is not None
                else "Ordem de servico nao encontrada"
            )
        super().__init__(mensagem=mensagem)


class ItemDaOrdemNaoEncontradoException(EntidadeNaoEncontradaException):
    """Levantada quando o item referenciado nao existe na ordem.

    Quando informados, ``ordem_id`` e ``item_id`` sao incluidos na
    mensagem padrao para diagnostico.
    """

    def __init__(
        self,
        ordem_id: UUID | None = None,
        item_id: UUID | None = None,
        mensagem: str | None = None,
    ) -> None:
        if mensagem is None:
            if ordem_id is not None and item_id is not None:
                mensagem = (
                    f"Item {item_id} nao encontrado na ordem de servico {ordem_id}"
                )
            else:
                mensagem = "Item da ordem nao encontrado"
        super().__init__(mensagem=mensagem)
