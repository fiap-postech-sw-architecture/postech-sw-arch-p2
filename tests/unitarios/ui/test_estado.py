from __future__ import annotations

import pytest

from ui.estado import Sessao, StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore()


def test_sessao_inicial_e_vazia(store: StateStore) -> None:
    assert store.token_atual() is None
    assert store.papel_atual() is None
    assert store.email_atual() is None


def test_salvar_sessao_persiste_campos(store: StateStore) -> None:
    store.salvar_sessao(
        Sessao(
            access_token="abc",
            refresh_token="xyz",
            email="admin@pytstop.dev",
            papel="admin",
        )
    )
    assert store.token_atual() == "abc"
    assert store.refresh_token_atual() == "xyz"
    assert store.email_atual() == "admin@pytstop.dev"
    assert store.papel_atual() == "admin"


def test_limpar_sessao_reseta_tudo(store: StateStore) -> None:
    store.salvar_sessao(
        Sessao(access_token="abc", refresh_token="xyz", email="a@b", papel="admin")
    )
    store.limpar_sessao()
    assert store.token_atual() is None
    assert store.papel_atual() is None


def test_obter_store_retorna_singleton_quando_nao_configurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ui import estado

    monkeypatch.setattr(estado, "_store", None)
    s1 = estado.obter_store()
    s2 = estado.obter_store()
    assert s1 is s2


def test_configurar_store_sobrescreve_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ui import estado

    monkeypatch.setattr(estado, "_store", None)
    custom = estado.StateStore()
    estado.configurar_store(custom)
    assert estado.obter_store() is custom
