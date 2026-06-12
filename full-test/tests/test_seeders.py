"""Smoke tests dos seeders.

Os seeders de verdade (DB + API) sao exercidos pelos testes de journeys
(steps 5-8), rodando contra a instancia viva. Aqui validamos apenas as
funcoes puras e o shape das credenciais padrao.
"""

from __future__ import annotations

from full_test.seeders.seed_usuarios import credenciais_padrao


def test_credenciais_padrao_inclui_admin_mecanicos_atendentes() -> None:
    creds = credenciais_padrao(n_mecanicos=2, n_atendentes=3, admin_email="admin@x.com")
    papeis = [c.papel.value for c in creds]
    assert papeis.count("admin") == 1
    assert papeis.count("mecanico") == 2
    assert papeis.count("atendente") == 3


def test_credenciais_padrao_tem_emails_unicos() -> None:
    creds = credenciais_padrao(n_mecanicos=3, n_atendentes=3, admin_email="admin@x.com")
    emails = [c.email for c in creds]
    assert len(set(emails)) == len(emails)


def test_credenciais_padrao_senha_atende_minimo_do_app() -> None:
    # LoginRequest.senha: Field(min_length=12). Conferir no SystemClient.login.
    creds = credenciais_padrao(n_mecanicos=1, n_atendentes=1, admin_email="admin@x.com")
    for cred in creds:
        assert len(cred.senha) >= 12
