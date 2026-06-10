from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.mapping import usuarios_table

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class UsuarioSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        return self._session.get(Usuario, usuario_id)

    def obter_por_email(self, email: str) -> Usuario | None:
        stmt = select(Usuario).where(usuarios_table.c.email == email)
        return self._session.scalars(stmt).first()

    def salvar(self, usuario: Usuario) -> None:
        self._session.add(usuario)
        self._session.flush()

    def email_existe(self, email: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(usuarios_table)
            .where(usuarios_table.c.email == email)
        )
        return (self._session.scalar(stmt) or 0) > 0
