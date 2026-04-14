from __future__ import annotations

import pytest

from src.cliente_veiculo.dominio.cpf import CPF

CPF_VALIDO = "21249722519"


class TestCPF:
    def test_criacao_com_digitos(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        assert cpf.numero == CPF_VALIDO

    def test_criacao_com_formatacao(self) -> None:
        cpf = CPF(numero="212.497.225-19")
        assert cpf.numero == CPF_VALIDO

    def test_cpf_invalido_digito_verificador(self) -> None:
        with pytest.raises(ValueError, match="CPF invalido"):
            CPF(numero="21249722510")

    def test_cpf_invalido_todos_iguais(self) -> None:
        with pytest.raises(ValueError, match="CPF invalido"):
            CPF(numero="11111111111")

    def test_cpf_invalido_tamanho_curto(self) -> None:
        with pytest.raises(ValueError, match="CPF invalido"):
            CPF(numero="123")

    def test_cpf_invalido_vazio(self) -> None:
        with pytest.raises(ValueError, match="CPF invalido"):
            CPF(numero="")

    def test_formatado(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        assert cpf.formatado() == "212.497.225-19"

    def test_mascarado(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        assert cpf.mascarado() == "***.***.***-19"

    def test_igualdade_mesmo_numero(self) -> None:
        a = CPF(numero=CPF_VALIDO)
        b = CPF(numero=CPF_VALIDO)
        assert a == b

    def test_desigualdade_numero_diferente(self) -> None:
        a = CPF(numero=CPF_VALIDO)
        b = CPF(numero="16755769983")
        assert a != b

    def test_imutabilidade(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        with pytest.raises(AttributeError):
            cpf.numero = "99999999999"  # type: ignore[misc]

    def test_hash_consistente(self) -> None:
        a = CPF(numero=CPF_VALIDO)
        b = CPF(numero=CPF_VALIDO)
        assert hash(a) == hash(b)

    def test_usavel_em_set(self) -> None:
        a = CPF(numero=CPF_VALIDO)
        b = CPF(numero="212.497.225-19")
        assert len({a, b}) == 1

    def test_repr_mascara_cpf(self) -> None:
        cpf = CPF(numero=CPF_VALIDO)
        r = repr(cpf)
        assert "***.***.***-19" in r
        assert CPF_VALIDO not in r
