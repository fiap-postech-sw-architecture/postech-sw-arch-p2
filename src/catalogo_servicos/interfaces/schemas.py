from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CriarServicoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1, max_length=5000)
    # max_digits/decimal_places espelham a coluna Numeric(10, 2): rejeita no
    # schema (422) o que estouraria a precisao no banco.
    preco: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class AtualizarServicoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1, max_length=5000)
    preco: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class ServicoResponse(BaseModel):
    id: UUID
    nome: str
    descricao: str
    preco: Decimal
    moeda: str
    ativo: bool


class ServicoListaResponse(BaseModel):
    items: list[ServicoResponse]
    total: int
    offset: int
    limit: int
