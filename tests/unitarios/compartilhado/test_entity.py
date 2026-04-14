from __future__ import annotations

from uuid import uuid4

import pytest

from src.compartilhado.dominio.entity import Entity


class _EntidadeA(Entity):
    pass


class _EntidadeB(Entity):
    pass


class TestEntity:
    def test_identidade_por_uuid(self) -> None:
        id_fixo = uuid4()
        a = _EntidadeA(id=id_fixo)
        b = _EntidadeA(id=id_fixo)
        assert a == b

    def test_desigualdade_com_id_diferente(self) -> None:
        a = _EntidadeA(id=uuid4())
        b = _EntidadeA(id=uuid4())
        assert a != b

    def test_desigualdade_com_tipo_diferente(self) -> None:
        id_fixo = uuid4()
        a = _EntidadeA(id=id_fixo)
        b = _EntidadeB(id=id_fixo)
        assert a != b

    def test_desigualdade_com_nao_entidade(self) -> None:
        a = _EntidadeA(id=uuid4())
        assert a != "nao_entidade"

    def test_hash_por_id(self) -> None:
        id_fixo = uuid4()
        a = _EntidadeA(id=id_fixo)
        b = _EntidadeA(id=id_fixo)
        assert hash(a) == hash(b)

    def test_hash_diferente_para_ids_diferentes(self) -> None:
        a = _EntidadeA(id=uuid4())
        b = _EntidadeA(id=uuid4())
        assert a != b
        assert len({a, b}) == 2

    def test_id_gerado_automaticamente(self) -> None:
        a = _EntidadeA()
        b = _EntidadeA()
        assert a.id != b.id

    def test_entidade_usavel_em_set(self) -> None:
        id_fixo = uuid4()
        a = _EntidadeA(id=id_fixo)
        b = _EntidadeA(id=id_fixo)
        assert len({a, b}) == 1

    def test_id_imutavel_apos_criacao(self) -> None:
        a = _EntidadeA()
        with pytest.raises(AttributeError, match="nao pode ser alterada"):
            a.id = uuid4()

    def test_eq_retorna_not_implemented_para_tipo_diferente(self) -> None:
        a = _EntidadeA(id=uuid4())
        assert a.__eq__("string") is NotImplemented
