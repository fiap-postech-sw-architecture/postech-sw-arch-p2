from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.interfaces.middleware import obter_usuario_atual
from src.cliente_veiculo.aplicacao.dtos import (
    ClienteDTO,
    ClienteResumoDTO,
    ConsentimentoDTO,
    VeiculoDTO,
)
from src.cliente_veiculo.interfaces.router import router
from src.compartilhado.interfaces.dependencies import obter_session

_ID = uuid4()
_VEICULO_ID = uuid4()
_CONSENTIMENTO_ID = uuid4()

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
_DADOS_PESSOAIS_DTO = ClienteDTO(
    id=_ID,
    nome="Joao Silva",
    documento_formatado="123.456.789-00",
    documento_mascarado="***.***.***-00",
    tipo_documento="cpf",
    contato="11999990000",
    ativo=True,
    veiculos=[_VEICULO_DTO],
)

_CONSENTIMENTO = ConsentimentoDTO(
    id=_CONSENTIMENTO_ID,
    cliente_id=_ID,
    tipo="marketing",
    concedido_em=datetime.datetime.now(datetime.UTC),
    revogado_em=None,
    ativo=True,
)


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


class TestRouter:
    def test_quantidade_de_rotas(self) -> None:
        assert len(router.routes) == 13

    def test_rotas_registradas(self) -> None:
        # Compara conjunto de (path, method) ignorando HEAD (auto-adicionado
        # pelo Starlette para toda rota GET) para evitar teste flaky quando
        # `next(iter(r.methods))` escolheria um valor arbitrario. Cobre
        # renomeacao de path e mudanca de metodo HTTP, que `len(...) == 13`
        # nao detecta.
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
            ("/api/v1/clientes/{cliente_id}/dados-pessoais", "GET"),
            ("/api/v1/clientes/{cliente_id}/dados-pessoais/exportar", "GET"),
            ("/api/v1/clientes/{cliente_id}/dados-pessoais", "DELETE"),
            ("/api/v1/clientes/{cliente_id}/consentimento", "POST"),
            ("/api/v1/clientes/{cliente_id}/consentimento", "DELETE"),
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
            # Valida `dataclasses.asdict()` em DTO frozen+slots — regressao do PR #58.
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
            assert resp.json()["total"] == 1

    def test_obter_cliente(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_obter_cliente") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_CLIENTE_DTO))
            client = TestClient(app)
            resp = client.get(f"/api/v1/clientes/{_ID}")
            assert resp.status_code == 200
            assert resp.json()["id"] == str(_ID)

    def test_atualizar_cliente(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_atualizar_cliente"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_CLIENTE_DTO))
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/clientes/{_ID}",
                json={"nome": "Novo Nome", "contato": "11000000000"},
            )
            assert resp.status_code == 200
            assert resp.json()["id"] == str(_ID)

    def test_desativar_cliente(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_desativar_cliente"
        ) as m:
            m.return_value = MagicMock()
            client = TestClient(app)
            resp = client.delete(f"/api/v1/clientes/{_ID}")
            assert resp.status_code == 204

    def test_adicionar_veiculo(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_adicionar_veiculo"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_VEICULO_DTO))
            client = TestClient(app)
            resp = client.post(
                f"/api/v1/clientes/{_ID}/veiculos",
                json={
                    "placa": "ABC1234",
                    "marca": "Fiat",
                    "modelo": "Uno",
                    "ano": 2020,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["placa"] == "ABC1234"

    def test_listar_veiculos(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_listar_veiculos") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=[_VEICULO_DTO]))
            client = TestClient(app)
            resp = client.get(f"/api/v1/clientes/{_ID}/veiculos")
            assert resp.status_code == 200
            assert len(resp.json()) == 1

    def test_remover_veiculo(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_remover_veiculo") as m:
            m.return_value = MagicMock()
            client = TestClient(app)
            resp = client.delete(f"/api/v1/clientes/{_ID}/veiculos/{_VEICULO_ID}")
            assert resp.status_code == 204

    def test_obter_dados_pessoais(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_exportar_dados") as m:
            m.return_value = MagicMock(
                executar=MagicMock(return_value=_DADOS_PESSOAIS_DTO)
            )
            client = TestClient(app)
            resp = client.get(f"/api/v1/clientes/{_ID}/dados-pessoais")
            assert resp.status_code == 200
            assert resp.json()["id"] == str(_ID)

    def test_exportar_dados_pessoais(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_exportar_dados") as m:
            m.return_value = MagicMock(
                executar=MagicMock(return_value=_DADOS_PESSOAIS_DTO)
            )
            client = TestClient(app)
            resp = client.get(f"/api/v1/clientes/{_ID}/dados-pessoais/exportar")
            assert resp.status_code == 200
            assert resp.json()["id"] == str(_ID)

    def test_excluir_dados_pessoais(self) -> None:
        app = _criar_app()
        with patch("src.cliente_veiculo.interfaces.router.obter_excluir_dados") as m:
            m.return_value = MagicMock()
            client = TestClient(app)
            resp = client.delete(f"/api/v1/clientes/{_ID}/dados-pessoais")
            assert resp.status_code == 204

    def test_registrar_consentimento(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_registrar_consentimento"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_CONSENTIMENTO))
            client = TestClient(app)
            resp = client.post(
                f"/api/v1/clientes/{_ID}/consentimento", json={"tipo": "marketing"}
            )
            assert resp.status_code == 201
            assert resp.json()["tipo"] == "marketing"

    def test_revogar_consentimento_endpoint(self) -> None:
        app = _criar_app()
        with patch(
            "src.cliente_veiculo.interfaces.router.obter_revogar_consentimento"
        ) as m:
            m.return_value = MagicMock()
            client = TestClient(app)
            resp = client.delete(f"/api/v1/clientes/{_ID}/consentimento?tipo=marketing")
            assert resp.status_code == 204


class TestLgpdAuditoriaEAutorizacao:
    """#76: erasure admin-only + trilha de auditoria em export/erasure de PII."""

    @staticmethod
    def _app_com_papel(papel: str) -> FastAPI:
        app = _criar_app()
        app.dependency_overrides[obter_usuario_atual] = lambda: {
            "sub": "ator-123",
            "papel": papel,
        }
        return app

    def test_excluir_dados_pessoais_negado_para_atendente(self) -> None:
        """Erasure e destrutivo -> admin-only: atendente recebe 403 e nao executa."""
        app = self._app_com_papel("atendente")
        with patch("src.cliente_veiculo.interfaces.router.obter_excluir_dados") as m:
            uc = MagicMock()
            m.return_value = uc
            client = TestClient(app)
            resp = client.delete(f"/api/v1/clientes/{_ID}/dados-pessoais")
        assert resp.status_code == 403
        uc.executar.assert_not_called()

    def test_excluir_dados_pessoais_admin_emite_auditoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Erasure por admin emite audit com ator + cliente_id apos o efeito."""
        import structlog.testing

        from src.cliente_veiculo.interfaces import router as router_mod

        monkeypatch.setattr(
            router_mod, "_log", structlog.get_logger("test_lgpd"), raising=False
        )
        app = self._app_com_papel("admin")
        with patch("src.cliente_veiculo.interfaces.router.obter_excluir_dados") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=None))
            client = TestClient(app)
            with structlog.testing.capture_logs() as logs:
                resp = client.delete(f"/api/v1/clientes/{_ID}/dados-pessoais")
        assert resp.status_code == 204
        evento = next(
            e for e in logs if e["event"] == "dados_pessoais_excluidos_via_admin"
        )
        assert evento["cliente_id"] == str(_ID)
        assert evento["ator"] == "ator-123"

    def test_exportar_dados_pessoais_emite_auditoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Export de PII (atendente permitido) emite audit com ator + cliente_id."""
        import structlog.testing

        from src.cliente_veiculo.interfaces import router as router_mod

        monkeypatch.setattr(
            router_mod, "_log", structlog.get_logger("test_lgpd"), raising=False
        )
        app = self._app_com_papel("atendente")
        with patch("src.cliente_veiculo.interfaces.router.obter_exportar_dados") as m:
            m.return_value = MagicMock(
                executar=MagicMock(return_value=_DADOS_PESSOAIS_DTO)
            )
            client = TestClient(app)
            with structlog.testing.capture_logs() as logs:
                resp = client.get(f"/api/v1/clientes/{_ID}/dados-pessoais/exportar")
        assert resp.status_code == 200
        evento = next(
            e for e in logs if e["event"] == "dados_pessoais_exportados_via_admin"
        )
        assert evento["cliente_id"] == str(_ID)
        assert evento["ator"] == "ator-123"

    def test_obter_dados_pessoais_emite_auditoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O GET /dados-pessoais tambem expoe PII -> tambem audita."""
        import structlog.testing

        from src.cliente_veiculo.interfaces import router as router_mod

        monkeypatch.setattr(
            router_mod, "_log", structlog.get_logger("test_lgpd"), raising=False
        )
        app = self._app_com_papel("admin")
        with patch("src.cliente_veiculo.interfaces.router.obter_exportar_dados") as m:
            m.return_value = MagicMock(
                executar=MagicMock(return_value=_DADOS_PESSOAIS_DTO)
            )
            client = TestClient(app)
            with structlog.testing.capture_logs() as logs:
                resp = client.get(f"/api/v1/clientes/{_ID}/dados-pessoais")
        assert resp.status_code == 200
        assert any(e["event"] == "dados_pessoais_exportados_via_admin" for e in logs)

    def test_export_falho_nao_emite_auditoria(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Use case que levanta (cliente inexistente) NAO gera audit."""
        import structlog.testing

        from src.cliente_veiculo.dominio.exceptions import (
            ClienteNaoEncontradoException,
        )
        from src.cliente_veiculo.interfaces import router as router_mod

        monkeypatch.setattr(
            router_mod, "_log", structlog.get_logger("test_lgpd"), raising=False
        )
        app = self._app_com_papel("admin")
        with patch("src.cliente_veiculo.interfaces.router.obter_exportar_dados") as m:
            m.return_value = MagicMock(
                executar=MagicMock(side_effect=ClienteNaoEncontradoException())
            )
            client = TestClient(app, raise_server_exceptions=False)
            with structlog.testing.capture_logs() as logs:
                resp = client.get(f"/api/v1/clientes/{_ID}/dados-pessoais/exportar")
        assert resp.status_code >= 400
        assert not [
            e for e in logs if e["event"] == "dados_pessoais_exportados_via_admin"
        ]
