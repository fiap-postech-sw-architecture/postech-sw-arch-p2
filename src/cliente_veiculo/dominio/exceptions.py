from __future__ import annotations

from src.compartilhado.dominio.exceptions import (
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
)


class ClienteNaoEncontradoException(EntidadeNaoEncontradaException):
    """Levantada quando uma busca por Cliente retorna vazia."""

    def __init__(self, mensagem: str = "Cliente nao encontrado") -> None:
        super().__init__(mensagem=mensagem)


class VeiculoNaoEncontradoException(EntidadeNaoEncontradaException):
    """Levantada quando um Veiculo nao existe no agregado Cliente esperado."""

    def __init__(self, mensagem: str = "Veiculo nao encontrado") -> None:
        super().__init__(mensagem=mensagem)


class PlacaDuplicadaException(EntidadeDuplicadaException):
    """Levantada quando uma placa ja esta cadastrada (em qualquer cliente)."""

    def __init__(self, mensagem: str = "Placa ja cadastrada") -> None:
        super().__init__(mensagem=mensagem)


class DocumentoDuplicadoException(EntidadeDuplicadaException):
    """Levantada quando um CPF ou CNPJ ja esta cadastrado em outro cliente."""

    def __init__(self, mensagem: str = "Documento ja cadastrado") -> None:
        super().__init__(mensagem=mensagem)


class ConsentimentoNaoEncontradoException(EntidadeNaoEncontradaException):
    """Levantada quando um consentimento nao existe para o par cliente+tipo."""

    def __init__(self, mensagem: str = "Consentimento nao encontrado") -> None:
        super().__init__(mensagem=mensagem)
