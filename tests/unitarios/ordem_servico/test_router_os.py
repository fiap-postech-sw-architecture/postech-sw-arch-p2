from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

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


class TestResolverNomesItens:
    """Cobre ``_resolver_nomes_itens`` — helper que enriquece a resposta com
    ``servico_nome`` e ``item_estoque_nome`` via batch lookup.

    Backend resolve os nomes server-side pra UI nao precisar de chamadas
    extras pro catalogo/estoque (ver mudanca em ItemDaOrdemResponse). O
    helper coleta IDs unicos e faz UMA query por entidade — N+1 evitado.
    """

    @staticmethod
    def _item_response(
        servico_id: object | None = None,
        item_estoque_id: object | None = None,
    ) -> object:
        """Cria um ItemDaOrdemResponse minimo direto via SimpleNamespace.

        ``_resolver_nomes_itens`` so le ``servico_catalogo_id`` /
        ``item_estoque_id`` e atribui ``servico_nome`` / ``item_estoque_nome``,
        entao um ns funciona igual ao Pydantic real.
        """
        return SimpleNamespace(
            servico_catalogo_id=servico_id or uuid4(),
            item_estoque_id=item_estoque_id,
            servico_nome=None,
            item_estoque_nome=None,
        )

    @staticmethod
    def _stub_session(
        servicos: list[object] | None = None,
        estoque: list[object] | None = None,
    ) -> MagicMock:
        """Stub session.execute() retornando duas chamadas (servicos depois estoque).

        ``_resolver_nomes_itens`` chama ``session.execute(select(...))`` 1x pra
        servicos e — apenas se houver itens com ``item_estoque_id`` — outra pra
        estoque. Cada chamada usa ``.scalars()`` para iterar.
        """
        session = MagicMock()

        def _resultado_iteravel(rows: list[object]) -> MagicMock:
            res = MagicMock()
            res.scalars.return_value = iter(rows)
            return res

        side = [_resultado_iteravel(servicos or [])]
        if estoque is not None:
            side.append(_resultado_iteravel(estoque))
        session.execute.side_effect = side
        return session

    def test_resolve_servico_nome_para_linha_de_mao_de_obra(self) -> None:
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        sid = uuid4()
        item = self._item_response(servico_id=sid)
        response = SimpleNamespace(itens=[item])
        session = self._stub_session(
            servicos=[SimpleNamespace(id=sid, nome="Troca de oleo")],
        )

        _resolver_nomes_itens(response, session)

        assert item.servico_nome == "Troca de oleo"
        assert item.item_estoque_nome is None
        # 1 query (so servicos) — sem item_estoque_id na lista.
        assert session.execute.call_count == 1

    def test_resolve_servico_e_item_estoque_para_peca_consumida(self) -> None:
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        sid = uuid4()
        eid = uuid4()
        item = self._item_response(servico_id=sid, item_estoque_id=eid)
        response = SimpleNamespace(itens=[item])
        session = self._stub_session(
            servicos=[SimpleNamespace(id=sid, nome="Troca de oleo")],
            estoque=[SimpleNamespace(id=eid, nome="Filtro de oleo")],
        )

        _resolver_nomes_itens(response, session)

        assert item.servico_nome == "Troca de oleo"
        assert item.item_estoque_nome == "Filtro de oleo"
        # 2 queries: 1 para servicos, 1 para estoque.
        assert session.execute.call_count == 2

    def test_servico_inexistente_deixa_nome_none(self) -> None:
        """Catalogo limpo apos OS criada — UI cai pro placeholder."""
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        item = self._item_response()
        response = SimpleNamespace(itens=[item])
        session = self._stub_session(servicos=[])  # nada no batch

        _resolver_nomes_itens(response, session)

        assert item.servico_nome is None
        assert item.item_estoque_nome is None

    def test_item_estoque_inexistente_deixa_nome_none(self) -> None:
        """Servico encontrado mas peca nao — caso edge de cleanup parcial."""
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        sid = uuid4()
        eid = uuid4()
        item = self._item_response(servico_id=sid, item_estoque_id=eid)
        response = SimpleNamespace(itens=[item])
        session = self._stub_session(
            servicos=[SimpleNamespace(id=sid, nome="Troca de oleo")],
            estoque=[],  # batch vazio
        )

        _resolver_nomes_itens(response, session)

        assert item.servico_nome == "Troca de oleo"
        assert item.item_estoque_nome is None

    def test_lista_vazia_nao_consulta_db(self) -> None:
        """Sem itens nao deve gerar query nenhuma — early return."""
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        response = SimpleNamespace(itens=[])
        session = MagicMock()

        _resolver_nomes_itens(response, session)

        session.execute.assert_not_called()

    def test_batch_dedupe_servicos_iguais(self) -> None:
        """N itens com mesmo servico_catalogo_id -> 1 query, todos resolvidos."""
        from src.ordem_servico.interfaces.router import _resolver_nomes_itens

        sid = uuid4()
        item_a = self._item_response(servico_id=sid)
        item_b = self._item_response(servico_id=sid, item_estoque_id=uuid4())
        item_c = self._item_response(servico_id=sid, item_estoque_id=uuid4())
        response = SimpleNamespace(itens=[item_a, item_b, item_c])
        session = self._stub_session(
            servicos=[SimpleNamespace(id=sid, nome="Troca de oleo")],
            estoque=[
                SimpleNamespace(id=item_b.item_estoque_id, nome="Filtro"),
                SimpleNamespace(id=item_c.item_estoque_id, nome="Oleo"),
            ],
        )

        _resolver_nomes_itens(response, session)

        # Mesmo nome de servico replicado nas 3 linhas (sem 3 queries!).
        assert item_a.servico_nome == "Troca de oleo"
        assert item_b.servico_nome == "Troca de oleo"
        assert item_c.servico_nome == "Troca de oleo"
        assert item_b.item_estoque_nome == "Filtro"
        assert item_c.item_estoque_nome == "Oleo"
        # 2 queries total (servicos + estoque) independentemente do n de itens.
        assert session.execute.call_count == 2
