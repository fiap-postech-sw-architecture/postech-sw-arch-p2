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
    """Cliente referenciado na criacao da OS nao existe no contexto Cliente.

    O ``cliente_id`` (quando informado) e incluido na mensagem para
    facilitar diagnostico em logs e respostas de API (UUID, nao-PII).
    """

    def __init__(
        self,
        cliente_id: UUID | None = None,
        mensagem: str | None = None,
    ) -> None:
        if mensagem is None:
            mensagem = (
                f"Cliente {cliente_id} nao encontrado"
                if cliente_id is not None
                else "Cliente nao encontrado"
            )
        super().__init__(mensagem=mensagem)


class VeiculoNaoEncontradoException(EntidadeNaoEncontradaException):
    """Veiculo referenciado na OS nao existe ou nao pertence ao cliente.

    Os dois casos (veiculo inexistente vs veiculo de outro cliente) sao
    indistinguiveis na resposta para preservar defesa em profundidade — ver
    ``CriarOrdem`` em aplicacao/use_cases.py. O ``veiculo_id`` (quando
    informado, UUID nao-PII) entra na mensagem SEM revelar qual dos dois
    casos ocorreu.
    """

    def __init__(
        self,
        veiculo_id: UUID | None = None,
        mensagem: str | None = None,
    ) -> None:
        if mensagem is None:
            mensagem = (
                f"Veiculo {veiculo_id} nao encontrado para o cliente informado"
                if veiculo_id is not None
                else "Veiculo nao encontrado para o cliente informado"
            )
        super().__init__(mensagem=mensagem)
