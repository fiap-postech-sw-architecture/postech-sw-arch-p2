from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.catalogo_servicos.interfaces.schemas import (
    CriarServicoRequest,
    ServicoResponse,
)


class TestCriarServicoRequest:
    def test_dados_validos(self) -> None:
        req = CriarServicoRequest(
            nome="Troca de oleo",
            descricao="Troca completa de oleo",
            preco=Decimal("100.00"),
        )
        assert req.nome == "Troca de oleo"

    def test_rejeita_campos_extras(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="Troca",
                descricao="Desc",
                preco=Decimal("100.00"),
                extra="x",  # type: ignore[call-arg]
            )

    def test_rejeita_preco_negativo(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="Troca",
                descricao="Desc",
                preco=Decimal("-10.00"),
            )

    def test_rejeita_nome_vazio(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="",
                descricao="Desc",
                preco=Decimal("100.00"),
            )

    def test_rejeita_descricao_vazia(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="Troca",
                descricao="",
                preco=Decimal("100.00"),
            )

    def test_rejeita_descricao_acima_do_limite(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="Troca",
                descricao="x" * 5001,
                preco=Decimal("100.00"),
            )

    def test_rejeita_preco_zero(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="Troca",
                descricao="Desc",
                preco=Decimal("0"),
            )

    def test_rejeita_nome_acima_do_limite(self) -> None:
        with pytest.raises(ValidationError):
            CriarServicoRequest(
                nome="x" * 256,
                descricao="Desc",
                preco=Decimal("100.00"),
            )


class TestServicoResponse:
    def test_serializa(self) -> None:
        servico_id = uuid4()
        resp = ServicoResponse(
            id=servico_id,
            nome="Troca",
            descricao="Desc",
            preco=Decimal("100.00"),
            moeda="BRL",
            ativo=True,
        )
        dump = resp.model_dump(mode="json")
        assert dump["id"] == str(servico_id)
        assert dump["moeda"] == "BRL"
        assert dump["ativo"] is True
