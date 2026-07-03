from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

import pytest

from src.compartilhado.aplicacao.outbox import (
    OutboxRegistro,
    serializar_integration_event,
)
from src.compartilhado.dominio.integration_event import IntegrationEvent
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    OrdemCanceladaEvent,
)


class _StatusTeste(Enum):
    ATIVO = "ativo"


@dataclass(frozen=True)
class _EventoTiposExtras(IntegrationEvent):
    valor: Decimal = field(kw_only=True)
    status: _StatusTeste = field(kw_only=True)
    vencimento: date = field(kw_only=True)


@dataclass(frozen=True)
class _EventoNaoSerializavel(IntegrationEvent):
    payload_cru: object = field(kw_only=True)


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


def test_serializa_decimal_enum_e_date() -> None:
    import json

    evento = _EventoTiposExtras(
        agregado_id=uuid4(),
        valor=Decimal("10.50"),
        status=_StatusTeste.ATIVO,
        vencimento=date(2026, 7, 1),
    )

    registro = serializar_integration_event(evento)

    assert registro.payload["valor"] == "10.50"
    assert registro.payload["status"] == "ativo"
    assert registro.payload["vencimento"] == "2026-07-01"
    json.dumps(registro.payload)  # nao levanta


def test_tipo_nao_suportado_levanta_type_error_no_commit() -> None:
    # Fail-fast: o TypeError sai na serializacao (commit da UoW), com o campo
    # e o evento no texto -- nao um erro opaco de json.dumps la no relay.
    evento = _EventoNaoSerializavel(agregado_id=uuid4(), payload_cru=object())

    with pytest.raises(TypeError, match=r"payload_cru.*_EventoNaoSerializavel"):
        serializar_integration_event(evento)
