from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.router_publico import router


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


class TestRouterPublico:
    def test_saude(self) -> None:
        app = _criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
