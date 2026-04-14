from __future__ import annotations

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cnpj import CNPJ
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento import Documento
from src.cliente_veiculo.dominio.events import (
    ClienteAtualizadoEvent,
    ClienteDesativadoEvent,
    VeiculoAdicionadoEvent,
    VeiculoRemovidoEvent,
)
from src.cliente_veiculo.dominio.exceptions import (
    ClienteNaoEncontradoException,
    DocumentoDuplicadoException,
    PlacaDuplicadaException,
    VeiculoNaoEncontradoException,
)
from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.dominio.repository import ClienteRepository
from src.cliente_veiculo.dominio.veiculo import Veiculo

__all__ = [
    "CNPJ",
    "CPF",
    "Cliente",
    "ClienteAtualizadoEvent",
    "ClienteDesativadoEvent",
    "ClienteNaoEncontradoException",
    "ClienteRepository",
    "Documento",
    "DocumentoDuplicadoException",
    "Placa",
    "PlacaDuplicadaException",
    "Veiculo",
    "VeiculoAdicionadoEvent",
    "VeiculoNaoEncontradoException",
    "VeiculoRemovidoEvent",
]
