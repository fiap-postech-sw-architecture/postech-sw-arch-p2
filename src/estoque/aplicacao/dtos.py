from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CriarItemEstoqueDTO:
    nome: str
    descricao: str
    quantidade: int
    preco_unitario: Decimal


@dataclass(frozen=True, slots=True)
class AtualizarItemEstoqueDTO:
    nome: str
    descricao: str
    preco_unitario: Decimal


@dataclass(frozen=True, slots=True)
class AjustarQuantidadeDTO:
    nova_quantidade: int


@dataclass(frozen=True, slots=True)
class ItemEstoqueDTO:
    id: UUID
    nome: str
    descricao: str
    quantidade: int
    preco_unitario: Decimal
    moeda: str
    ativo: bool
