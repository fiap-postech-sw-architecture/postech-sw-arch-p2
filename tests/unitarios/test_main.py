from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest
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
                patch(
                    "src.compartilhado.infraestrutura.database.criar_engine"
                ) as mock_engine,
                patch(
                    "src.compartilhado.infraestrutura.database.criar_session_factory"
                ) as mock_factory,
                patch(
                    "src.compartilhado.interfaces.dependencies.configurar_session_factory"
                ) as mock_configurar,
                # Fixa ambiente de teste para que o ramo de fail-fast de
                # DATABASE_URL em producao nao interfira (o ramo e coberto
                # em test_lifespan_sem_database_url_em_producao_falha).
                patch.dict(
                    os.environ,
                    {"ENVIRONMENT": "development"},
                    clear=False,
                ),
            ):
                mock_engine.return_value.dispose = lambda: None
                async with lifespan(app):
                    pass
                mock_logging.assert_called_once()
                mock_cliente.assert_called_once()
                mock_catalogo.assert_called_once()
                mock_estoque.assert_called_once()
                mock_os.assert_called_once()
                mock_auth.assert_called_once()
                mock_engine.assert_called_once()
                mock_factory.assert_called_once()
                mock_configurar.assert_called_once()

        asyncio.run(_run())

    def test_lifespan_configura_session_factory_com_database_url(self) -> None:
        app = FastAPI()
        url_customizada = "postgresql://custom:custom@remote:5433/db"

        async def _run() -> None:
            with (
                patch("src.compartilhado.infraestrutura.logging.configurar_logging"),
                patch("src.cliente_veiculo.infraestrutura.mapping.iniciar_mapeamentos"),
                patch(
                    "src.catalogo_servicos.infraestrutura.mapping.iniciar_mapeamentos"
                ),
                patch("src.estoque.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.ordem_servico.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.autenticacao.infraestrutura.mapping.iniciar_mapeamentos"),
                patch(
                    "src.compartilhado.infraestrutura.database.criar_engine"
                ) as mock_engine,
                patch(
                    "src.compartilhado.infraestrutura.database.criar_session_factory"
                ),
                patch(
                    "src.compartilhado.interfaces.dependencies.configurar_session_factory"
                ),
                patch.dict(os.environ, {"DATABASE_URL": url_customizada}, clear=False),
            ):
                mock_engine.return_value.dispose = lambda: None
                async with lifespan(app):
                    pass
                mock_engine.assert_called_once_with(url_customizada)

        asyncio.run(_run())

    def test_lifespan_sem_database_url_em_development_usa_default(self) -> None:
        app = FastAPI()
        default_dev = "postgresql://pytstop:pytstop@localhost:5432/pytstop"
        env_sem_db = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        env_sem_db["ENVIRONMENT"] = "development"

        async def _run() -> None:
            with (
                patch("src.compartilhado.infraestrutura.logging.configurar_logging"),
                patch("src.cliente_veiculo.infraestrutura.mapping.iniciar_mapeamentos"),
                patch(
                    "src.catalogo_servicos.infraestrutura.mapping.iniciar_mapeamentos"
                ),
                patch("src.estoque.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.ordem_servico.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.autenticacao.infraestrutura.mapping.iniciar_mapeamentos"),
                patch(
                    "src.compartilhado.infraestrutura.database.criar_engine"
                ) as mock_engine,
                patch(
                    "src.compartilhado.infraestrutura.database.criar_session_factory"
                ),
                patch(
                    "src.compartilhado.interfaces.dependencies.configurar_session_factory"
                ),
                patch.dict(os.environ, env_sem_db, clear=True),
            ):
                mock_engine.return_value.dispose = lambda: None
                async with lifespan(app):
                    pass
                mock_engine.assert_called_once_with(default_dev)

        asyncio.run(_run())

    def test_lifespan_sem_database_url_em_producao_falha(self) -> None:
        app = FastAPI()
        env_sem_db = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        env_sem_db["ENVIRONMENT"] = "production"

        async def _run() -> None:
            with (
                patch("src.compartilhado.infraestrutura.logging.configurar_logging"),
                patch("src.cliente_veiculo.infraestrutura.mapping.iniciar_mapeamentos"),
                patch(
                    "src.catalogo_servicos.infraestrutura.mapping.iniciar_mapeamentos"
                ),
                patch("src.estoque.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.ordem_servico.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.autenticacao.infraestrutura.mapping.iniciar_mapeamentos"),
                patch("src.compartilhado.infraestrutura.database.criar_engine"),
                patch(
                    "src.compartilhado.infraestrutura.database.criar_session_factory"
                ),
                patch(
                    "src.compartilhado.interfaces.dependencies.configurar_session_factory"
                ),
                patch.dict(os.environ, env_sem_db, clear=True),
            ):
                async with lifespan(app):
                    pass

        with pytest.raises(RuntimeError, match="DATABASE_URL obrigatoria"):
            asyncio.run(_run())
