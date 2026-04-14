from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass

import pytest

from src.compartilhado.dominio.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class _Cor(ValueObject):
    r: int
    g: int
    b: int


class TestValueObject:
    def test_igualdade_estrutural(self) -> None:
        a = _Cor(r=255, g=0, b=0)
        b = _Cor(r=255, g=0, b=0)
        assert a == b

    def test_desigualdade_por_valores(self) -> None:
        a = _Cor(r=255, g=0, b=0)
        b = _Cor(r=0, g=255, b=0)
        assert a != b

    def test_imutabilidade(self) -> None:
        cor = _Cor(r=255, g=0, b=0)
        with pytest.raises(FrozenInstanceError):
            cor.r = 0  # type: ignore[misc]

    def test_hash_consistente(self) -> None:
        a = _Cor(r=255, g=0, b=0)
        b = _Cor(r=255, g=0, b=0)
        assert hash(a) == hash(b)

    def test_hash_diferente_para_valores_diferentes(self) -> None:
        a = _Cor(r=255, g=0, b=0)
        b = _Cor(r=0, g=255, b=0)
        assert a != b
        assert len({a, b}) == 2

    def test_usavel_em_set(self) -> None:
        a = _Cor(r=255, g=0, b=0)
        b = _Cor(r=255, g=0, b=0)
        assert len({a, b}) == 1
