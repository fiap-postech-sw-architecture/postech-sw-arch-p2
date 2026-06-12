from __future__ import annotations

from uuid import uuid4

import pytest

from src.cliente_veiculo.dominio import veiculo as veiculo_module
from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.dominio.veiculo import Veiculo

_ANO_CONGELADO = 2030


@pytest.fixture(autouse=True)
def _congelar_ano_maximo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Congela o ano maximo permitido em 2031 (2030 + 1) para tornar os testes
    de fronteira deterministicos ao longo do tempo.
    """
    monkeypatch.setattr(
        veiculo_module,
        "_ano_maximo_permitido",
        lambda: _ANO_CONGELADO + 1,
    )


class TestVeiculo:
    def test_criacao_valida(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        assert v.placa == placa
        assert v.marca == "Fiat"
        assert v.modelo == "Uno"
        assert v.ano == 2020

    def test_id_gerado_automaticamente(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        assert v.id is not None

    def test_ano_invalido_muito_antigo(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=1886)

    def test_ano_invalido_futuro(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2100)

    def test_ano_atual_congelado_valido(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Tesla", _modelo="M3", _ano=_ANO_CONGELADO)
        assert v.ano == _ANO_CONGELADO

    def test_ano_limite_inferior(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Benz", _modelo="Patent", _ano=1887)
        assert v.ano == 1887

    def test_identidade_por_id(self) -> None:
        placa = Placa(valor="ABC1234")
        id_fixo = uuid4()
        a = Veiculo(id=id_fixo, _placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        b = Veiculo(id=id_fixo, _placa=placa, _marca="VW", _modelo="Gol", _ano=2021)
        assert a == b

    def test_desigualdade_ids_diferentes(self) -> None:
        placa = Placa(valor="ABC1234")
        a = Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        b = Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        assert a != b

    def test_ano_1886_invalido_fronteira(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="Benz", _modelo="Patent", _ano=1886)

    def test_ano_1887_valido_fronteira(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Benz", _modelo="Patent", _ano=1887)
        assert v.ano == 1887

    def test_ano_proximo_valido_fronteira(self) -> None:
        ano_proximo = _ANO_CONGELADO + 1
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Tesla", _modelo="Model S", _ano=ano_proximo)
        assert v.ano == ano_proximo

    def test_ano_depois_do_proximo_invalido_fronteira(self) -> None:
        ano_invalido = _ANO_CONGELADO + 2
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="Tesla", _modelo="Model S", _ano=ano_invalido)

    def test_ano_zero_invalido(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="X", _modelo="Y", _ano=0)

    def test_ano_negativo_invalido(self) -> None:
        placa = Placa(valor="ABC1234")
        with pytest.raises(ValueError, match="Ano deve ser entre"):
            Veiculo(_placa=placa, _marca="X", _modelo="Y", _ano=-1)

    def test_placa_none_invalida(self) -> None:
        with pytest.raises(ValueError, match="Placa do veiculo"):
            Veiculo(_placa=None, _marca="Fiat", _modelo="Uno", _ano=2020)  # type: ignore[arg-type]

    def test_placa_property_nao_pode_ser_nula(self) -> None:
        placa = Placa(valor="ABC1234")
        v = Veiculo(_placa=placa, _marca="Fiat", _modelo="Uno", _ano=2020)
        object.__setattr__(v, "_placa", None)

        with pytest.raises(ValueError, match="Placa do veiculo nao pode ser nula"):
            _ = v.placa
