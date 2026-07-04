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


# ----- storage corrompido (fix 16 do #174) -----


@pytest.mark.parametrize(
    "sessao_corrompida",
    [
        {},
        {"papel": "admin"},
        {"access_token": "a"},
        {"access_token": "a", "refresh_token": "r"},
        {"access_token": "a", "refresh_token": "r", "email": "a@b"},
        {"access_token": "a", "refresh_token": "r", "papel": "admin"},
    ],
    ids=[
        "vazio",
        "so-papel",
        "so-access",
        "sem-email-e-papel",
        "sem-papel",
        "sem-email",
    ],
)
def test_sessao_corrompida_sem_chaves_retorna_none(
    sessao_corrompida: dict[str, str],
) -> None:
    """Cookie truncado/versao antiga do dict de sessao: qualquer chave
    ausente vira 'sem sessao' — antes ``s["access_token"]`` estourava
    KeyError e derrubava a pagina inteira."""
    storage: dict[str, object] = {"sessao": sessao_corrompida}
    store = StateStore(user_storage=storage)
    assert store.sessao_atual() is None
    assert store.esta_autenticado() is False
    assert store.token_atual() is None


def test_sessao_com_papel_invalido_retorna_none() -> None:
    storage: dict[str, object] = {
        "sessao": {
            "access_token": "a",
            "refresh_token": "r",
            "email": "a@b",
            "papel": "superuser",
        }
    }
    store = StateStore(user_storage=storage)
    assert store.sessao_atual() is None


def test_sessao_completa_continua_valida() -> None:
    storage: dict[str, object] = {
        "sessao": {
            "access_token": "a",
            "refresh_token": "r",
            "email": "a@b",
            "papel": "admin",
        }
    }
    store = StateStore(user_storage=storage)
    sessao = store.sessao_atual()
    assert sessao is not None
    assert sessao.papel == "admin"
