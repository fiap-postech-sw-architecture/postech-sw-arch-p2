from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.interfaces.middleware import obter_usuario_atual
from src.catalogo_servicos.aplicacao.dtos import ServicoDTO
from src.catalogo_servicos.interfaces.router import (
    atualizar_servico,
    desativar_servico,
    obter_servico,
    router,
)
from src.catalogo_servicos.interfaces.schemas import AtualizarServicoRequest
from src.compartilhado.interfaces.dependencies import obter_session

_ID = uuid4()

# Usar ServicoDTO concreto (frozen dataclass com slots) garante que o router
# exercite a conversao via dataclasses.asdict().
_SERVICO_DTO = ServicoDTO(
    id=_ID,
    nome="Troca de oleo",
    descricao="Troca completa",
    preco=Decimal("100.00"),
    moeda="BRL",
    ativo=True,
)
_USUARIO = {"sub": str(uuid4()), "papel": "admin"}


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    mock_session = MagicMock()
    app.dependency_overrides[obter_session] = lambda: mock_session
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": str(uuid4()),
        "papel": "admin",
    }
    return app


class TestCatalogoRouter:
    def test_quantidade_de_rotas(self) -> None:
        assert len(router.routes) == 5

    def test_rotas_registradas(self) -> None:
        paths_methods = {
            (r.path, method)
            for r in router.routes
            if hasattr(r, "methods")
            for method in r.methods  # type: ignore[union-attr]
            if method != "HEAD"
        }
        esperado = {
            ("/api/v1/servicos/", "POST"),
            ("/api/v1/servicos/", "GET"),
            ("/api/v1/servicos/{servico_id}", "GET"),
            ("/api/v1/servicos/{servico_id}", "PUT"),
            ("/api/v1/servicos/{servico_id}", "DELETE"),
        }
        assert paths_methods == esperado

    def test_criar_servico(self) -> None:
        app = _criar_app()
        with patch(
            "src.catalogo_servicos.interfaces.router.obter_criar_servico"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _SERVICO_DTO
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/servicos/",
                json={
                    "nome": "Troca de oleo",
                    "descricao": "Troca completa",
                    "preco": "100.00",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == str(_ID)
            assert data["nome"] == "Troca de oleo"
            assert data["ativo"] is True

    def test_listar_servicos(self) -> None:
        app = _criar_app()
        with patch(
            "src.catalogo_servicos.interfaces.router.obter_listar_servicos"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = [_SERVICO_DTO]
            mock_uc.contar.return_value = 1
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/servicos/")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == str(_ID)

    def test_obter_servico_direto(self) -> None:
        with patch(
            "src.catalogo_servicos.interfaces.router.obter_obter_servico"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _SERVICO_DTO
            mock_factory.return_value = mock_uc

            result = obter_servico(_ID, _USUARIO, MagicMock())
            assert result.id == _ID
            assert result.nome == "Troca de oleo"

    def test_atualizar_servico_direto(self) -> None:
        body = AtualizarServicoRequest(
            nome="Novo nome",
            descricao="Nova desc",
            preco=Decimal("200.00"),
        )
        with patch(
            "src.catalogo_servicos.interfaces.router.obter_atualizar_servico"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _SERVICO_DTO
            mock_factory.return_value = mock_uc

            result = atualizar_servico(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_desativar_servico_direto(self) -> None:
        with patch(
            "src.catalogo_servicos.interfaces.router.obter_desativar_servico"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_factory.return_value = mock_uc

            desativar_servico(_ID, _USUARIO, MagicMock())
            mock_uc.executar.assert_called_once_with(_ID)
