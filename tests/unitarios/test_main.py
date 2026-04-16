from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.main import criar_app, lifespan


class TestMain:
    def test_criar_app_retorna_fastapi(self) -> None:
        application = criar_app()
        assert isinstance(application, FastAPI)

    def test_titulo(self) -> None:
        application = criar_app()
        assert application.title == "PytStop"

    def test_routers_montados(self) -> None:
        application = criar_app()
        paths = {r.path for r in application.routes if hasattr(r, "path")}
        assert "/api/v1/saude" in paths
        assert any("/api/v1/clientes" in p for p in paths)
        assert any("/api/v1/servicos" in p for p in paths)
        assert any("/api/v1/estoque" in p for p in paths)
        assert any("/api/v1/ordens-de-servico" in p for p in paths)
        assert any("/api/v1/autenticacao" in p for p in paths)

    def test_versao(self) -> None:
        from importlib.metadata import version

        application = criar_app()
        assert application.version == version("pytstop")

    def test_middleware_registrado(self) -> None:
        application = criar_app()
        middleware_classes = [m.cls.__name__ for m in application.user_middleware]
        assert "SecurityHeadersMiddleware" in middleware_classes

    def test_docs_url_em_development(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=False):
            application = criar_app()
            assert application.docs_url == "/docs"
            assert application.redoc_url == "/redoc"

    def test_docs_url_em_production(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            application = criar_app()
            assert application.docs_url is None
            assert application.redoc_url is None

    def test_openapi_schema_gera_sem_erro(self) -> None:
        """Garante que /openapi.json e gerado com sucesso.

        Pega regressoes de from __future__ import annotations vs Pydantic
        (ForwardRef nao resolvido) e qualquer schema Pydantic malformado
        antes de chegar a producao.
        """
        app = criar_app()
        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["openapi"].startswith("3.")
        assert len(schema["paths"]) > 0

    def test_lifespan_executa_mapeamentos(self) -> None:
        app = FastAPI()

        async def _run() -> None:
            with (
                patch(
                    "src.compartilhado.infraestrutura.logging.configurar_logging"
                ) as mock_logging,
                patch(
                    "src.cliente_veiculo.infraestrutura.mapping.iniciar_mapeamentos"
                ) as mock_cliente,
                patch(
                    "src.catalogo_servicos.infraestrutura.mapping.iniciar_mapeamentos"
                ) as mock_catalogo,
                patch(
                    "src.estoque.infraestrutura.mapping.iniciar_mapeamentos"
                ) as mock_estoque,
                patch(
                    "src.ordem_servico.infraestrutura.mapping.iniciar_mapeamentos"
                ) as mock_os,
                patch(
                    "src.autenticacao.infraestrutura.mapping.iniciar_mapeamentos"
                ) as mock_auth,
            ):
                async with lifespan(app):
                    pass
                mock_logging.assert_called_once()
                mock_cliente.assert_called_once()
                mock_catalogo.assert_called_once()
                mock_estoque.assert_called_once()
                mock_os.assert_called_once()
                mock_auth.assert_called_once()

        asyncio.run(_run())
