from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class PasswordHasherPort(Protocol):
    """Porta de hashing/verificacao de senha; implementacao na infraestrutura.

    Mantem a aplicacao desacoplada da biblioteca de hashing (pwdlib/bcrypt): os
    use cases dependem deste Protocol, nunca do modulo de infraestrutura.
    """

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def hash_senha(self, senha: str) -> str:
        """Gera o hash da senha em texto plano (valida tamanho minimo/maximo)."""
        pass

    def verificar_senha(self, senha_plana: str, senha_hash: str) -> bool:
        """Confere se a senha em texto plano corresponde ao hash armazenado."""
        pass


class JWTServicePort(Protocol):
    """Porta de emissao/validacao de tokens JWT; implementacao na infraestrutura."""

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def gerar_access_token(self, usuario_id: UUID, email: str, papel: str) -> str:
        """Emite um access token assinado para o usuario."""
        pass

    def gerar_refresh_token(self, usuario_id: UUID) -> str:
        """Emite um refresh token assinado para o usuario."""
        pass

    def validar_token(self, token: str) -> dict[str, object]:
        """Decodifica e valida o token e retorna o payload; levanta se invalido."""
        pass
