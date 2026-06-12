from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter
from src.compartilhado.interfaces.router_publico import router


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)
    # Stub da session para os testes — nao e usada no mock do use case.
    app.dependency_overrides[obter_session] = lambda: MagicMock()
    return app


class TestRouterPublico:
    def test_saude(self) -> None:
        app = _criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_acompanhamento_encontrado(self) -> None:
        """Happy path: use case retorna DTO -> 200 + AcompanhamentoResponse."""
        app = _criar_app()
        dto_ns = SimpleNamespace(
            status="em_execucao",
            criado_em=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
            atualizado_em=datetime(2026, 4, 1, 15, 30, tzinfo=UTC),
        )
        with patch(
            "src.ordem_servico.interfaces.dependencies.obter_consultar_acompanhamento"
        ) as factory:
            factory.return_value = MagicMock(executar=MagicMock(return_value=dto_ns))
            client = TestClient(app)
            resp = client.get(
                "/api/v1/acompanhamento",
                params={"placa": "ABC1D23", "documento": "12345678901"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "em_execucao"
            # RF-021: a consulta publica tambem informa `situacao` no
            # vocabulario do challenge ao lado do `status` tecnico.
            assert body["situacao"] == "Em execução"
            assert "criado_em" in body
            assert "atualizado_em" in body

    def test_acompanhamento_nao_encontrado_retorna_404(self) -> None:
        """Miss case: use case retorna None -> 404 (evita oracle attack)."""
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.dependencies.obter_consultar_acompanhamento"
        ) as factory:
            factory.return_value = MagicMock(executar=MagicMock(return_value=None))
            client = TestClient(app)
            resp = client.get(
                "/api/v1/acompanhamento",
                params={"placa": "XYZ0A00", "documento": "00000000000"},
            )
            assert resp.status_code == 404
            assert resp.json() == {"detail": "Ordem nao encontrada"}

    def test_acompanhamento_sem_parametros_retorna_422(self) -> None:
        """Query params faltando -> 422 (validation error do FastAPI)."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/acompanhamento")
        assert resp.status_code == 422

    def test_acompanhamento_placa_muito_curta_retorna_422(self) -> None:
        """Placa < 7 chars rejeitada via ``Query(min_length=7)``."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/acompanhamento",
            params={"placa": "AB1", "documento": "12345678901"},
        )
        assert resp.status_code == 422

    def test_acompanhamento_documento_muito_curto_retorna_422(self) -> None:
        """Documento < 11 chars rejeitado via ``Query(min_length=11)``."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.get(
            "/api/v1/acompanhamento",
            params={"placa": "ABC1D23", "documento": "123"},
        )
        assert resp.status_code == 422
