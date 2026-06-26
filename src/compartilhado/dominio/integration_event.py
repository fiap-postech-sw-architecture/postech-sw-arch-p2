"""Marcador ``IntegrationEvent``: eventos que cruzam a fronteira de entrega.

Subclasse de ``DomainEvent`` sem campos proprios. Eventos que devem ser
entregues de forma duravel (at-least-once) via Transactional Outbox
(RF-018) subclassam ``IntegrationEvent`` em vez de ``DomainEvent``; a
``UnitOfWork`` coleta apenas estes no commit e os grava na tabela
``outbox``. Domain events puros (subclasses diretas de ``DomainEvent``)
seguem no dispatch sincrono in-process, sem durabilidade.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True, slots=True)
class IntegrationEvent(DomainEvent):
    """Evento de integracao: entregue via outbox + relay (RF-018)."""
