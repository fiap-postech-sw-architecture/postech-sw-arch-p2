from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.estoque.dominio.item_estoque import ItemEstoque


class ItemEstoqueRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(
        self, item_id: UUID, *, com_lock: bool = False
    ) -> ItemEstoque | None:
        """Busca o item pelo id; ``com_lock=True`` serializa escritas (FOR UPDATE)."""
        pass

    def salvar(self, item: ItemEstoque) -> None:
        """Adiciona o item a sessao e faz flush imediato."""
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoque]:
        """Lista paginada ordenada por nome, com id como desempate deterministico."""
        pass

    def contar(self) -> int:
        """Total de itens cadastrados (para a paginacao de ``listar``)."""
        pass
