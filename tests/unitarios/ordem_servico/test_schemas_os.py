from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.ordem_servico.interfaces.schemas import (
    AdicionarItemRequest,
    CancelarOrdemRequest,
    CriarOrdemRequest,
    OrdemDeServicoResponse,
)


class TestCriarOrdemRequest:
    def test_valido(self) -> None:
        req = CriarOrdemRequest(cliente_id=uuid4(), veiculo_id=uuid4())
        assert req.cliente_id is not None

    def test_rejeita_extras(self) -> None:
        with pytest.raises(ValidationError):
            CriarOrdemRequest(
                cliente_id=uuid4(),
                veiculo_id=uuid4(),
                extra="x",  # type: ignore[call-arg]
            )


class TestAdicionarItemRequest:
    def test_rejeita_quantidade_zero(self) -> None:
        with pytest.raises(ValidationError):
            AdicionarItemRequest(
                servico_catalogo_id=uuid4(),
                descricao="X",
                quantidade=0,
            )


class TestCancelarOrdemRequest:
    def test_rejeita_motivo_vazio(self) -> None:
        with pytest.raises(ValidationError):
            CancelarOrdemRequest(motivo="")


class TestOrdemDeServicoResponse:
    def test_serializa(self) -> None:
        resp = OrdemDeServicoResponse(
            id=uuid4(),
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            status="recebida",
            itens=[],
            orcamento=None,
            criado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
        )
        assert resp.status == "recebida"
