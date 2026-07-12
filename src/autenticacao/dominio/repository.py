from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.usuario import Usuario


class UsuarioRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        """Busca o usuario pelo id; None se nao existir."""
        pass

    def obter_por_email(self, email: str) -> Usuario | None:
        """Busca o usuario pelo e-mail exato; None se nao existir."""
        pass

    def salvar(self, usuario: Usuario) -> None:
        """Adiciona o usuario a sessao e faz flush imediato."""
        pass

    def email_existe(self, email: str) -> bool:
        """True se ja existe usuario cadastrado com este e-mail."""
        pass


class TokenRevogadoRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def revogar(self, jti: str) -> bool:
        """Revoga o jti. True se revogou agora; False se ja estava revogado."""
        pass

    def esta_revogado(self, jti: str) -> bool:
        """True se o jti consta na lista de tokens revogados."""
        pass
