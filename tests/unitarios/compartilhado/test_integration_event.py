from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from src.compartilhado.dominio.events import DomainEvent
from src.compartilhado.dominio.integration_event import IntegrationEvent
from src.ordem_servico.aplicacao.notificacoes import _STATUS_POR_EVENTO


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


def test_nomes_de_integration_event_sao_globalmente_unicos() -> None:
    # Invariante do roteamento do relay: ``serializar_integration_event`` grava
    # ``tipo = type(evento).__name__`` SEM o modulo, e o relay roteia por esse
    # nome via ``relay.handlers._POR_NOME`` (derivado de ``_STATUS_POR_EVENTO``).
    # Dois IntegrationEvents com o mesmo ``__name__`` em contextos diferentes
    # colidiriam na coluna ``outbox.tipo``. ``_STATUS_POR_EVENTO`` e a fonte unica
    # dos eventos roteados; se um contexto novo emitir eventos homonimos, este
    # teste falha.
    nomes = [cls.__name__ for cls in _STATUS_POR_EVENTO]
    assert len(nomes) == len(set(nomes)), (
        f"nomes de IntegrationEvent duplicados: {nomes}"
    )
    assert len(nomes) >= 9  # os 9 eventos de transicao da OS
