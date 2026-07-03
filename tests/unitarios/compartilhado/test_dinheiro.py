from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro


class TestDinheiro:
    def test_criacao_basica(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        assert d.valor == Decimal("10.00")
        assert d.moeda == "BRL"

    def test_criacao_com_moeda_diferente(self) -> None:
        d = Dinheiro(valor=Decimal("5.00"), moeda="USD")
        assert d.moeda == "USD"

    def test_arredondamento_para_duas_casas(self) -> None:
        d = Dinheiro(valor=Decimal("10.005"))
        assert d.valor == Decimal("10.01")

    def test_arredondamento_tres_casas(self) -> None:
        d = Dinheiro(valor=Decimal("10.004"))
        assert d.valor == Decimal("10.00")

    def test_valor_zero_valido(self) -> None:
        d = Dinheiro(valor=Decimal("0"))
        assert d.valor == Decimal("0.00")

    def test_valor_negativo_invalido(self) -> None:
        with pytest.raises(ValueError, match="negativo"):
            Dinheiro(valor=Decimal("-1"))

    def test_moeda_minuscula_invalida(self) -> None:
        with pytest.raises(ValueError, match="maiusculas"):
            Dinheiro(valor=Decimal("10"), moeda="brl")

    def test_moeda_duas_letras_invalida(self) -> None:
        with pytest.raises(ValueError, match="maiusculas"):
            Dinheiro(valor=Decimal("10"), moeda="BR")

    def test_moeda_com_numeros_invalida(self) -> None:
        with pytest.raises(ValueError, match="maiusculas"):
            Dinheiro(valor=Decimal("10"), moeda="BR1")

    def test_igualdade_estrutural(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("10.00"))
        assert a == b

    def test_desigualdade_por_valor(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("20.00"))
        assert a != b

    def test_desigualdade_por_moeda(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"), moeda="BRL")
        b = Dinheiro(valor=Decimal("10.00"), moeda="USD")
        assert a != b

    def test_imutabilidade(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        with pytest.raises(FrozenInstanceError):
            d.valor = Decimal("20.00")  # type: ignore[misc]

    def test_soma(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("5.50"))
        resultado = a + b
        assert resultado.valor == Decimal("15.50")
        assert resultado.moeda == "BRL"

    def test_soma_moedas_diferentes_erro(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"), moeda="BRL")
        b = Dinheiro(valor=Decimal("5.00"), moeda="USD")
        with pytest.raises(ValueError, match="Moedas diferentes"):
            _ = a + b

    def test_subtracao(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("3.50"))
        resultado = a - b
        assert resultado.valor == Decimal("6.50")

    def test_subtracao_resultado_negativo_erro(self) -> None:
        a = Dinheiro(valor=Decimal("5.00"))
        b = Dinheiro(valor=Decimal("10.00"))
        with pytest.raises(ValueError, match="negativo"):
            _ = a - b

    def test_subtracao_moedas_diferentes_erro(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"), moeda="BRL")
        b = Dinheiro(valor=Decimal("5.00"), moeda="USD")
        with pytest.raises(ValueError, match="Moedas diferentes"):
            _ = a - b

    def test_multiplicacao(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        resultado = d * 3
        assert resultado.valor == Decimal("30.00")

    def test_multiplicacao_reversa(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        resultado = 3 * d
        assert resultado.valor == Decimal("30.00")

    def test_multiplicacao_por_zero(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        resultado = d * 0
        assert resultado.valor == Decimal("0.00")

    def test_multiplicacao_por_nao_inteiro_retorna_not_implemented(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        assert d.__mul__(2.5) is NotImplemented  # type: ignore[arg-type]

    def test_conversao_automatica_de_int_para_decimal(self) -> None:
        d = Dinheiro(valor=Decimal("10"))
        assert d.valor == Decimal("10.00")

    def test_hash_consistente(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("10.00"))
        assert hash(a) == hash(b)

    def test_usavel_em_set(self) -> None:
        a = Dinheiro(valor=Decimal("10.00"))
        b = Dinheiro(valor=Decimal("10.00"))
        assert len({a, b}) == 1

    def test_multiplicacao_por_negativo_invalido(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        with pytest.raises(ValueError, match="negativo"):
            d * -1

    def test_multiplicacao_por_menos_dois_invalido(self) -> None:
        d = Dinheiro(valor=Decimal("5.00"))
        with pytest.raises(ValueError, match="negativo"):
            d * -2

    def test_multiplicacao_reversa_por_negativo_invalido(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        with pytest.raises(ValueError, match="negativo"):
            # codeql[py/ineffectual-statement] -- exercita __rmul__ sob pytest.raises
            -1 * d

    def test_valor_infinito_invalido(self) -> None:
        with pytest.raises(ValueError, match="finito"):
            Dinheiro(valor=Decimal("Infinity"))

    def test_valor_nan_invalido(self) -> None:
        with pytest.raises(ValueError, match="finito"):
            Dinheiro(valor=Decimal("NaN"))

    def test_coercao_de_int_para_decimal(self) -> None:
        d = Dinheiro(valor=10)  # type: ignore[arg-type]
        assert isinstance(d.valor, Decimal)
        assert d.valor == Decimal("10.00")

    def test_coercao_de_float_para_decimal(self) -> None:
        d = Dinheiro(valor=10.5)  # type: ignore[arg-type]
        assert isinstance(d.valor, Decimal)
        assert d.valor == Decimal("10.50")

    def test_soma_com_nao_dinheiro_retorna_not_implemented(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        assert d.__add__(5) is NotImplemented  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            _ = d + 5  # type: ignore[operator]

    def test_subtracao_com_nao_dinheiro_retorna_not_implemented(self) -> None:
        d = Dinheiro(valor=Decimal("10.00"))
        assert d.__sub__("1.00") is NotImplemented  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            _ = d - 1  # type: ignore[operator]

    def test_moeda_nao_ascii_invalida(self) -> None:
        # isalpha/isupper aceitam letras acentuadas; ISO 4217 exige A-Z.
        with pytest.raises(ValueError, match="maiusculas"):
            Dinheiro(valor=Decimal("10"), moeda="RÉA")

    def test_valor_string_invalida_vira_value_error(self) -> None:
        # Decimal("abc") levantaria decimal.InvalidOperation (nao ValueError):
        # o VO converte para o contrato de invariante do dominio.
        with pytest.raises(ValueError, match="valor monetario invalido"):
            Dinheiro(valor="abc")  # type: ignore[arg-type]

    def test_zero_negativo_normalizado(self) -> None:
        d = Dinheiro(valor=Decimal("-0.001"))
        assert d.valor == Decimal("0.00")
        assert str(d.valor) == "0.00"  # sem sinal: -0.00 e normalizado
