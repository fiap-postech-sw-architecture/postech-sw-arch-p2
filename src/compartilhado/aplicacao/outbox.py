"""Serializacao e porta de saida da Transactional Outbox (RF-018).

``serializar_integration_event`` converte um ``IntegrationEvent`` (frozen
dataclass) num ``OutboxRegistro`` com ``payload`` JSON-serializavel:
``UUID`` viram ``str`` e ``datetime`` viram ISO-8601. A funcao e pura
(sem I/O) para ser exercitada em unit test; o INSERT real e
responsabilidade da infraestrutura (``outbox_mapping.inserir_na_outbox``).

``OutboxPort`` e o contrato que a ``UnitOfWork`` consome para enfileirar
os registros na mesma transacao do estado.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.compartilhado.dominio.integration_event import IntegrationEvent


@dataclass(frozen=True, slots=True)
class OutboxRegistro:
    """Linha a inserir na ``outbox``: tipo do evento + payload serializado."""

    agregado_id: UUID
    tipo: str
    payload: dict[str, Any]


def _serializar_valor(valor: Any) -> Any:  # noqa: ANN401 — campos heterogeneos do evento
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor


def serializar_integration_event(evento: IntegrationEvent) -> OutboxRegistro:
    """Projeta um ``IntegrationEvent`` para ``OutboxRegistro`` (payload JSON).

    Percorre os ``dataclasses.fields`` do evento (inclui ``agregado_id`` e
    ``ocorrido_em`` herdados de ``DomainEvent`` e quaisquer campos da
    subclasse, ex.: ``OrdemCanceladaEvent.motivo``), normalizando UUID/
    datetime para tipos JSON.
    """
    payload = {
        campo.name: _serializar_valor(getattr(evento, campo.name))
        for campo in fields(evento)
    }
    return OutboxRegistro(
        agregado_id=evento.agregado_id,
        tipo=type(evento).__name__,
        payload=payload,
    )


class OutboxPort(Protocol):
    """Enfileira ``IntegrationEvent`` na outbox dentro da transacao corrente."""

    def enfileirar(self, eventos: Sequence[IntegrationEvent]) -> None:
        """Insere os eventos na ``outbox`` usando a transacao em andamento."""
        ...  # lgtm[py/ineffectual-statement]
