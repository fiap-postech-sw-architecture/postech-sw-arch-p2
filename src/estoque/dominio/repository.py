from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.estoque.dominio.item_estoque import ItemEstoque


class ItemEstoqueRepository(Protocol):
    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def obter_por_id(
        self, item_id: UUID, *, com_lock: bool = False
    ) -> ItemEstoque | None:
        pass

    def obter_por_ids(self, ids: list[UUID]) -> list[ItemEstoque]:
        pass

    def salvar(self, item: ItemEstoque) -> None:
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoque]:
        pass

    def contar(self) -> int:
        pass
