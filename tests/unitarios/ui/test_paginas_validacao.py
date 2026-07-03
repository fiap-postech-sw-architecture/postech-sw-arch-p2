"""Validacao de inputs numericos das paginas (bugs 6 e 17 do #170/#174).

``ui.number().value`` vira ``None``/``""`` quando o usuario apaga o campo;
``int(None)`` estoura TypeError e ``int(value or 0)`` zerava silenciosamente.
Mesmo padrao de ``_quantidade_valida`` (ordens_servico), ja testado la.
"""

from __future__ import annotations

from typing import Any

import pytest

from ui.paginas.clientes import _ano_valido
from ui.paginas.estoque import _quantidade_estoque_valida


class TestAnoValido:
    @pytest.mark.parametrize("valor", [None, "", "abc", object()])
    def test_invalido_retorna_none(self, valor: Any) -> None:
        assert _ano_valido(valor) is None

    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [(2020, 2020), (2020.0, 2020), ("2021", 2021)],
    )
    def test_valores_validos_normalizam_para_int(
        self, valor: Any, esperado: int
    ) -> None:
        assert _ano_valido(valor) == esperado


class TestQuantidadeEstoqueValida:
    @pytest.mark.parametrize("valor", [None, "", "abc", -1, -10])
    def test_invalido_retorna_none(self, valor: Any) -> None:
        assert _quantidade_estoque_valida(valor) is None

    def test_zero_e_valido_para_estoque(self) -> None:
        """Diferente de ``_quantidade_valida`` de itens de OS (>= 1), estoque
        zerado e um estado legitimo — zero passa."""
        assert _quantidade_estoque_valida(0) == 0

    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [(5, 5), (5.0, 5), ("7", 7)],
    )
    def test_valores_validos_normalizam_para_int(
        self, valor: Any, esperado: int
    ) -> None:
        assert _quantidade_estoque_valida(valor) == esperado
