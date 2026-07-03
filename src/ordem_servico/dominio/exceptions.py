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


class ClienteNaoEncontradoException(EntidadeNaoEncontradaException):
    """Cliente referenciado na criacao da OS nao existe no contexto Cliente."""

    def __init__(self, mensagem: str = "Cliente nao encontrado") -> None:
        super().__init__(mensagem=mensagem)


class VeiculoNaoEncontradoException(EntidadeNaoEncontradaException):
    """Veiculo referenciado na OS nao existe ou nao pertence ao cliente.

    Os dois casos (veiculo inexistente vs veiculo de outro cliente) sao
    indistinguiveis na resposta para preservar defesa em profundidade — ver
    ``CriarOrdem`` em aplicacao/use_cases.py.
    """

    def __init__(
        self,
        mensagem: str = "Veiculo nao encontrado para o cliente informado",
    ) -> None:
        super().__init__(mensagem=mensagem)
