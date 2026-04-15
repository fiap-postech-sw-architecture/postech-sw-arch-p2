from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.estoque.dominio.item_estoque import ItemEstoque
from src.estoque.infraestrutura.mapping import itens_estoque_table

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class ItemEstoqueSQLAlchemyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_por_id(self, item_id: UUID) -> ItemEstoque | None:
        return self._session.get(ItemEstoque, item_id)

    def obter_por_ids(self, ids: list[UUID]) -> list[ItemEstoque]:
        stmt = (
            select(ItemEstoque)
            .where(itens_estoque_table.c.id.in_(ids))
            .with_for_update(nowait=True)
            .order_by(itens_estoque_table.c.id)
        )
        return list(self._session.scalars(stmt))

    def salvar(self, item: ItemEstoque) -> None:
        self._session.add(item)
        self._session.flush()

    def listar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoque]:
        stmt = (
            select(ItemEstoque)
            .order_by(itens_estoque_table.c.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def contar(self) -> int:
        stmt = select(func.count()).select_from(itens_estoque_table)
        return self._session.scalar(stmt) or 0
