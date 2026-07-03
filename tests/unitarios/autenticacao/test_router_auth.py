from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.dominio.papel import Papel
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
    token_type="bearer",
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
            # token_type propagado do DTO da aplicacao (fonte unica), nao
            # de um default duplicado no schema.
            assert data["token_type"] == "bearer"

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
                json={
                    "email": "new@test.com",
                    "senha": "senhaforte123",
                    "papel": "mecanico",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["email"] == "user@test.com"
            assert data["papel"] == "admin"
            # O router deve propagar o papel do request ate o DTO (#84).
            dto = mock_uc.executar.call_args.args[0]
            assert dto.papel is Papel.MECANICO

    def test_registrar_sem_papel_retorna_422(self) -> None:
        # Omitir papel nao pode criar usuario (e muito menos um ADMIN): 422.
        app = _criar_app()
        with patch(
            "src.autenticacao.interfaces.router.obter_registrar"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/autenticacao/registrar",
                json={"email": "new@test.com", "senha": "senhaforte123"},
            )
            assert resp.status_code == 422
            mock_uc.executar.assert_not_called()

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

    def test_logout_sem_header_retorna_401(self) -> None:
        # HTTPBearer(auto_error=False) + 401 manual (#167): header ausente e
        # falta de AUTENTICACAO (401 com WWW-Authenticate e mensagem PT), nao
        # o 403 generico do HTTPBearer default.
        app = _criar_app()
        with patch("src.autenticacao.interfaces.router.obter_logout") as mock_factory:
            mock_uc = MagicMock()
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post("/api/v1/autenticacao/logout")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Token de autenticacao nao fornecido"
            assert resp.headers["WWW-Authenticate"] == "Bearer"
            mock_uc.executar.assert_not_called()

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
