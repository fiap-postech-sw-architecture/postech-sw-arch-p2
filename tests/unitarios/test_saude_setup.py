from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


def test_saude_retorna_ok() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/saude")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
