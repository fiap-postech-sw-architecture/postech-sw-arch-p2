"""Testa a formatacao de preco no catalogo.

Regressao pinada: backend serializa ``Decimal`` como string JSON (ex.:
``"280.00"``). Se a UI tentar formatar esse valor direto com ``:.2f`` SEM o
cast explicito para ``float``, o Python levanta ``TypeError`` e a pagina
``/catalogo`` retorna 500 no browser. Esse foi o bug 3 reportado na validacao
manual.

Desde o #174 a formatacao delega pro helper compartilhado
``ui.formatacao.formatar_dinheiro_br`` (padrao brasileiro ``R$ 1.234,56``).
"""

from __future__ import annotations

import pytest

from ui.paginas.catalogo import _formatar_preco_servico


def test_formatar_preco_aceita_string_do_backend() -> None:
    """Bug 3: backend serializa Decimal como string JSON. Sem float() antes do
    format, f-string ``:.2f`` raise TypeError e a pagina vai pra 500."""
    assert _formatar_preco_servico("280.00") == "R$ 280,00"


def test_formatar_preco_aceita_float() -> None:
    assert _formatar_preco_servico(280.0) == "R$ 280,00"


def test_formatar_preco_aceita_int() -> None:
    assert _formatar_preco_servico(280) == "R$ 280,00"


def test_formatar_preco_usa_padrao_brasileiro_com_milhar() -> None:
    assert _formatar_preco_servico(1234.56) == "R$ 1.234,56"


def test_formatar_preco_zero_explicito() -> None:
    assert _formatar_preco_servico(0) == "R$ 0,00"


def test_formatar_preco_none_vira_zero() -> None:
    """Defesa contra payload malformado do backend (``preco`` ausente)."""
    assert _formatar_preco_servico(None) == "R$ 0,00"


def test_formatar_preco_string_vazia_vira_zero() -> None:
    assert _formatar_preco_servico("") == "R$ 0,00"


def test_formatar_preco_rejeita_string_nao_numerica() -> None:
    """``float("abc")`` levanta ValueError — propagamos sem mascarar. A UI
    nao tenta adivinhar o valor; se o backend enviar lixo, algo quebrou mais
    em cima e o erro precisa estourar pra ser investigado."""
    with pytest.raises(ValueError, match="could not convert string to float"):
        _formatar_preco_servico("abc")
