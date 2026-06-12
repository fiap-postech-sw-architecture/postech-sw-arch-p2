from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem


class TestItemDaOrdem:
    def test_criacao_valida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        servico_id = uuid4()
        item = ItemDaOrdem(
            _servico_catalogo_id=servico_id,
            _descricao="Troca de oleo",
            _quantidade=2,
            _preco_unitario=preco,
        )
        assert item.servico_catalogo_id == servico_id
        assert item.descricao == "Troca de oleo"
        assert item.quantidade == 2
        assert item.preco_unitario == preco

    def test_subtotal(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _descricao="Filtro",
            _quantidade=3,
            _preco_unitario=preco,
        )
        assert item.subtotal == Dinheiro(valor=Decimal("150.00"))

    def test_item_estoque_id_opcional(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _descricao="Servico",
            _quantidade=1,
            _preco_unitario=preco,
        )
        assert item.item_estoque_id is None

    def test_identidade_por_id(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        id_fixo = uuid4()
        a = ItemDaOrdem(
            id=id_fixo,
            _servico_catalogo_id=uuid4(),
            _descricao="A",
            _quantidade=1,
            _preco_unitario=preco,
        )
        b = ItemDaOrdem(
            id=id_fixo,
            _servico_catalogo_id=uuid4(),
            _descricao="B",
            _quantidade=2,
            _preco_unitario=preco,
        )
        assert a == b

    def test_descricao_vazia_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Descricao do item nao pode ser vazia"):
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _descricao="",
                _quantidade=1,
                _preco_unitario=preco,
            )

    def test_quantidade_zero_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Quantidade deve ser maior que zero"):
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _descricao="Item",
                _quantidade=0,
                _preco_unitario=preco,
            )

    def test_quantidade_negativa_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Quantidade deve ser maior que zero"):
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _descricao="Item",
                _quantidade=-1,
                _preco_unitario=preco,
            )

    def test_servico_catalogo_id_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="servico_catalogo_id e obrigatorio"):
            ItemDaOrdem(
                _servico_catalogo_id=None,  # type: ignore[arg-type]
                _descricao="Item",
                _quantidade=1,
                _preco_unitario=preco,
            )

    def test_servico_catalogo_id_property_nao_pode_ser_nulo(self) -> None:
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _descricao="Item",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        object.__setattr__(item, "_servico_catalogo_id", None)

        with pytest.raises(ValueError, match="servico_catalogo_id nao pode ser nulo"):
            _ = item.servico_catalogo_id

    def test_preco_unitario_none_invalido(self) -> None:
        with pytest.raises(ValueError, match="preco_unitario do item e obrigatorio"):
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _descricao="Item",
                _quantidade=1,
                _preco_unitario=None,  # type: ignore[arg-type]
            )

    def test_preco_unitario_zero_invalido(self) -> None:
        preco_zero = Dinheiro(valor=Decimal("0.00"))
        with pytest.raises(ValueError, match="preco_unitario do item deve ser maior"):
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _descricao="Item",
                _quantidade=1,
                _preco_unitario=preco_zero,
            )

    def test_preco_unitario_property_nao_pode_ser_nulo(self) -> None:
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _descricao="Item",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        object.__setattr__(item, "_preco_unitario", None)

        with pytest.raises(ValueError, match="preco_unitario nao pode ser nulo"):
            _ = item.preco_unitario
