from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.estoque.interfaces.schemas import (
    AjustarQuantidadeRequest,
    AtualizarItemEstoqueRequest,
    CriarItemEstoqueRequest,
    ItemEstoqueResponse,
)


class TestCriarItemEstoqueRequest:
    def test_dados_validos(self) -> None:
        req = CriarItemEstoqueRequest(
            nome="Filtro",
            descricao="Filtro de oleo",
            quantidade=10,
            preco_unitario=Decimal("50.00"),
        )
        assert req.nome == "Filtro"

    def test_rejeita_campos_extras(self) -> None:
        with pytest.raises(ValidationError):
            CriarItemEstoqueRequest(
                nome="Filtro",
                descricao="Desc",
                quantidade=10,
                preco_unitario=Decimal("50.00"),
                extra="x",  # type: ignore[call-arg]
            )

    def test_rejeita_quantidade_negativa(self) -> None:
        with pytest.raises(ValidationError):
            CriarItemEstoqueRequest(
                nome="Filtro",
                descricao="Desc",
                quantidade=-1,
                preco_unitario=Decimal("50.00"),
            )

    def test_rejeita_quantidade_acima_do_limite(self) -> None:
        with pytest.raises(ValidationError):
            CriarItemEstoqueRequest(
                nome="Filtro",
                descricao="Desc",
                quantidade=10_000_001,
                preco_unitario=Decimal("50.00"),
            )

    def test_rejeita_descricao_acima_do_limite(self) -> None:
        with pytest.raises(ValidationError):
            CriarItemEstoqueRequest(
                nome="Filtro",
                descricao="x" * 2001,
                quantidade=10,
                preco_unitario=Decimal("50.00"),
            )

    def test_rejeita_preco_acima_do_limite_numerico(self) -> None:
        with pytest.raises(ValidationError):
            CriarItemEstoqueRequest(
                nome="Filtro",
                descricao="Desc",
                quantidade=10,
                preco_unitario=Decimal("99999999999"),
            )


class TestAtualizarItemEstoqueRequest:
    def test_dados_validos(self) -> None:
        req = AtualizarItemEstoqueRequest(
            nome="Novo",
            descricao="Nova desc",
            preco_unitario=Decimal("75.00"),
        )
        assert req.preco_unitario == Decimal("75.00")

    def test_rejeita_nome_vazio(self) -> None:
        with pytest.raises(ValidationError):
            AtualizarItemEstoqueRequest(
                nome="",
                descricao="Desc",
                preco_unitario=Decimal("75.00"),
            )

    def test_rejeita_preco_zero(self) -> None:
        with pytest.raises(ValidationError):
            AtualizarItemEstoqueRequest(
                nome="Filtro",
                descricao="Desc",
                preco_unitario=Decimal("0"),
            )


class TestAjustarQuantidadeRequest:
    def test_rejeita_negativa(self) -> None:
        with pytest.raises(ValidationError):
            AjustarQuantidadeRequest(nova_quantidade=-1)

    def test_rejeita_acima_do_limite(self) -> None:
        with pytest.raises(ValidationError):
            AjustarQuantidadeRequest(nova_quantidade=10_000_001)


class TestItemEstoqueResponse:
    def test_serializa(self) -> None:
        item_id = uuid4()
        resp = ItemEstoqueResponse(
            id=item_id,
            nome="Filtro",
            descricao="Desc",
            quantidade=10,
            preco_unitario=Decimal("50.00"),
            moeda="BRL",
            ativo=True,
        )
        dump = resp.model_dump(mode="json")
        assert dump["id"] == str(item_id)
        assert dump["moeda"] == "BRL"
