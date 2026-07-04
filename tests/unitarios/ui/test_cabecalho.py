"""Testes do fluxo de troca de papel do cabecalho (bug 3 do #170).

A ordem importa: login novo PRIMEIRO; so depois de autenticado a sessao
antiga e revogada no backend. No fluxo antigo (logout -> login), uma falha
no login deixava o usuario deslogado e sem papel nenhum.

Nota de local: este arquivo fica na RAIZ de tests/unitarios/ui (nao em
``componentes/``) de proposito — ele importa ``ui.app`` em runtime, e o teste
de browser ``componentes/test_login.py`` (coletado antes dos arquivos desta
pasta) exige que nenhum teste anterior tenha registrado as rotas ``@ui.page``
no processo (ver ``_preservar_sys_modules_ui`` no conftest do pacote).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from ui.cliente_api import ClienteApi
from ui.componentes.cabecalho import CabecalhoApp
from ui.estado import Sessao, obter_store

if TYPE_CHECKING:
    from collections.abc import Callable

# {"alg":"HS256","typ":"JWT"} + {"email":"a@b","papel":"admin"} sem padding.
_HEADER_B64 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
_PAYLOAD_ADMIN_B64 = "eyJlbWFpbCI6ImFAYiIsInBhcGVsIjoiYWRtaW4ifQ"
_JWT_ADMIN = f"{_HEADER_B64}.{_PAYLOAD_ADMIN_B64}.assinatura-fake"


def _instalar_api(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    api = ClienteApi(
        base_url="http://x",
        store=obter_store(),
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr("ui.app.obter_api", lambda: api)


def _cabecalho_sem_render() -> CabecalhoApp:
    """Instancia sem rodar __init__ (que renderiza header NiceGUI)."""
    return CabecalhoApp.__new__(CabecalhoApp)


def test_trocar_papel_loga_antes_e_revoga_sessao_antiga_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = obter_store()
    store.salvar_sessao(Sessao("tok-antigo", "ref-antigo", "at@b", "atendente"))
    eventos: list[tuple[str, object]] = []
    reloads: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/login":
            eventos.append(("login", None))
            return httpx.Response(
                200,
                json={
                    "access_token": _JWT_ADMIN,
                    "refresh_token": "ref-novo",
                    "token_type": "bearer",
                },
            )
        if request.url.path == "/api/v1/autenticacao/logout":
            import json as _json

            eventos.append(
                (
                    "logout",
                    (
                        request.headers.get("authorization"),
                        _json.loads(request.content),
                    ),
                )
            )
            return httpx.Response(200, json={})
        return httpx.Response(500)

    _instalar_api(monkeypatch, handler)
    monkeypatch.setattr(
        "ui.componentes.cabecalho.ui.navigate.reload",
        lambda: reloads.append(True),
    )

    _cabecalho_sem_render()._trocar_papel("admin")

    # Ordem: login novo primeiro, revogacao da sessao antiga depois.
    assert [nome for nome, _ in eventos] == ["login", "logout"]
    # A revogacao usa os tokens ANTIGOS (a sessao nova ja esta no store).
    assert eventos[1][1] == (
        "Bearer tok-antigo",
        {"refresh_token": "ref-antigo"},
    )
    assert store.papel_atual() == "admin"
    assert store.token_atual() == _JWT_ADMIN
    assert reloads == [True]


def test_trocar_papel_com_login_falho_mantem_sessao_atual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = obter_store()
    store.salvar_sessao(Sessao("tok-antigo", "ref-antigo", "at@b", "atendente"))
    caminhos: list[str] = []
    notifies: list[tuple[str, dict[str, object]]] = []
    reloads: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        caminhos.append(request.url.path)
        return httpx.Response(401, json={"detail": "credenciais invalidas"})

    _instalar_api(monkeypatch, handler)
    monkeypatch.setattr(
        "ui.componentes.cabecalho.ui.notify",
        lambda msg, **kw: notifies.append((msg, kw)),
    )
    monkeypatch.setattr(
        "ui.componentes.cabecalho.ui.navigate.reload",
        lambda: reloads.append(True),
    )

    _cabecalho_sem_render()._trocar_papel("admin")

    # Sessao atual intacta (o bug antigo deslogava antes de tentar logar).
    assert store.papel_atual() == "atendente"
    assert store.token_atual() == "tok-antigo"
    # Nenhuma revogacao aconteceu; so a tentativa de login.
    assert caminhos == ["/api/v1/autenticacao/login"]
    assert len(notifies) == 1
    assert "Falha ao trocar papel" in notifies[0][0]
    assert reloads == []
