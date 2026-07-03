from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from relay.handlers import (
    NOME_HANDLER_EMAIL,
    _desserializar_valor,
    construir_mapa_handlers,
)
from relay.processador import PayloadInvalidoError


def test_mapa_cobre_os_nove_eventos_de_transicao() -> None:
    engine = MagicMock()
    mapa = construir_mapa_handlers(engine)
    assert set(mapa) == {
        "DiagnosticoIniciadoEvent",
        "OrcamentoGeradoEvent",
        "OrcamentoAprovadoEvent",
        "ServicoFinalizadoEvent",
        "EntregaRegistradaEvent",
        "OrdemCanceladaEvent",
        "OrcamentoComplementarGeradoEvent",
        "OrcamentoComplementarAprovadoEvent",
        "OrcamentoComplementarRejeitadoEvent",
    }


def test_nome_handler_email_estavel() -> None:
    # Usado como chave em processed_events; nao pode mudar entre deploys.
    assert NOME_HANDLER_EMAIL == "email"


def test_handler_reconstroi_evento_e_invoca_notificacao(monkeypatch) -> None:
    import relay.handlers as handlers_mod

    capturado: list = []

    class FakeNotificar:
        def __init__(self, **_kwargs) -> None:
            pass

        def __call__(self, evento) -> None:
            capturado.append(evento)

    monkeypatch.setattr(handlers_mod, "NotificarMudancaDeStatus", FakeNotificar)

    engine = MagicMock()
    mapa = construir_mapa_handlers(engine)
    agregado_id = uuid4()
    mapa["DiagnosticoIniciadoEvent"](
        {"agregado_id": str(agregado_id), "ocorrido_em": "2026-06-24T12:00:00+00:00"}
    )

    assert len(capturado) == 1
    assert str(capturado[0].agregado_id) == str(agregado_id)


# ---------------------------------------------------------------------------
# Payload malformado: falha DETERMINISTICA -> PayloadInvalidoError (DLQ direto)
# ---------------------------------------------------------------------------


def test_payload_malformado_levanta_payload_invalido_antes_da_entrega() -> None:
    # A desserializacao roda ANTES de abrir session/SMTP: um payload que nao
    # reconstroi (UUID invalido -> ValueError) vira PayloadInvalidoError — o
    # processador manda a linha DIRETO para a DLQ na 1a, sem retries (o dado
    # gravado nao muda entre tentativas).
    mapa = construir_mapa_handlers(MagicMock())

    with pytest.raises(PayloadInvalidoError, match="DiagnosticoIniciadoEvent"):
        mapa["DiagnosticoIniciadoEvent"]({"agregado_id": "nao-e-um-uuid"})


def test_payload_com_tipo_errado_levanta_payload_invalido() -> None:
    # TypeError (ISO datetime nao-string) tambem e deterministico -> mesmo
    # tratamento de payload invalido.
    mapa = construir_mapa_handlers(MagicMock())

    with pytest.raises(PayloadInvalidoError):
        mapa["DiagnosticoIniciadoEvent"](
            {"agregado_id": str(uuid4()), "ocorrido_em": 12345}
        )


# ---------------------------------------------------------------------------
# Heuristica de annotation da desserializacao: opcionais normalizados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "anotacao",
    [
        "UUID",
        "uuid.UUID",
        "UUID | None",
        "None | UUID",
        "uuid.UUID | None",
        "Optional[UUID]",
        "typing.Optional[UUID]",
        "Optional[uuid.UUID]",
    ],
)
def test_desserializa_uuid_mesmo_em_anotacoes_opcionais(anotacao: str) -> None:
    # Um campo opcional novo ("UUID | None"/"Optional[UUID]") nao pode cair no
    # ramo cru e nascer str onde o evento espera UUID.
    bruto = str(uuid4())

    valor = _desserializar_valor(anotacao, bruto)

    assert isinstance(valor, UUID)
    assert str(valor) == bruto


@pytest.mark.parametrize(
    "anotacao",
    ["datetime", "datetime | None", "Optional[datetime]", "datetime.datetime | None"],
)
def test_desserializa_datetime_mesmo_em_anotacoes_opcionais(anotacao: str) -> None:
    bruto = "2026-06-24T12:00:00+00:00"

    valor = _desserializar_valor(anotacao, bruto)

    assert isinstance(valor, datetime)
    assert valor.isoformat() == bruto


def test_desserializa_none_e_tipos_crus_passam_intactos() -> None:
    # None continua None (campo opcional ausente) e tipos sem regra especial
    # (str/int/uniao ambigua) passam crus.
    assert _desserializar_valor("UUID | None", None) is None
    assert _desserializar_valor("str | None", "texto") == "texto"
    assert _desserializar_valor("int", 7) == 7
    # Uniao com mais de um tipo nao-None e ambigua: fica cru de proposito.
    assert _desserializar_valor("UUID | int", "abc") == "abc"
