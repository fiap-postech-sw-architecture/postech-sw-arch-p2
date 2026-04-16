from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.cliente_veiculo.dominio.veiculo import (
    _ANO_PRIMEIRO_CARRO,
    _ano_maximo_permitido,
)

_ANO_MINIMO = _ANO_PRIMEIRO_CARRO + 1


class CriarClienteRequest(BaseModel):
    """Payload de entrada para criacao de cliente via POST /clientes."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    documento: str = Field(min_length=11, max_length=18)
    tipo_documento: Literal["cpf", "cnpj"]
    contato: str = Field(min_length=1, max_length=255)


class AtualizarClienteRequest(BaseModel):
    """Payload de entrada para atualizacao via PUT /clientes/{id}."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=255)
    contato: str = Field(min_length=1, max_length=255)


class AdicionarVeiculoRequest(BaseModel):
    """Payload de entrada para adicao de veiculo a um cliente.

    O limite maximo do campo `ano` e resolvido dinamicamente pela regra do
    dominio (`_ano_maximo_permitido()`), garantindo que o schema e o agregado
    `Veiculo` falhem consistentemente com o mesmo range — incluindo nos testes
    que congelam o ano maximo via monkeypatch.
    """

    model_config = ConfigDict(extra="forbid")

    placa: str = Field(min_length=7, max_length=8)
    marca: str = Field(min_length=1, max_length=100)
    modelo: str = Field(min_length=1, max_length=100)
    ano: int = Field(ge=_ANO_MINIMO)

    @field_validator("ano")
    @classmethod
    def _ano_nao_excede_dominio(cls, v: int) -> int:
        limite = _ano_maximo_permitido()
        if v > limite:
            msg = f"ano deve ser menor ou igual a {limite}"
            raise ValueError(msg)
        return v


class VeiculoResponse(BaseModel):
    """Representacao JSON de um veiculo retornada pela API."""

    id: UUID
    placa: str
    marca: str
    modelo: str
    ano: int


class ClienteResponse(BaseModel):
    """Representacao JSON completa do cliente (com veiculos aninhados)."""

    id: UUID
    nome: str
    documento_formatado: str
    documento_mascarado: str
    tipo_documento: str
    contato: str
    ativo: bool
    veiculos: list[VeiculoResponse]


class ClienteResumoResponse(BaseModel):
    """Representacao resumida do cliente usada em listagens paginadas."""

    id: UUID
    nome: str
    documento_mascarado: str
    tipo_documento: str
    contato: str
    ativo: bool


class ClienteListaResponse(BaseModel):
    """Envelope de listagem paginada de clientes."""

    items: list[ClienteResumoResponse]
    total: int
    offset: int
    limit: int


class DadosPessoaisResponse(BaseModel):
    """Dados pessoais exportados (LGPD direito de acesso)."""

    id: UUID
    nome: str
    documento_formatado: str
    tipo_documento: str
    contato: str
    veiculos: list[dict[str, object]]
    ativo: bool


class ConsentimentoRequest(BaseModel):
    """Payload de entrada para registro de consentimento LGPD."""

    model_config = ConfigDict(extra="forbid")
    tipo: str = Field(
        min_length=1,
        max_length=50,
        examples=["tratamento_dados", "marketing", "compartilhamento"],
    )


class ConsentimentoResponse(BaseModel):
    """Representacao de consentimento LGPD."""

    id: UUID
    cliente_id: UUID
    tipo: str
    concedido_em: str
    revogado_em: str | None
    ativo: bool
