"""Serializacao e porta de saida da Transactional Outbox (RF-018).

``serializar_integration_event`` converte um ``IntegrationEvent`` (frozen
dataclass) num ``OutboxRegistro`` com ``payload`` JSON-serializavel:
``UUID`` viram ``str``, ``datetime``/``date`` viram ISO-8601, ``Decimal``
vira ``str`` e ``Enum`` vira ``.value``. A funcao e pura (sem I/O) para
ser exercitada em unit test; o INSERT real e responsabilidade da
infraestrutura (``outbox_mapping.inserir_na_outbox``), chamada diretamente
pela ``UnitOfWork`` na mesma transacao do estado.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
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
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, Enum):
        return _serializar_valor(valor.value)
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    msg = (
        f"Tipo nao suportado no payload da outbox: {type(valor).__name__}. "
        "Suportados: JSON nativos, UUID, datetime/date, Decimal e Enum."
    )
    raise TypeError(msg)


def serializar_integration_event(evento: IntegrationEvent) -> OutboxRegistro:
    """Projeta um ``IntegrationEvent`` para ``OutboxRegistro`` (payload JSON).

    Percorre os ``dataclasses.fields`` do evento (inclui ``agregado_id`` e
    ``ocorrido_em`` herdados de ``DomainEvent`` e quaisquer campos da
    subclasse, ex.: ``OrdemCanceladaEvent.motivo``), normalizando UUID/
    datetime/date/Decimal/Enum para tipos JSON. Campo de tipo nao suportado
    -> ``TypeError`` imediato (fail-fast no commit, nao no relay).

    ``tipo`` e ``type(evento).__name__`` SEM o modulo: nomes de classe de
    ``IntegrationEvent`` devem ser GLOBALMENTE unicos entre os bounded
    contexts, senao dois eventos distintos colidem na coluna ``outbox.tipo``
    (e no roteamento de handlers do relay).

    Raises:
        TypeError: algum campo do evento tem tipo nao serializavel.
    """
    payload: dict[str, Any] = {}
    for campo in fields(evento):
        valor = getattr(evento, campo.name)
        try:
            payload[campo.name] = _serializar_valor(valor)
        except TypeError as exc:
            msg = (
                f"Campo {campo.name!r} de {type(evento).__name__} nao e "
                f"serializavel para a outbox: {exc}"
            )
            raise TypeError(msg) from exc
    return OutboxRegistro(
        agregado_id=evento.agregado_id,
        tipo=type(evento).__name__,
        payload=payload,
    )
