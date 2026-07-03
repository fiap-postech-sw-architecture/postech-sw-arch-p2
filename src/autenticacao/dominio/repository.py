from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.usuario import Usuario


class UsuarioRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        pass

    def obter_por_email(self, email: str) -> Usuario | None:
        pass

    def salvar(self, usuario: Usuario) -> None:
        pass

    def email_existe(self, email: str) -> bool:
        pass


class TokenRevogadoRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def revogar(self, jti: str) -> bool:
        """Revoga o jti. True se revogou agora; False se ja estava revogado."""
        pass

    def esta_revogado(self, jti: str) -> bool:
        pass
