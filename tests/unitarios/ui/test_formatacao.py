"""Testes do helper compartilhado de formatacao de dinheiro BR."""

from __future__ import annotations

import pytest

from ui.formatacao import formatar_dinheiro_br


def test_formata_padrao_brasileiro_com_milhar_e_virgula() -> None:
    assert formatar_dinheiro_br(1234.56) == "R$ 1.234,56"


def test_formata_milhoes() -> None:
    assert formatar_dinheiro_br(1234567.89) == "R$ 1.234.567,89"


def test_valor_simples_sem_milhar() -> None:
    assert formatar_dinheiro_br(280) == "R$ 280,00"


def test_aceita_string_decimal_do_backend() -> None:
    """Backend serializa Decimal como string JSON (``"280.00"``)."""
    assert formatar_dinheiro_br("280.00") == "R$ 280,00"


@pytest.mark.parametrize("vazio", [None, "", 0])
def test_none_vazio_e_zero_viram_zero(vazio: object) -> None:
    """``float(None)`` explodia nos 3 callers antigos — aqui vira zero."""
    assert formatar_dinheiro_br(vazio) == "R$ 0,00"


def test_prefixo_customizavel() -> None:
    assert formatar_dinheiro_br(50, prefixo="Total: R$ ") == "Total: R$ 50,00"


def test_string_nao_numerica_propaga_value_error() -> None:
    with pytest.raises(ValueError, match="could not convert string to float"):
        formatar_dinheiro_br("abc")
