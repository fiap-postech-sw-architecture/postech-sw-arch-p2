from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.main import criar_app


class TestCriarApp:
    def test_retorna_instancia_fastapi(self) -> None:
        app = criar_app()
        assert isinstance(app, FastAPI)

    def test_titulo_pytstop(self) -> None:
        app = criar_app()
        assert app.title == "PytStop"

    def test_health_endpoint_responde(self) -> None:
        app = criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_docs_habilitados_em_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "development")
        app = criar_app()
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_docs_desabilitados_em_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        app = criar_app()
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_limiter_configurado(self) -> None:
        app = criar_app()
        assert hasattr(app.state, "limiter")

    def test_security_headers_presentes(self) -> None:
        app = criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert "X-Request-ID" in resp.headers


def test_lifespan_configura_logging_e_mapeamentos() -> None:
    """Dispara o ciclo de vida do app via TestClient como context manager.

    Sem o ``with`` o lifespan nao executa (FastAPI/Starlette so invoca o
    startup+shutdown quando o TestClient e usado como context manager),
    entao as chamadas a ``configurar_logging`` e aos ``iniciar_mapeamentos``
    de cada contexto nao rodam nos testes de unidade.
    """
    app = criar_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
