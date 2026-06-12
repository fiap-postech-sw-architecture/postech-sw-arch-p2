from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.interfaces.middleware import obter_usuario_atual
from src.compartilhado.interfaces.dependencies import obter_session
from src.ordem_servico.interfaces.router import (
    adicionar_item,
    aprovar_complementar,
    aprovar_orcamento,
    cancelar_ordem,
    finalizar_servico,
    gerar_complementar,
    gerar_orcamento,
    iniciar_diagnostico,
    obter_ordem,
    registrar_entrega,
    rejeitar_complementar,
    remover_item,
    router,
)
from src.ordem_servico.interfaces.schemas import (
    AdicionarItemRequest,
    CancelarOrdemRequest,
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


_ID = uuid4()
_NOW = datetime.now(tz=UTC)
_ORDEM_NS = SimpleNamespace(
    id=_ID,
    cliente_id=uuid4(),
    veiculo_id=uuid4(),
    status="recebida",
    itens=[],
    orcamento=None,
    criado_em=_NOW,
    atualizado_em=_NOW,
)
_RESUMO_NS = SimpleNamespace(
    id=_ID,
    cliente_id=uuid4(),
    veiculo_id=uuid4(),
    status="recebida",
    criado_em=_NOW,
)
_METRICAS_NS = SimpleNamespace(
    total=5,
    por_status={"recebida": 2, "em_diagnostico": 3},
)
_USUARIO = {"sub": str(uuid4()), "papel": "admin"}


class TestRouterOS:
    @pytest.fixture(autouse=True)
    def _patch_enriquecer_ordem(self) -> Iterator[None]:
        """Substitui ``EnriquecerOrdemDeServico`` por stub identidade.

        Os testes deste arquivo trocam DTOs reais por ``SimpleNamespace``
        para nao depender da camada de aplicacao. A query real chama
        ``dataclasses.replace`` no DTO antes de devolver — operacao que
        falha em ``SimpleNamespace``. O stub aqui devolve o input
        intacto, mantendo o foco do teste no router.
        """
        stub = MagicMock()
        stub.executar.side_effect = lambda dto: dto
        stub.executar_lote.side_effect = lambda dtos: dtos
        with patch(
            "src.ordem_servico.interfaces.router.obter_enriquecer_ordem",
            return_value=stub,
        ):
            yield

    def test_quantidade_de_rotas(self) -> None:
        assert len(router.routes) == 15

    def test_prefixo(self) -> None:
        assert router.prefix == "/api/v1/ordens-de-servico"

    def test_criar_ordem(self) -> None:
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.router.obter_criar_ordem"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _ORDEM_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/ordens-de-servico/",
                json={
                    "cliente_id": str(uuid4()),
                    "veiculo_id": str(uuid4()),
                },
            )
            assert resp.status_code == 201
            # RF-021: todo response de detalhe carrega `situacao` no
            # vocabulario do challenge ao lado do `status` tecnico.
            payload = resp.json()
            assert payload["status"] == "recebida"
            assert payload["situacao"] == "Recebida"

    def test_criar_ordem_com_servicos_e_pecas_mapeia_dto(self) -> None:
        """RF-020: as listas do payload chegam ao use case como tuplas de DTO."""
        from src.ordem_servico.aplicacao.dtos import (
            PecaDaOrdemDTO,
            ServicoDaOrdemDTO,
        )

        app = _criar_app()
        servico_id = uuid4()
        peca_id = uuid4()
        with patch(
            "src.ordem_servico.interfaces.router.obter_criar_ordem"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _ORDEM_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.post(
                "/api/v1/ordens-de-servico/",
                json={
                    "cliente_id": str(uuid4()),
                    "veiculo_id": str(uuid4()),
                    "servicos": [
                        {"servico_catalogo_id": str(servico_id), "quantidade": 2}
                    ],
                    "pecas": [
                        {
                            "servico_catalogo_id": str(servico_id),
                            "item_estoque_id": str(peca_id),
                            "quantidade": 3,
                        }
                    ],
                },
            )
            assert resp.status_code == 201
            dto = mock_uc.executar.call_args.args[0]
            assert dto.servicos == (
                ServicoDaOrdemDTO(servico_catalogo_id=servico_id, quantidade=2),
            )
            assert dto.pecas == (
                PecaDaOrdemDTO(
                    servico_catalogo_id=servico_id,
                    item_estoque_id=peca_id,
                    quantidade=3,
                ),
            )

    def test_listar_ordens(self) -> None:
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.router.obter_listar_ordens"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = [_RESUMO_NS]
            mock_uc.contar.return_value = 1
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/ordens-de-servico/")
            assert resp.status_code == 200
            # Schema da listagem expoe cliente_nome/veiculo_placa (defaults)
            # — o stub de enriquecimento nao preenche os campos, mas a chave
            # precisa existir no JSON pra UI nao cair em KeyError.
            payload = resp.json()
            assert payload["items"][0]["cliente_nome"] is None
            assert payload["items"][0]["veiculo_placa"] is None
            # RF-021: item de listagem tambem expoe `situacao`.
            assert payload["items"][0]["status"] == "recebida"
            assert payload["items"][0]["situacao"] == "Recebida"

    def test_listar_ordens_default_exclui_encerradas(self) -> None:
        """RF-023: sem query param, o router pede o universo filtrado."""
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.router.obter_listar_ordens"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = []
            mock_uc.contar.return_value = 0
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/ordens-de-servico/")
            assert resp.status_code == 200
            mock_uc.executar.assert_called_once_with(
                offset=0, limit=20, incluir_encerradas=False
            )
            mock_uc.contar.assert_called_once_with(incluir_encerradas=False)

    def test_listar_ordens_repassa_incluir_encerradas(self) -> None:
        """RF-023: ``incluir_encerradas=true`` chega ao use case e ao total."""
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.router.obter_listar_ordens"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = []
            mock_uc.contar.return_value = 0
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/ordens-de-servico/?incluir_encerradas=true")
            assert resp.status_code == 200
            mock_uc.executar.assert_called_once_with(
                offset=0, limit=20, incluir_encerradas=True
            )
            mock_uc.contar.assert_called_once_with(incluir_encerradas=True)

    def test_metricas(self) -> None:
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.router.obter_metricas"
        ) as mock_factory:
            mock_uc = MagicMock()
            mock_uc.executar.return_value = _METRICAS_NS
            mock_factory.return_value = mock_uc

            client = TestClient(app)
            resp = client.get("/api/v1/ordens-de-servico/metricas")
            assert resp.status_code == 200

    def test_obter_ordem_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_obter_ordem") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = obter_ordem(_ID, _USUARIO, MagicMock())
            assert result.id == _ID
            assert result.situacao == "Recebida"

    def test_adicionar_item_direto(self) -> None:
        body = AdicionarItemRequest(
            servico_catalogo_id=uuid4(),
            descricao="Troca",
            quantidade=1,
        )
        with patch("src.ordem_servico.interfaces.router.obter_adicionar_item") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = adicionar_item(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_remover_item_direto(self) -> None:
        iid = uuid4()
        with patch("src.ordem_servico.interfaces.router.obter_remover_item") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = remover_item(_ID, iid, _USUARIO, MagicMock())
            assert result.id == _ID
            m.return_value.executar.assert_called_once_with(_ID, iid)

    def test_iniciar_diagnostico_direto(self) -> None:
        with patch(
            "src.ordem_servico.interfaces.router.obter_iniciar_diagnostico"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = iniciar_diagnostico(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_gerar_orcamento_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_gerar_orcamento") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = gerar_orcamento(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_aprovar_orcamento_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_aprovar_orcamento") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = aprovar_orcamento(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_finalizar_servico_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_finalizar_servico") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = finalizar_servico(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_registrar_entrega_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_registrar_entrega") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = registrar_entrega(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_cancelar_ordem_direto(self) -> None:
        body = CancelarOrdemRequest(motivo="Cliente desistiu")
        with patch("src.ordem_servico.interfaces.router.obter_cancelar_ordem") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = cancelar_ordem(_ID, body, _USUARIO, MagicMock())
            assert result.id == _ID
            m.return_value.executar.assert_called_once()

    def test_gerar_complementar_direto(self) -> None:
        with patch("src.ordem_servico.interfaces.router.obter_gerar_complementar") as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = gerar_complementar(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_aprovar_complementar_direto(self) -> None:
        with patch(
            "src.ordem_servico.interfaces.router.obter_aprovar_complementar"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = aprovar_complementar(_ID, _USUARIO, MagicMock())
            assert result.id == _ID

    def test_rejeitar_complementar_direto(self) -> None:
        with patch(
            "src.ordem_servico.interfaces.router.obter_rejeitar_complementar"
        ) as m:
            m.return_value = MagicMock(executar=MagicMock(return_value=_ORDEM_NS))
            result = rejeitar_complementar(_ID, _USUARIO, MagicMock())
            assert result.id == _ID
