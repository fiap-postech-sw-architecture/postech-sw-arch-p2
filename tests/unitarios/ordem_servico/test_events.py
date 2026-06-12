from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    EntregaRegistradaEvent,
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarRejeitadoEvent,
    OrcamentoGeradoEvent,
    OrdemCanceladaEvent,
    OrdemCriadaEvent,
    ServicoFinalizadoEvent,
)


class TestEvents:
    def test_ordem_criada_event(self) -> None:
        e = OrdemCriadaEvent(
            agregado_id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
        )
        assert e.cliente_id is not None
        assert isinstance(e.ocorrido_em, datetime)

    def test_ordem_criada_event_rejeita_cliente_id_none(self) -> None:
        with pytest.raises(ValueError, match="cliente_id e obrigatorio"):
            OrdemCriadaEvent(
                agregado_id=uuid4(),
                cliente_id=None,  # type: ignore[arg-type]
                veiculo_id=uuid4(),
            )

    def test_ordem_criada_event_rejeita_veiculo_id_none(self) -> None:
        with pytest.raises(ValueError, match="veiculo_id e obrigatorio"):
            OrdemCriadaEvent(
                agregado_id=uuid4(),
                cliente_id=uuid4(),
                veiculo_id=None,  # type: ignore[arg-type]
            )

    def test_diagnostico_iniciado_event(self) -> None:
        e = DiagnosticoIniciadoEvent(agregado_id=uuid4())
        assert isinstance(e.ocorrido_em, datetime)

    def test_orcamento_gerado_event(self) -> None:
        e = OrcamentoGeradoEvent(agregado_id=uuid4())
        assert isinstance(e.ocorrido_em, datetime)

    def test_ordem_cancelada_event(self) -> None:
        e = OrdemCanceladaEvent(agregado_id=uuid4(), motivo="Cliente desistiu")
        assert e.motivo == "Cliente desistiu"

    @pytest.mark.parametrize(
        "event_cls",
        [
            OrdemCriadaEvent,
            DiagnosticoIniciadoEvent,
            OrcamentoGeradoEvent,
            OrcamentoAprovadoEvent,
            ServicoFinalizadoEvent,
            EntregaRegistradaEvent,
            OrdemCanceladaEvent,
            OrcamentoComplementarGeradoEvent,
            OrcamentoComplementarAprovadoEvent,
            OrcamentoComplementarRejeitadoEvent,
        ],
    )
    def test_eventos_sao_frozen(self, event_cls: type) -> None:
        kwargs: dict[str, object] = {"agregado_id": uuid4()}
        if event_cls is OrdemCriadaEvent:
            kwargs["cliente_id"] = uuid4()
            kwargs["veiculo_id"] = uuid4()
        e = event_cls(**kwargs)
        with pytest.raises(AttributeError):
            e.agregado_id = uuid4()  # type: ignore[misc]
