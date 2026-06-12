from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.usuario import Usuario


class UsuarioRepository(Protocol):
    def obter_por_id(self, usuario_id: UUID) -> Usuario | None: ...

    def obter_por_email(self, email: str) -> Usuario | None: ...

    def salvar(self, usuario: Usuario) -> None: ...

    def email_existe(self, email: str) -> bool: ...


class TokenRevogadoRepository(Protocol):
    def revogar(self, jti: str) -> None: ...

    def esta_revogado(self, jti: str) -> bool: ...
