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
    # Invariante do roteamento do relay (outbox.serializar_integration_event
    # grava ``tipo = type(evento).__name__`` SEM o modulo, e o relay roteia por
    # esse nome via ``relay.handlers._POR_NOME``): dois IntegrationEvents com o
    # mesmo ``__name__`` em contextos diferentes colidiriam na coluna
    # ``outbox.tipo``. Ate aqui o invariante so vivia em docstring; este teste o
    # torna executavel.
    #
    # Importa EXPLICITAMENTE os modulos que definem IntegrationEvents (hoje so o
    # de ordem_servico) — NAO via pkgutil.walk_packages, que re-executa modulos e
    # registraria cada classe duas vezes (falso positivo de duplicata). Um
    # contexto novo que passe a emitir IntegrationEvents deve ser adicionado a
    # esta lista; o teste de round-trip (tests/unitarios/relay) e o mapa do relay
    # cobrem a completude do conjunto de eventos de transicao.
    import importlib
    import sys

    modulos_com_eventos = ("src.ordem_servico.dominio.events",)
    for nome_modulo in modulos_com_eventos:
        importlib.import_module(nome_modulo)

    def subclasses_transitivas(cls: type) -> set[type]:
        encontradas: set[type] = set()
        for sub in cls.__subclasses__():
            encontradas.add(sub)
            encontradas |= subclasses_transitivas(sub)
        return encontradas

    def eh_canonica(cls: type) -> bool:
        # ``@dataclass(slots=True)`` RECRIA a classe (para injetar __slots__) e a
        # versao original, ja registrada como subclasse no momento do ``class``,
        # fica como fantasma em ``__subclasses__()`` ate ser coletada. Ela nao e
        # a que o modulo expoe -- filtra-se comparando com o objeto no namespace
        # do modulo, senao todo evento com slots aparece "duplicado".
        modulo = sys.modules.get(cls.__module__)
        return getattr(modulo, cls.__name__, None) is cls

    classes = {c for c in subclasses_transitivas(IntegrationEvent) if eh_canonica(c)}
    nomes = [c.__name__ for c in classes]
    duplicados = {nome for nome in nomes if nomes.count(nome) > 1}
    assert not duplicados, f"nomes de IntegrationEvent duplicados: {duplicados}"
    # Sanidade: o walk encontrou as subclasses concretas de transicao (a base
    # TransicaoStatusEvent + os 9 eventos, no minimo).
    assert "TransicaoStatusEvent" in nomes
    assert len(classes) >= len(_STATUS_POR_EVENTO)
