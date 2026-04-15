from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.estoque.dominio.item_estoque import ItemEstoque


class ItemEstoqueRepository(Protocol):
    def obter_por_id(self, item_id: UUID) -> ItemEstoque | None: ...

    def obter_por_ids(self, ids: list[UUID]) -> list[ItemEstoque]: ...

    def salvar(self, item: ItemEstoque) -> None: ...

    def listar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoque]: ...

    def contar(self) -> int: ...
