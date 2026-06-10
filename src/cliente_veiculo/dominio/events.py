from __future__ import annotations

from dataclasses import dataclass

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class VeiculoAdicionadoEvent(DomainEvent):
    """Evento emitido quando um veiculo e adicionado ao Cliente.

    `placa_valor` nao e PII (placa e publica). Payload carrega apenas dados
    tecnicos do veiculo; consumidores que precisarem de dados do cliente
    consultam o agregado via repository.
    """

    placa_valor: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True, slots=True, kw_only=True)
class VeiculoRemovidoEvent(DomainEvent):
    """Evento emitido quando um veiculo e removido do Cliente."""

    placa_valor: str


@dataclass(frozen=True, slots=True)
class ClienteAtualizadoEvent(DomainEvent):
    """Evento emitido quando dados do Cliente sao alterados.

    Payload intencionalmente vazio (alem de `agregado_id` herdado) para nao
    propagar PII (nome, contato) em mensageria/outbox/logs. Consumidores que
    precisarem dos dados atualizados devem consultar o agregado pelo id.
    """


@dataclass(frozen=True, slots=True)
class ClienteDesativadoEvent(DomainEvent):
    """Evento emitido quando um Cliente e desativado (soft delete)."""
