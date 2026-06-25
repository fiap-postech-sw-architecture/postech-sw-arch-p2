"""Unitarios do ``EventDispatcher`` (RF-024).

O dispatcher e o mecanismo minimo de publicacao sincrona in-process dos
eventos de dominio coletados pelos casos de uso apos o commit. Falha de
handler NUNCA propaga (o aceite do RF-024 exige que falha de notificacao
nao bloqueie a transicao ja persistida).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import structlog
from structlog.testing import capture_logs

import src.ordem_servico.aplicacao.dispatcher as dispatcher_modulo
from src.compartilhado.dominio.events import DomainEvent
    DiagnosticoIniciadoEvent,
    ServicoFinalizadoEvent,
)


@pytest.fixture(autouse=True)
def _logger_fresco(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mesmo racional de test_notificacoes.py: proxy novo por teste evita
    # que um logger cacheado por boot anterior do app fure o capture_logs.
    monkeypatch.setattr(
        dispatcher_modulo, "_log", structlog.get_logger("test_dispatcher")
    )


class TestEventDispatcher:
    def test_despacha_cada_evento_para_todos_os_handlers_na_ordem(self) -> None:
        recebidos_a: list[DomainEvent] = []
        recebidos_b: list[DomainEvent] = []
        eventos = [
            DiagnosticoIniciadoEvent(agregado_id=uuid4()),
            ServicoFinalizadoEvent(agregado_id=uuid4()),
        ]
        dispatcher = dispatcher_modulo.EventDispatcher(
        dispatcher = dispatcher_modulo.EventDispatcher(
            handlers=(recebidos_a.append, recebidos_b.append)
        )
        )

        dispatcher.despachar(eventos)

        assert recebidos_a == eventos
        assert recebidos_b == eventos

    def test_excecao_de_handler_e_engolida_logada_e_nao_bloqueia_os_demais(
        self,
    ) -> None:
        recebidos: list[DomainEvent] = []

        def handler_quebrado(_evento: DomainEvent) -> None:
            raise RuntimeError("falha proposital do handler")

        dispatcher = dispatcher_modulo.EventDispatcher(
            handlers=(handler_quebrado, recebidos.append)
        )
        dispatcher = dispatcher_modulo.EventDispatcher(
            handlers=(handler_quebrado, recebidos.append)
        )

        with capture_logs() as logs:
            dispatcher.despachar([evento])

        # O handler seguinte ainda recebeu o evento e nada propagou.
        assert recebidos == [evento]
        assert any("handler" in str(log.get("event", "")).lower() for log in logs)
        dispatcher = dispatcher_modulo.EventDispatcher(handlers=(recebidos.append,))
    def test_sem_eventos_nao_chama_handler(self) -> None:
        recebidos: list[DomainEvent] = []
        dispatcher = dispatcher_modulo.EventDispatcher(handlers=(recebidos.append,))

        dispatcher.despachar([])

        dispatcher = dispatcher_modulo.EventDispatcher(handlers=())

    def test_sem_handlers_nao_falha(self) -> None:
        dispatcher = dispatcher_modulo.EventDispatcher(handlers=())

        dispatcher.despachar([DiagnosticoIniciadoEvent(agregado_id=uuid4())])
