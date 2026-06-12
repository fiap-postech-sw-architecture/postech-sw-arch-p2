from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import criar_app

pytestmark = pytest.mark.e2e


class TestSaudeE2E:
    def test_saude_endpoint(self) -> None:
        app = criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
