from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.middleware import (
    SecurityHeadersMiddleware,
    configurar_cors,
    configurar_rate_limiting,
)


def _criar_app_com_saude() -> FastAPI:
    app = FastAPI()

    @app.get("/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestSecurityHeadersMiddleware:
    def test_headers_de_seguranca_aplicados(self) -> None:
        app = _criar_app_com_saude()
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp = client.get("/saude")

        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )
        assert resp.headers["Cache-Control"] == "no-store"
        assert resp.headers["Content-Security-Policy"] == "default-src 'none'"
        assert "X-Request-ID" in resp.headers

    def test_request_id_gerado_por_request(self) -> None:
        app = _criar_app_com_saude()
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp1 = client.get("/saude")
        resp2 = client.get("/saude")

        assert resp1.headers["X-Request-ID"] != resp2.headers["X-Request-ID"]

    def test_csp_nao_aplicado_em_rotas_de_docs(self) -> None:
        app = FastAPI()

        @app.get("/docs")
        def docs_stub() -> dict[str, str]:
            return {"page": "swagger"}

        @app.get("/openapi.json")
        def openapi_stub() -> dict[str, str]:
            return {"openapi": "3.1"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp_docs = client.get("/docs")
        assert "Content-Security-Policy" not in resp_docs.headers
        # Security headers still land even when CSP is skipped.
        assert resp_docs.headers["X-Content-Type-Options"] == "nosniff"

        resp_openapi = client.get("/openapi.json")
        assert "Content-Security-Policy" not in resp_openapi.headers


class TestConfigurarCors:
    def test_cors_sem_origens_configuradas(self, monkeypatch: object) -> None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)  # type: ignore[attr-defined]
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}

    def test_cors_com_origem_permitida(self, monkeypatch: object) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "https://allowed.example.com")  # type: ignore[attr-defined]
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://allowed.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://allowed.example.com"
        )

    def test_cors_com_multiplas_origens(self, monkeypatch: object) -> None:
        monkeypatch.setenv(  # type: ignore[attr-defined]
            "CORS_ORIGINS",
            "https://a.example.com, https://b.example.com",
        )
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://b.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin") == "https://b.example.com"
        )

    def test_cors_rejeita_wildcard_com_credenciais(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "*")
        app = _criar_app_com_saude()
        with pytest.raises(ValueError, match="CORS_ORIGINS='\\*'"):
            configurar_cors(app)


class TestConfigurarRateLimiting:
    def test_limiter_instalado_no_app(self) -> None:
        app = _criar_app_com_saude()
        configurar_rate_limiting(app)

        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None

    def test_limiter_permite_request_normal(self) -> None:
        app = _criar_app_com_saude()
        configurar_rate_limiting(app)

        client = TestClient(app)
        resp = client.get("/saude")
        assert resp.status_code == 200
