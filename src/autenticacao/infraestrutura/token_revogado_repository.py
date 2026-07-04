from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import exists, select

from src.autenticacao.dominio.token_revogado import TokenRevogado
from src.autenticacao.infraestrutura.mapping import tokens_revogados_table

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TokenRevogadoSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def revogar(self, jti: str) -> bool:
        """Revoga o jti. True se revogou agora; False se ja estava revogado.

        Idempotente (#121): logout duplo / retry nao pode estourar o UNIQUE de
        jti (IntegrityError -> 500 num fluxo trivial). O retorno bool (#167)
        distingue "revoguei agora" de "ja estava revogado": o fluxo de refresh
        usa False para negar o segundo uso do mesmo token (single-use), em vez
        de tratar a revogacao repetida como sucesso.
        """
        if self.esta_revogado(jti):
            return False
        token = TokenRevogado.criar(jti=jti)
        self._session.add(token)
        self._session.flush()
        return True

    def esta_revogado(self, jti: str) -> bool:
        stmt = select(exists().where(tokens_revogados_table.c.jti == jti))
        return bool(self._session.scalar(stmt))
