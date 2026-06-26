from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from relay.handlers import NOME_HANDLER_EMAIL, construir_mapa_handlers


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
