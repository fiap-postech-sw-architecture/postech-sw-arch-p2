"""Testes unitarios puros do ``router_admin`` (sem HTTP / sem banco).

A superficie HTTP auth-gated (autorizacao, contrato do reenfileiramento e o
audit de requeue ponta a ponta) e coberta em
``tests/integracao/test_admin_outbox.py``. Aqui exercitamos so a funcao pura
``_ator_de``, cujos ramos de fallback (``email``) e ausencia total (``None``)
nao sao alcancados pelo caminho normal do JWT (que sempre carrega ``sub``).
"""

from __future__ import annotations

from src.compartilhado.interfaces.router_admin import _ator_de


def test_ator_usa_sub_quando_presente() -> None:
    usuario = {"sub": "11111111-1111-1111-1111-111111111111", "email": "a@b.com"}
    assert _ator_de(usuario) == "11111111-1111-1111-1111-111111111111"


def test_ator_cai_para_email_sem_sub() -> None:
    # Sem `sub` (ou `sub` vazio/nao-string): usa o `email` como identificador.
    assert _ator_de({"email": "admin@oficina.com"}) == "admin@oficina.com"
    assert _ator_de({"sub": "", "email": "admin@oficina.com"}) == "admin@oficina.com"
    assert _ator_de({"sub": 123, "email": "admin@oficina.com"}) == "admin@oficina.com"


def test_ator_none_sem_sub_nem_email() -> None:
    # Nenhum identificador disponivel: audit ainda e emitido, so sem ator.
    assert _ator_de({}) is None
    assert _ator_de({"papel": "admin"}) is None
    assert _ator_de({"sub": None, "email": None}) is None
