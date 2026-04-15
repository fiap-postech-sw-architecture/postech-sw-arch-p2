from __future__ import annotations

from dataclasses import dataclass

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True)
class EstoqueReservadoEvent(DomainEvent):
    """Evento emitido quando uma reserva bem-sucedida consome estoque.

    ``agregado_id`` (herdado de ``DomainEvent``) identifica o ``ItemEstoque``.
    """

    quantidade_reservada: int = 0
    quantidade_restante: int = 0


@dataclass(frozen=True)
class EstoqueLiberadoEvent(DomainEvent):
    """Evento emitido quando estoque e devolvido (liberado) ao agregado.

    ``agregado_id`` (herdado de ``DomainEvent``) identifica o ``ItemEstoque``.
    """

    quantidade_liberada: int = 0
    quantidade_atual: int = 0
