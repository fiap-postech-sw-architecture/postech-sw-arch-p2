from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from src.compartilhado.dominio.events import DomainEvent
from src.compartilhado.dominio.integration_event import IntegrationEvent


def test_integration_event_e_subclasse_de_domain_event() -> None:
    assert issubclass(IntegrationEvent, DomainEvent)


def test_integration_event_carrega_payload_base() -> None:
    agregado_id = uuid4()
    evento = IntegrationEvent(agregado_id=agregado_id)
    assert evento.agregado_id == agregado_id
    assert isinstance(evento.ocorrido_em, datetime)


def test_integration_event_e_imutavel() -> None:
    evento = IntegrationEvent(agregado_id=uuid4())
    with pytest.raises(FrozenInstanceError):
        evento.agregado_id = uuid4()  # type: ignore[misc]
