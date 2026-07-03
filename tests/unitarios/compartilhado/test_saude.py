from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.router_publico import router
from src.main import criar_app


def test_saude_retorna_ok() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/saude")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_saude_atraves_do_app_completo() -> None:
    # Smoke movido de tests/e2e/ (diretorio removido): o teste acima monta so
    # o router; este atravessa o `criar_app()` REAL (middlewares, error
    # handler, wiring) — um middleware quebrado passaria no de cima e falharia
    # aqui. Sem lifespan/TestClient-context: /saude nao toca banco.
    client = TestClient(criar_app())
    resp = client.get("/api/v1/saude")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
