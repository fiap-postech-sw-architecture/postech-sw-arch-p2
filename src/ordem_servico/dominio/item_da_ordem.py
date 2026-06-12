"""Entity ``ItemDaOrdem``: linha de servico ou peca dentro de uma OrdemDeServico."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.compartilhado.dominio.entity import Entity

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.dominio.dinheiro import Dinheiro


@dataclass(eq=False)
class ItemDaOrdem(Entity):
    """Linha de servico ou peca dentro de uma OrdemDeServico.

    Identificada por ``id`` (Entity), mantem invariantes:

    - ``descricao`` nao vazia
    - ``quantidade`` > 0
    - ``servico_catalogo_id`` obrigatorio
    - ``preco_unitario`` obrigatorio (``Dinheiro`` nao nulo) e ``valor`` > 0
    """

    _servico_catalogo_id: UUID | None = field(default=None, repr=False)
    _item_estoque_id: UUID | None = field(default=None, repr=False)
    _descricao: str = ""
    _quantidade: int = 0
    _preco_unitario: Dinheiro | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self._servico_catalogo_id is None:
            msg = "servico_catalogo_id e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if not self._descricao:
            msg = (
                f"Descricao do item nao pode ser vazia (recebido: {self._descricao!r})"
            )
            raise ValueError(msg)
        if self._quantidade <= 0:
            msg = f"Quantidade deve ser maior que zero (recebido: {self._quantidade})"
            raise ValueError(msg)
        if self._preco_unitario is None:
            msg = "preco_unitario do item e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if self._preco_unitario.valor <= 0:
            msg = (
                f"preco_unitario do item deve ser maior que zero "
                f"(recebido: {self._preco_unitario.valor})"
            )
            raise ValueError(msg)

    @property
    def servico_catalogo_id(self) -> UUID:
        if self._servico_catalogo_id is None:
            msg = "servico_catalogo_id nao pode ser nulo"
            raise ValueError(msg)
        return self._servico_catalogo_id

    @property
    def item_estoque_id(self) -> UUID | None:
        return self._item_estoque_id

    @property
    def descricao(self) -> str:
        return self._descricao

    @property
    def quantidade(self) -> int:
        return self._quantidade

    @property
    def preco_unitario(self) -> Dinheiro:
        if self._preco_unitario is None:
            msg = "preco_unitario nao pode ser nulo"
            raise ValueError(msg)
        return self._preco_unitario

    @property
    def subtotal(self) -> Dinheiro:
        preco_unitario = self.preco_unitario
        return preco_unitario * self._quantidade
