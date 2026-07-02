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

    def obter_por_id(
        self, item_id: UUID, *, com_lock: bool = False
    ) -> ItemEstoque | None:
        """Busca item por id.

        ``com_lock=True`` aplica ``SELECT FOR UPDATE`` para serializar
        escritas concorrentes (evita lost-update em ``AjustarQuantidade``
        quando multiplas threads leem-modificam-escrevem o mesmo item).
        ``com_lock=False`` preserva o caminho antigo (leitura simples, sem
        overhead de lock) para chamadas read-only.
        """
        if not com_lock:
            return self._session.get(ItemEstoque, item_id)
        # populate_existing=True: refresh das colunas mesmo se o item ja esta
        # no identity map — senao o FOR UPDATE devolveria a instancia stale
        # (ex.: item pre-carregado em _montar_item e depois relido para
        # reservar), reabrindo a janela de sobre-venda que o lock deveria
        # fechar (issue #117; mesma classe do fix #83).
        stmt = (
            select(ItemEstoque)
            .where(itens_estoque_table.c.id == item_id)
            .with_for_update(nowait=False)
            .execution_options(populate_existing=True)
        )
        return self._session.scalars(stmt).one_or_none()

    def obter_por_ids(self, ids: list[UUID]) -> list[ItemEstoque]:
        # populate_existing=True pelo mesmo motivo do ramo com_lock acima: este
        # e o lock em lote da reserva/liberacao (FOR UPDATE), e itens ja
        # carregados na session precisam do estado fresco pos-lock (#117).
        stmt = (
            select(ItemEstoque)
            .where(itens_estoque_table.c.id.in_(ids))
            .with_for_update(nowait=True)
            .order_by(itens_estoque_table.c.id)
            .execution_options(populate_existing=True)
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
