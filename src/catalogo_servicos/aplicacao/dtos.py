from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CriarServicoDTO:
    nome: str
    descricao: str
    preco: Decimal


@dataclass(frozen=True, slots=True)
class AtualizarServicoDTO:
    nome: str
    descricao: str
    preco: Decimal


@dataclass(frozen=True, slots=True)
class ServicoDTO:
    id: UUID
    nome: str
    descricao: str
    preco: Decimal
    moeda: str
    ativo: bool
