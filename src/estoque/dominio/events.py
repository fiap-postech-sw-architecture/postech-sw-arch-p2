from __future__ import annotations

from dataclasses import dataclass, field

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True)
class EstoqueReservadoEvent(DomainEvent):
    """Evento emitido quando uma reserva bem-sucedida consome estoque.

    ``agregado_id`` (herdado de ``DomainEvent``) identifica o ``ItemEstoque``.
    """

    # kw_only sem defaults: evento sem os dados nao e construivel por engano
    # (padrao dos eventos de cliente_veiculo; finding DDD-tatico).
    quantidade_reservada: int = field(kw_only=True)
    quantidade_restante: int = field(kw_only=True)


@dataclass(frozen=True)
class EstoqueLiberadoEvent(DomainEvent):
    """Evento emitido quando estoque e devolvido (liberado) ao agregado.

    ``agregado_id`` (herdado de ``DomainEvent``) identifica o ``ItemEstoque``.
    """

    quantidade_liberada: int = field(kw_only=True)
    quantidade_atual: int = field(kw_only=True)
