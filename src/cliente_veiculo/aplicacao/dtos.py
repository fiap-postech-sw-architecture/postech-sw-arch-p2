from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CriarClienteDTO:
    """Entrada do use case `CriarCliente` (payload de criacao).

    Contem dados brutos de entrada (documento ainda sem mascara). E tratado
    como PII e nao deve ser logado em texto puro pelos handlers de erro.
    """

    nome: str = field(repr=False)
    documento: str = field(repr=False)
    tipo_documento: str
    contato: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AtualizarClienteDTO:
    """Entrada do use case `AtualizarCliente` (novos valores de nome/contato)."""

    nome: str = field(repr=False)
    contato: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AdicionarVeiculoDTO:
    """Entrada do use case `AdicionarVeiculo`. `placa` nao e PII."""

    placa: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True, slots=True)
class VeiculoDTO:
    """DTO de saida para um veiculo individual."""

    id: UUID
    placa: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True, slots=True)
class ClienteDTO:
    """DTO detalhado de Cliente (saida de criacao, atualizacao e obtencao).

    `documento_formatado` carrega o CPF/CNPJ sem mascara e so deve ser exposto
    em contextos autenticados. `nome` e `contato` sao PII e nao entram no
    `__repr__` gerado automaticamente.
    """

    id: UUID
    nome: str = field(repr=False)
    documento_formatado: str = field(repr=False)
    documento_mascarado: str
    tipo_documento: str
    contato: str = field(repr=False)
    ativo: bool
    veiculos: list[VeiculoDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ClienteResumoDTO:
    """DTO compacto para listagens (sem veiculos e sem documento completo)."""

    id: UUID
    nome: str = field(repr=False)
    documento_mascarado: str
    tipo_documento: str
    contato: str = field(repr=False)
    ativo: bool
