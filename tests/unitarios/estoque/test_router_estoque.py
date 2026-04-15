from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces.dependencies import obter_session
from src.estoque.aplicacao.dtos import ItemEstoqueDTO
from src.estoque.interfaces.router import (
    ajustar_quantidade,
    atualizar_item,
    desativar_item,
    obter_item,
    router,
)
from src.estoque.interfaces.schemas import (
    AjustarQuantidadeRequest,
    AtualizarItemEstoqueRequest,
)

_ID = uuid4()

# DTOs reais (frozen slots dataclass) garantem que o router exercite a
# conversao via dataclasses.asdict().
_ITEM_DTO = ItemEstoqueDTO(
    id=_ID,
    nome="Filtro de oleo",
    descricao="Filtro padrao",
    quantidade=10,
    preco_unitario=Decimal("25.50"),
    moeda="BRL",
    ativo=True,
)
_USUARIO = {"sub": str(uuid4()), "papel": "admin"}


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    mock_session = MagicMock()
    app.dependency_overrides[obter_session] = lambda: mock_session
    return app


class TestEstoqueRouter:
    def test_quantidade_de_rotas(self) -> None:
        assert len(router.routes) == 6

    def test_rotas_registradas(self) -> None:
        paths_methods = {
            (r.path, method)
            for r in router.routes
            if hasattr(r, "methods")
            for method in r.methods  # type: ignore[union-attr]
            if method != "HEAD"
        }
        esperado = {
            ("/api/v1/estoque/", "POST"),
            ("/api/v1/estoque/", "GET"),
            ("/api/v1/estoque/{item_id}", "GET"),
            ("/api/v1/estoque/{item_id}", "PUT"),
            ("/api/v1/estoque/{item_id}", "DELETE"),
            ("/api/v1/estoque/{item_id}/quantidade", "PATCH"),
        }
        assert paths_methods == esperado

    def test_criar_item(self) -> None:
        app = _criar_app()
        with patch("src.estoque.interfaces.router.obter_criar_item") as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _ITEM_DTO
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/estoque/",
                json={
                    "nome": "Filtro de oleo",
                    "descricao": "Filtro padrao",
                    "quantidade": 10,
                    "preco_unitario": "25.50",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["id"] == str(_ID)
            assert body["nome"] == "Filtro de oleo"
            assert body["quantidade"] == 10

    def test_listar_itens(self) -> None:
        app = _criar_app()
        with patch("src.estoque.interfaces.router.obter_listar_itens") as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = [_ITEM_DTO]
            mock_uc.contar.return_value = 1
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/estoque/")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert len(body["items"]) == 1
            assert body["items"][0]["id"] == str(_ID)

    def test_obter_item_direto(self) -> None:
        with patch("src.estoque.interfaces.router.obter_obter_item") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ITEM_DTO))
            result = obter_item(_ID, _USUARIO, MagicMock())
            assert result.id == _ID
            assert result.nome == "Filtro de oleo"

    def test_atualizar_item_direto(self) -> None:
        body = AtualizarItemEstoqueRequest(
            nome="Novo",
            descricao="Desc",
            preco_unitario=Decimal("30"),
        )
        with patch("src.estoque.interfaces.router.obter_atualizar_item") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ITEM_DTO))
            result = atualizar_item(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_ajustar_quantidade_direto(self) -> None:
        body = AjustarQuantidadeRequest(nova_quantidade=20)
        with patch("src.estoque.interfaces.router.obter_ajustar_quantidade") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ITEM_DTO))
            result = ajustar_quantidade(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_desativar_item_direto(self) -> None:
        with patch("src.estoque.interfaces.router.obter_desativar_item") as m:
            mock_uc = MagicMock()
            m.return_value = mock_uc
            desativar_item(_ID, _USUARIO, MagicMock())
            mock_uc.executar.assert_called_once_with(_ID)
