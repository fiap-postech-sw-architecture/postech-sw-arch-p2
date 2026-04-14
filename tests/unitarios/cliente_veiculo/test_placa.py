from __future__ import annotations

import pytest

from src.cliente_veiculo.dominio.placa import Placa


class TestPlaca:
    def test_formato_antigo_valido(self) -> None:
        placa = Placa(valor="ABC1234")
        assert placa.valor == "ABC1234"

    def test_formato_mercosul_valido(self) -> None:
        placa = Placa(valor="ABC1D23")
        assert placa.valor == "ABC1D23"

    def test_hifen_removido(self) -> None:
        placa = Placa(valor="ABC-1234")
        assert placa.valor == "ABC1234"

    def test_minuscula_normalizada(self) -> None:
        placa = Placa(valor="abc1234")
        assert placa.valor == "ABC1234"

    def test_hifen_e_minuscula(self) -> None:
        placa = Placa(valor="abc-1d23")
        assert placa.valor == "ABC1D23"

    def test_invalida_muito_curta(self) -> None:
        with pytest.raises(ValueError, match="Placa invalida"):
            Placa(valor="ABC")

    def test_invalida_muito_longa(self) -> None:
        with pytest.raises(ValueError, match="Placa invalida"):
            Placa(valor="ABC12345")

    def test_invalida_padrao_errado(self) -> None:
        with pytest.raises(ValueError, match="Placa invalida"):
            Placa(valor="1234ABC")

    def test_invalida_vazia(self) -> None:
        with pytest.raises(ValueError, match="Placa invalida"):
            Placa(valor="")

    def test_igualdade_mesmo_valor(self) -> None:
        a = Placa(valor="ABC1234")
        b = Placa(valor="ABC1234")
        assert a == b

    def test_igualdade_formatos_diferentes(self) -> None:
        a = Placa(valor="ABC-1234")
        b = Placa(valor="abc1234")
        assert a == b

    def test_imutabilidade(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(AttributeError):
            placa.valor = "DEF5678"  # type: ignore[misc]

    def test_hash_consistente(self) -> None:
        a = Placa(valor="ABC1234")
        b = Placa(valor="ABC-1234")
        assert hash(a) == hash(b)
