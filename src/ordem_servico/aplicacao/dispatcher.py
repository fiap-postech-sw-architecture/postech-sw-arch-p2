"""Dispatch sincrono in-process de eventos de dominio (RF-024).

Mecanismo minimo que liga o debito declarado desde a fase 1 (eventos
acumulados em ``_eventos_pendentes`` sem publicacao): os casos de uso de
transicao entregam ``ordem.coletar_eventos()`` ao dispatcher APOS o
commit da UnitOfWork, e o dispatcher repassa cada evento a cada handler
registrado, em ordem.

Falha de handler NUNCA propaga (log + segue): o aceite do RF-024 exige
que falha de notificacao nao bloqueie uma transicao ja persistida. Um
event bus assincrono/derivado fica deliberadamente fora da fase 2 — ver
ADR-018 (decisao de dispatch deferida ao plano de execucao).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from src.compartilhado.dominio.events import DomainEvent

_log = structlog.get_logger(__name__)


class EventDispatcher:
    """Repassa eventos de dominio a handlers sincronos, tolerando falhas."""

    def __init__(self, handlers: Sequence[Callable[[DomainEvent], None]]) -> None:
        self._handlers = tuple(handlers)

    def despachar(self, eventos: Sequence[DomainEvent]) -> None:
        """Entrega cada evento a cada handler; excecoes sao logadas e engolidas.

        A captura ampla e intencional (politica do RF-024: notificacao
        nunca derruba a transicao ja commitada); o stack trace completo
        vai para o log estruturado.
        """
        for evento in eventos:
            for handler in self._handlers:
                try:
                    handler(evento)
                except Exception:  # noqa: BLE001 — falha de handler nao pode propagar (RF-024)
                    _log.exception(
                        "handler de evento de dominio falhou; transicao preservada",
                        evento=type(evento).__name__,
                        handler=type(handler).__name__,
                        agregado_id=str(evento.agregado_id),
                    )
