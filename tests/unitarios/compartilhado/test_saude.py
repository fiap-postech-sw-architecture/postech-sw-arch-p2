from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.router_publico import router


def test_saude_retorna_ok() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/saude")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
