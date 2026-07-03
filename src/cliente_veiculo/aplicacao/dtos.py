from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CriarClienteDTO:
    nome: str = field(repr=False)
    documento: str = field(repr=False)
    tipo_documento: str
    contato: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AtualizarClienteDTO:
    nome: str = field(repr=False)
    contato: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AdicionarVeiculoDTO:
    placa: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True, slots=True)
class VeiculoDTO:
    id: UUID
    placa: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True, slots=True)
class ClienteDTO:
    id: UUID
    nome: str = field(repr=False)
    documento_formatado: str = field(repr=False)
    documento_mascarado: str
    tipo_documento: str
    contato: str = field(repr=False)
    ativo: bool
    veiculos: list[VeiculoDTO]


@dataclass(frozen=True, slots=True)
class ClienteResumoDTO:
    id: UUID
    nome: str = field(repr=False)
    documento_mascarado: str
    tipo_documento: str
    contato: str = field(repr=False)
    ativo: bool


@dataclass(frozen=True, slots=True)
class DadosPessoaisDTO:
    id: UUID
    nome: str = field(repr=False)
    documento_formatado: str = field(repr=False)
    tipo_documento: str
    contato: str = field(repr=False)
    veiculos: list[VeiculoDTO] = field(repr=False)
    ativo: bool


@dataclass(frozen=True, slots=True)
class ConsentimentoDTO:
    id: UUID
    cliente_id: UUID
    tipo: str
    concedido_em: datetime
    revogado_em: datetime | None
    ativo: bool


@dataclass(frozen=True, slots=True)
class RegistrarConsentimentoDTO:
    tipo: str
