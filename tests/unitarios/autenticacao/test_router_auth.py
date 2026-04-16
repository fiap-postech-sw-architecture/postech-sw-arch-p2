from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.interfaces.middleware import obter_usuario_atual
from src.autenticacao.interfaces.router import router
from src.compartilhado.interfaces.dependencies import obter_session


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    mock_session = MagicMock()
    app.dependency_overrides[obter_session] = lambda: mock_session
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": str(uuid4()),
        "papel": "admin",
    }
    return app


_TOKEN_NS = SimpleNamespace(
    access_token="access-abc",
    refresh_token="refresh-xyz",
)

_USUARIO_NS = SimpleNamespace(
    id=uuid4(),
    email="user@test.com",
    papel="admin",
)


class TestAuthRouter:
    def test_login(self) -> None:
        app = _criar_app()
        with patch("src.autenticacao.interfaces.router.obter_login") as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _TOKEN_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/autenticacao/login",
                json={"email": "user@test.com", "senha": "senhaforte123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["access_token"] == "access-abc"
            assert data["refresh_token"] == "refresh-xyz"

    def test_registrar(self) -> None:
        app = _criar_app()
        with patch(
            "src.autenticacao.interfaces.router.obter_registrar"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _USUARIO_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/autenticacao/registrar",
                json={"email": "new@test.com", "senha": "senhaforte123"},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["email"] == "user@test.com"
            assert data["papel"] == "admin"

    def test_logout(self) -> None:
        app = _criar_app()
        with patch("src.autenticacao.interfaces.router.obter_logout") as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = {"mensagem": "Logout realizado"}
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/autenticacao/logout",
                headers={"Authorization": "Bearer token-fake-123"},
            )
            assert resp.status_code == 200

    def test_refresh(self) -> None:
        app = _criar_app()
        with patch(
            "src.autenticacao.interfaces.router.obter_refresh_token"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _TOKEN_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/autenticacao/refresh",
                json={"refresh_token": "refresh-xyz"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["access_token"] == "access-abc"
