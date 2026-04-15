from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.dominio.orcamento import LinhaOrcamento, Orcamento


@dataclass(frozen=True)
class _ItemFake:
    descricao: str
    quantidade: int
    preco_unitario: Dinheiro


def _agora() -> datetime:
    return datetime.now(UTC)


class TestLinhaOrcamento:
    def test_criacao_valida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        subtotal = preco * 2
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=2, preco_unitario=preco, subtotal=subtotal
        )
        assert linha.descricao == "Filtro"
        assert linha.quantidade == 2
        assert linha.subtotal == Dinheiro(valor=Decimal("100.00"))

    def test_descricao_vazia_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Descricao"):
            LinhaOrcamento(
                descricao="", quantidade=1, preco_unitario=preco, subtotal=preco
            )

    def test_quantidade_zero_invalida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Quantidade"):
            LinhaOrcamento(
                descricao="Filtro", quantidade=0, preco_unitario=preco, subtotal=preco
            )

    def test_subtotal_inconsistente(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(ValueError, match="Subtotal inconsistente"):
            LinhaOrcamento(
                descricao="Filtro",
                quantidade=2,
                preco_unitario=preco,
                subtotal=Dinheiro(valor=Decimal("99.00")),
            )

    def test_imutabilidade(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        with pytest.raises(AttributeError):
            linha.descricao = "Outro"  # type: ignore[misc]

    def test_preco_unitario_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(
            ValueError, match="preco_unitario da linha de orcamento e obrigatorio"
        ):
            LinhaOrcamento(
                descricao="Filtro",
                quantidade=1,
                preco_unitario=None,  # type: ignore[arg-type]
                subtotal=preco,
            )

    def test_subtotal_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        with pytest.raises(
            ValueError, match="subtotal da linha de orcamento e obrigatorio"
        ):
            LinhaOrcamento(
                descricao="Filtro",
                quantidade=1,
                preco_unitario=preco,
                subtotal=None,  # type: ignore[arg-type]
            )


class TestOrcamento:
    def test_criacao_valida(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        orc = Orcamento(itens=(linha,), total=preco, gerado_em=_agora())
        assert len(orc.itens) == 1
        assert orc.versao_schema == 1

    def test_itens_vazio_invalido(self) -> None:
        with pytest.raises(ValueError, match="pelo menos um item"):
            Orcamento(
                itens=(),
                total=Dinheiro(valor=Decimal("0.00")),
                gerado_em=_agora(),
            )

    def test_gerar_com_um_item(self) -> None:
        item = _ItemFake(
            descricao="Filtro",
            quantidade=2,
            preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        orc = Orcamento.gerar([item])
        assert orc.total == Dinheiro(valor=Decimal("100.00"))
        assert len(orc.itens) == 1

    def test_gerar_com_multiplos_itens(self) -> None:
        items = [
            _ItemFake(
                descricao="Filtro",
                quantidade=2,
                preco_unitario=Dinheiro(valor=Decimal("50.00")),
            ),
            _ItemFake(
                descricao="Oleo",
                quantidade=1,
                preco_unitario=Dinheiro(valor=Decimal("30.00")),
            ),
        ]
        orc = Orcamento.gerar(items)
        assert orc.total == Dinheiro(valor=Decimal("130.00"))
        assert len(orc.itens) == 2

    def test_gerar_define_gerado_em(self) -> None:
        item = _ItemFake(
            descricao="Filtro",
            quantidade=1,
            preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        orc = Orcamento.gerar([item])
        assert orc.gerado_em is not None

    def test_gerar_lista_vazia_invalido(self) -> None:
        with pytest.raises(ValueError, match="pelo menos um item"):
            Orcamento.gerar([])

    def test_imutabilidade(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        orc = Orcamento(itens=(linha,), total=preco, gerado_em=_agora())
        with pytest.raises(AttributeError):
            orc.total = Dinheiro(valor=Decimal("0.00"))  # type: ignore[misc]

    def test_total_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        with pytest.raises(ValueError, match="total do orcamento e obrigatorio"):
            Orcamento(
                itens=(linha,),
                total=None,  # type: ignore[arg-type]
                gerado_em=_agora(),
            )

    def test_gerado_em_none_invalido(self) -> None:
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        with pytest.raises(ValueError, match="gerado_em do orcamento e obrigatorio"):
            Orcamento(
                itens=(linha,),
                total=preco,
                gerado_em=None,  # type: ignore[arg-type]
            )

    def test_total_inconsistente_invalido(self) -> None:
        """Construcao direta com total divergente da soma dos subtotais e rejeitada."""
        preco = Dinheiro(valor=Decimal("50.00"))
        linha = LinhaOrcamento(
            descricao="Filtro", quantidade=1, preco_unitario=preco, subtotal=preco
        )
        total_errado = Dinheiro(valor=Decimal("999.00"))
        with pytest.raises(ValueError, match="Total inconsistente"):
            Orcamento(itens=(linha,), total=total_errado, gerado_em=_agora())
