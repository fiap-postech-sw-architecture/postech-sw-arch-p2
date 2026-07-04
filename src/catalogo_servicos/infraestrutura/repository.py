from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.catalogo_servicos.infraestrutura.mapping import (
    servicos_oferecidos_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class ServicoOferecidoSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(self, servico_id: UUID) -> ServicoOferecido | None:
        return self._session.get(ServicoOferecido, servico_id)

    def salvar(self, servico: ServicoOferecido) -> None:
        self._session.add(servico)
        self._session.flush()

    def listar(self, offset: int = 0, limit: int = 20) -> list[ServicoOferecido]:
        # Ordena por nome (listagem amigavel); id como tie-break para
        # paginacao deterministica entre nomes repetidos.
        stmt = (
            select(ServicoOferecido)
            .order_by(
                servicos_oferecidos_table.c.nome,
                servicos_oferecidos_table.c.id,
            )
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def contar(self) -> int:
        stmt = select(func.count()).select_from(servicos_oferecidos_table)
        result = self._session.scalar(stmt)
        return result if result is not None else 0
