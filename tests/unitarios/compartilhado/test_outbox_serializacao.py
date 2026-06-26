from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.compartilhado.aplicacao.outbox import (
    OutboxRegistro,
    serializar_integration_event,
)
from src.compartilhado.dominio.integration_event import IntegrationEvent
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    OrdemCanceladaEvent,
)


def test_serializa_evento_sem_payload_extra() -> None:
    agregado_id = uuid4()
    ocorrido = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    evento = DiagnosticoIniciadoEvent(agregado_id=agregado_id, ocorrido_em=ocorrido)

    registro = serializar_integration_event(evento)

    assert isinstance(registro, OutboxRegistro)
    assert registro.agregado_id == agregado_id
    assert registro.tipo == "DiagnosticoIniciadoEvent"
    assert registro.payload == {
        "agregado_id": str(agregado_id),
        "ocorrido_em": "2026-06-24T12:00:00+00:00",
    }


def test_serializa_evento_com_campo_extra() -> None:
    agregado_id = uuid4()
    evento = OrdemCanceladaEvent(agregado_id=agregado_id, motivo="cliente desistiu")

    registro = serializar_integration_event(evento)

    assert registro.tipo == "OrdemCanceladaEvent"
    assert registro.payload["motivo"] == "cliente desistiu"
    assert registro.payload["agregado_id"] == str(agregado_id)


def test_payload_e_json_serializavel() -> None:
    import json

    evento = IntegrationEvent(agregado_id=uuid4())
    registro = serializar_integration_event(evento)
    # nao levanta
    json.dumps(registro.payload)
