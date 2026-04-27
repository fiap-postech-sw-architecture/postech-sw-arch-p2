from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ui.estado import RegistroHttp, Sessao, StateStore


@pytest.fixture
def store() -> StateStore:
    return StateStore(max_entradas_historico=3)


def test_sessao_inicial_e_vazia(store: StateStore) -> None:
    assert store.token_atual() is None
    assert store.papel_atual() is None
    assert store.email_atual() is None
    assert store.historico_http() == []


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


def test_registro_http_entra_no_inicio_do_historico(store: StateStore) -> None:
    r1 = _reg("GET", "/api/v1/clientes", 200)
    r2 = _reg("POST", "/api/v1/clientes", 201)
    store.registrar_chamada_http(r1)
    store.registrar_chamada_http(r2)
    hist = store.historico_http()
    assert hist[0] == r2
    assert hist[1] == r1


def test_historico_respeita_max_entradas(store: StateStore) -> None:
    for i in range(5):
        store.registrar_chamada_http(_reg("GET", f"/{i}", 200))
    hist = store.historico_http()
    assert len(hist) == 3
    # Com appendleft + maxlen=3, os mais recentes ficam e os mais antigos
    # (/0, /1) sao despejados. Ordem esperada: /4, /3, /2.
    assert hist[0].caminho == "/4"
    assert hist[1].caminho == "/3"
    assert hist[2].caminho == "/2"


def test_limpar_historico_esvazia(store: StateStore) -> None:
    store.registrar_chamada_http(_reg("GET", "/x", 200))
    store.limpar_historico_http()
    assert store.historico_http() == []


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
    custom = estado.StateStore(max_entradas_historico=7)
    estado.configurar_store(custom)
    assert estado.obter_store() is custom


def _reg(metodo: str, caminho: str, status: int) -> RegistroHttp:
    return RegistroHttp(
        timestamp=datetime.now(UTC),
        metodo=metodo,
        caminho=caminho,
        status=status,
        duracao_ms=10,
        request_body=None,
        response_body="{}",
        papel_no_momento="admin",
    )
