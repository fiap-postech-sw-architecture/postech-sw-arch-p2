from __future__ import annotations

from typing import TYPE_CHECKING

from src.autenticacao.dominio.token_revogado import TokenRevogado

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TokenRevogadoSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def revogar(self, jti: str) -> None:
        token = TokenRevogado.criar(jti=jti)
        self._session.add(token)
        self._session.flush()

    def esta_revogado(self, jti: str) -> bool:
        from src.autenticacao.infraestrutura.mapping import (
            tokens_revogados_table,
        )

        stmt = tokens_revogados_table.select().where(
            tokens_revogados_table.c.jti == jti
        )
        result = self._session.execute(stmt).first()
        return result is not None
