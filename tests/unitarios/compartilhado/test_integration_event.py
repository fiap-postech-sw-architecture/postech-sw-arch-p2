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


def test_eventos_de_transicao_da_os_sao_integration_events() -> None:
    from src.ordem_servico.dominio.events import (
        DiagnosticoIniciadoEvent,
        EntregaRegistradaEvent,
        OrcamentoAprovadoEvent,
        OrcamentoComplementarAprovadoEvent,
        OrcamentoComplementarGeradoEvent,
        OrcamentoComplementarRejeitadoEvent,
        OrcamentoGeradoEvent,
        OrdemCanceladaEvent,
        ServicoFinalizadoEvent,
    )

    transicao = (
        DiagnosticoIniciadoEvent,
        OrcamentoGeradoEvent,
        OrcamentoAprovadoEvent,
        ServicoFinalizadoEvent,
        EntregaRegistradaEvent,
        OrdemCanceladaEvent,
        OrcamentoComplementarGeradoEvent,
        OrcamentoComplementarAprovadoEvent,
        OrcamentoComplementarRejeitadoEvent,
    )
    for evento_cls in transicao:
        assert issubclass(evento_cls, IntegrationEvent), evento_cls.__name__


def test_ordem_criada_event_nao_e_integration_event() -> None:
    from src.ordem_servico.dominio.events import OrdemCriadaEvent

    assert not issubclass(OrdemCriadaEvent, IntegrationEvent)
    assert issubclass(OrdemCriadaEvent, DomainEvent)
