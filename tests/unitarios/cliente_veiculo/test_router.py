from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.cliente_veiculo.aplicacao.dtos import (
    ClienteDTO,
    ClienteResumoDTO,
    VeiculoDTO,
)
from src.cliente_veiculo.interfaces.router import (
    adicionar_veiculo,
    atualizar_cliente,
    desativar_cliente,
    listar_veiculos,
    obter_cliente,
    remover_veiculo,
    router,
)
from src.cliente_veiculo.interfaces.schemas import (
    AdicionarVeiculoRequest,
    AtualizarClienteRequest,
)
from src.compartilhado.interfaces.dependencies import obter_session

_ID = uuid4()
_VEICULO_ID = uuid4()

# DTOs reais sao `@dataclass(frozen=True, slots=True)` — sem `__dict__`.
# Usar os tipos concretos nos mocks garante que o router realmente converte
# via `dataclasses.asdict()` e impede regressao do bug do PR 58.
_VEICULO_DTO = VeiculoDTO(
    id=_VEICULO_ID,
    placa="ABC1234",
    marca="Fiat",
    modelo="Uno",
    ano=2020,
)
_CLIENTE_DTO = ClienteDTO(
    id=_ID,
    nome="Joao Silva",
    documento_formatado="123.456.789-00",
    documento_mascarado="***.***.***-00",
    tipo_documento="cpf",
    contato="11999990000",
    ativo=True,
    veiculos=[_VEICULO_DTO],
)
_CLIENTE_RESUMO_DTO = ClienteResumoDTO(
    id=_ID,
    nome="Joao Silva",
    documento_mascarado="***.***.***-00",
    tipo_documento="cpf",
    contato="11999990000",
    ativo=True,
)
_USUARIO = {"sub": str(uuid4()), "papel": "admin"}


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    mock_session = MagicMock()
    app.dependency_overrides[obter_session] = lambda: mock_session
    # Note: nao sobrescrevemos `obter_usuario_atual` aqui porque o stub
    # `exigir_papel` chama a funcao diretamente (nao via `Depends`); o stub
    # retorna sempre um usuario admin valido em testes, entao as rotas passam.
    return app


class TestRouter:
    def test_quantidade_de_rotas(self) -> None:
        assert len(router.routes) == 8

    def test_rotas_registradas(self) -> None:
        # Compara conjunto de (path, method) ignorando HEAD (auto-adicionado
        # pelo Starlette para toda rota GET) para evitar teste flaky quando
        # `next(iter(r.methods))` escolheria um valor arbitrario.
        paths_methods = {
            (r.path, method)
            for r in router.routes
            if hasattr(r, "methods")
            for method in r.methods  # type: ignore[union-attr]
            if method != "HEAD"
        }
        esperado = {
            ("/api/v1/clientes/", "POST"),
            ("/api/v1/clientes/", "GET"),
            ("/api/v1/clientes/{cliente_id}", "GET"),
            ("/api/v1/clientes/{cliente_id}", "PUT"),
            ("/api/v1/clientes/{cliente_id}", "DELETE"),
            ("/api/v1/clientes/{cliente_id}/veiculos", "POST"),
            ("/api/v1/clientes/{cliente_id}/veiculos", "GET"),
            ("/api/v1/clientes/{cliente_id}/veiculos/{veiculo_id}", "DELETE"),
        }
        assert paths_methods == esperado

    def test_criar_cliente(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_criar_cliente"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _CLIENTE_DTO
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/clientes/",
                json={
                    "nome": "Joao Silva",
                    "documento": "12345678900",
                    "tipo_documento": "cpf",
                    "contato": "11999990000",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["id"] == str(_ID)
            assert body["nome"] == "Joao Silva"

    def test_listar_clientes(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_listar_clientes"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = [_CLIENTE_RESUMO_DTO]
            mock_uc.contar.return_value = 1
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/clientes/")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert len(body["items"]) == 1
            assert body["items"][0]["id"] == str(_ID)

    def test_obter_cliente_direto(self) -> None:
        with patch("src.cliente_veiculo.interfaces.router.obter_obter_cliente") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_CLIENTE_DTO))
            result = obter_cliente(_ID, _USUARIO, MagicMock())
            assert result.id == _ID
            assert result.nome == "Joao Silva"

    def test_atualizar_cliente_direto(self) -> None:
        body = AtualizarClienteRequest(nome="Novo", contato="11000000000")
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_atualizar_cliente"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_CLIENTE_DTO))
            result = atualizar_cliente(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_desativar_cliente_direto(self) -> None:
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_desativar_cliente"
        ) as m:
            mock_uc = MagicMock()
            m.return_value = mock_uc
            desativar_cliente(_ID, _USUARIO, MagicMock())
            mock_uc.executar.assert_called_once_with(_ID)

    def test_adicionar_veiculo_direto(self) -> None:
        body = AdicionarVeiculoRequest(
            placa="ABC1234", marca="Fiat", modelo="Uno", ano=2020
        )
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_adicionar_veiculo"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_VEICULO_DTO))
            result = adicionar_veiculo(_ID, body, _USUARIO, MagicMock())
            assert result.id == _VEICULO_ID
            assert result.placa == "ABC1234"

    def test_listar_veiculos_direto(self) -> None:
        with patch("src.cliente_veiculo.interfaces.router.obter_listar_veiculos") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=[_VEICULO_DTO]))
            result = listar_veiculos(_ID, _USUARIO, MagicMock())
            assert len(result) == 1
            assert result[0].id == _VEICULO_ID

    def test_remover_veiculo_direto(self) -> None:
        vid = uuid4()
        with patch("src.cliente_veiculo.interfaces.router.obter_remover_veiculo") as m:
            mock_uc = MagicMock()
            m.return_value = mock_uc
            remover_veiculo(_ID, vid, _USUARIO, MagicMock())
            mock_uc.executar.assert_called_once_with(_ID, vid)
