"""Testes de sessao/transporte do ClienteApi (issues #170/#174).

Arquivo separado de ``test_cliente_api.py`` (que cobre o mapeamento
status->excecao e os helpers por endpoint): aqui ficam os fluxos novos de
revogacao no logout, TransportError, refresh serializado por lock, 401
terminal limpando a sessao e o 404 tipado.
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import httpx
import pytest

from ui.cliente_api import (
    BackendInacessivelError,
    ClienteApi,
    NaoAutenticadoError,
    NaoEncontradoError,
    RateLimitExcedidoError,
    ValidacaoError,
)
from ui.estado import Sessao, StateStore

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def store() -> StateStore:
    return StateStore()


def _transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# ----- logout revoga o refresh token no backend (bug 1 do #170) -----


def test_logout_envia_refresh_token_no_body(store: StateStore) -> None:
    """O backend so revoga o refresh token quando ele vem no body do POST
    /logout (campo opcional, issue #118). Sem o body, o logout da UI deixava
    o refresh token valido ate expirar."""
    store.salvar_sessao(Sessao("tok-acesso", "tok-refresh", "a@b", "admin"))
    capturado: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        capturado["auth"] = request.headers.get("authorization")
        capturado["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.logout()

    assert capturado["path"] == "/api/v1/autenticacao/logout"
    assert capturado["auth"] == "Bearer tok-acesso"
    assert capturado["body"] == {"refresh_token": "tok-refresh"}
    assert store.sessao_atual() is None


def test_revogar_sessao_nao_toca_o_store(store: StateStore) -> None:
    """Usado pelo role switcher: revoga a sessao ANTIGA depois que o login
    novo ja gravou a sessao nova — nao pode limpar o store."""
    sessao_antiga = Sessao("tok-velho", "ref-velho", "a@b", "atendente")
    store.salvar_sessao(Sessao("tok-novo", "ref-novo", "a@b", "admin"))
    corpos: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json={})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.revogar_sessao(sessao_antiga)

    assert corpos == [{"refresh_token": "ref-velho"}]
    assert store.token_atual() == "tok-novo"


# ----- httpx.TransportError -> BackendInacessivelError (bug 4 do #170) -----


@pytest.mark.parametrize(
    "erro",
    [
        httpx.RemoteProtocolError("conexao resetada"),
        httpx.ReadError("leitura interrompida"),
        httpx.ConnectTimeout("timeout"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_transport_error_vira_backend_inacessivel(
    store: StateStore, erro: httpx.TransportError
) -> None:
    """Antes so ConnectError/TimeoutException eram mapeados; um
    RemoteProtocolError (proxy caindo no meio) vazava traceback cru."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise erro

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(BackendInacessivelError):
        api.get("/api/v1/saude")


def test_login_com_transport_error_vira_backend_inacessivel(
    store: StateStore,
) -> None:
    """O login usava ``_client.post`` cru — ConnectError estourava na cara do
    usuario como traceback httpx em vez de mensagem amigavel."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(BackendInacessivelError):
        api.login(email="a@b", senha="secret123456")
    assert store.sessao_atual() is None


# ----- refresh serializado por lock (fix 9 do #174) -----


def test_double_refresh_concorrente_usa_uma_unica_rotacao(
    store: StateStore,
) -> None:
    """Dois threads tomam 401 com o mesmo access token expirado. Sem o lock,
    ambos postavam o MESMO refresh token; com rotacao single-use no backend o
    segundo POST falhava e derrubava a sessao. Com o lock, o segundo thread
    re-le o estado ja renovado e nao gasta outra rotacao."""
    store.salvar_sessao(Sessao("T0", "R0", "a@b", "admin"))
    estado_backend = {"refresh_valido": "R0", "tokens_validos": set(), "geracao": 0}
    guarda = threading.Lock()
    barreira = threading.Barrier(2, timeout=5)
    refreshes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            body = json.loads(request.content)
            with guarda:
                refreshes.append(body["refresh_token"])
                if body["refresh_token"] != estado_backend["refresh_valido"]:
                    # Rotacao single-use: reuso de refresh token e rejeitado.
                    return httpx.Response(401)
                estado_backend["geracao"] += 1
                access = f"T{estado_backend['geracao']}"
                novo_refresh = f"R{estado_backend['geracao']}"
                estado_backend["refresh_valido"] = novo_refresh
                estado_backend["tokens_validos"].add(access)
            return httpx.Response(
                200,
                json={
                    "access_token": access,
                    "refresh_token": novo_refresh,
                    "token_type": "bearer",
                },
            )
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ")
        with guarda:
            valido = token in estado_backend["tokens_validos"]
        if valido:
            return httpx.Response(200, json={"ok": True})
        # Ambos os threads chegam aqui com T0 expirado antes de qualquer
        # refresh acontecer — a barreira garante a concorrencia real.
        if token == "T0":
            barreira.wait()
        return httpx.Response(401, json={"detail": "token expirado"})

    # Duas instancias (obter_api cria uma por chamada) com o MESMO store:
    # o lock precisa ser por store, nao por instancia.
    api_a = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api_b = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))

    resultados: list[object] = []
    erros: list[BaseException] = []

    def chamar(api: ClienteApi) -> None:
        try:
            resultados.append(api.get("/api/v1/clientes"))
        except Exception as exc:  # teste captura falhas de thread pra reportar
            erros.append(exc)

    t1 = threading.Thread(target=chamar, args=(api_a,))
    t2 = threading.Thread(target=chamar, args=(api_b,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert erros == []
    assert resultados == [{"ok": True}, {"ok": True}]
    # Uma unica rotacao: o segundo thread reaproveitou a sessao renovada.
    assert refreshes == ["R0"]
    assert store.token_atual() == "T1"


def test_refresh_com_lock_continua_funcionando_em_thread_unica(
    store: StateStore,
) -> None:
    """Sanidade: o caminho single-thread (401 -> refresh -> retry) segue igual."""
    store.salvar_sessao(Sessao("expired", "valid-refresh", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "novo-token",
                    "refresh_token": "novo-refresh",
                    "token_type": "bearer",
                },
            )
        if request.headers.get("authorization") == "Bearer novo-token":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    assert api.get("/api/v1/clientes") == {"ok": True}
    assert store.refresh_token_atual() == "novo-refresh"


# ----- 401 terminal limpa a sessao (fix 10 do #174) -----


def test_401_apos_refresh_bem_sucedido_limpa_sessao(store: StateStore) -> None:
    """Refresh funciona mas o retry ainda leva 401 (ex.: usuario desativado):
    a sessao morta nao pode ficar no storage — proximo render redireciona
    pro /login em vez de repetir o ciclo com tokens invalidos."""
    store.salvar_sessao(Sessao("expired", "valid-refresh", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "novo-token",
                    "refresh_token": "novo-refresh",
                    "token_type": "bearer",
                },
            )
        return httpx.Response(401, json={"detail": "usuario desativado"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")
    assert store.sessao_atual() is None


# ----- 404 tipado (fix 12 do #174) -----


def test_404_vira_nao_encontrado_error(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Ordem nao encontrada"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoEncontradoError) as exc:
        api.get("/api/v1/ordens-de-servico/inexistente")
    assert "Ordem nao encontrada" in str(exc.value)


def test_404_sem_detail_usa_mensagem_amigavel(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoEncontradoError) as exc:
        api.get("/api/v1/clientes/x")
    assert "Recurso nao encontrado" in str(exc.value)


# ----- fallbacks de parsing defensivo (NITs do #174) -----


def test_422_sem_body_json_vira_validacao_error_vazia(store: StateStore) -> None:
    """Gateway pode emitir 422 sem JSON; nao pode estourar JSONDecodeError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, content=b"unprocessable", headers={"content-type": "text/plain"}
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ValidacaoError) as exc:
        api.post("/api/v1/clientes", json_body={})
    assert exc.value.detalhes == []


def test_429_com_retry_after_nao_numerico_usa_default(store: StateStore) -> None:
    """Retry-After pode vir como HTTP-date (RFC 9110); cai no default 60s."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(RateLimitExcedidoError) as exc:
        api.get("/api/v1/acompanhamento")
    assert exc.value.retry_after == 60
