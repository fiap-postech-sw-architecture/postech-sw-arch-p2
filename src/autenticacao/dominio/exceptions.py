from __future__ import annotations

from src.compartilhado.dominio.exceptions import (
    EntidadeDuplicadaException,
    FalhaAutenticacaoException,
)


class CredenciaisInvalidasException(FalhaAutenticacaoException):
    def __init__(self, mensagem: str = "Credenciais invalidas") -> None:
        super().__init__(mensagem=mensagem)


class EmailDuplicadoException(EntidadeDuplicadaException):
    def __init__(self, mensagem: str = "Email ja cadastrado") -> None:
        super().__init__(mensagem=mensagem)


class TokenInvalidoException(FalhaAutenticacaoException):
    def __init__(self, mensagem: str = "Token invalido") -> None:
        super().__init__(mensagem=mensagem)


class TokenExpiradoException(FalhaAutenticacaoException):
    def __init__(self, mensagem: str = "Token expirado") -> None:
        super().__init__(mensagem=mensagem)


class TokenRevogadoException(FalhaAutenticacaoException):
    def __init__(self, mensagem: str = "Token revogado") -> None:
        super().__init__(mensagem=mensagem)
