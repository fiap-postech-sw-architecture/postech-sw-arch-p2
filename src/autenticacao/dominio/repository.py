from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.usuario import Usuario


class UsuarioRepository(Protocol):
    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        pass

    def obter_por_email(self, email: str) -> Usuario | None:
        pass

    def salvar(self, usuario: Usuario) -> None:
        pass

    def email_existe(self, email: str) -> bool:
        pass


class TokenRevogadoRepository(Protocol):
    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def revogar(self, jti: str) -> None:
        pass

    def esta_revogado(self, jti: str) -> bool:
        pass
