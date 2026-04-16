from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CriarItemEstoqueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1, max_length=2000)
    quantidade: int = Field(ge=0, le=1_000_000)
    preco_unitario: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class AtualizarItemEstoqueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1, max_length=2000)
    preco_unitario: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class AjustarQuantidadeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nova_quantidade: int = Field(ge=0, le=1_000_000)


class ItemEstoqueResponse(BaseModel):
    id: UUID
    nome: str
    descricao: str
    quantidade: int
    preco_unitario: Decimal
    moeda: str
    ativo: bool


class ItemEstoqueListaResponse(BaseModel):
    items: list[ItemEstoqueResponse]
    total: int
    offset: int
    limit: int
