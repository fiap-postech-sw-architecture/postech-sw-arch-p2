"""Testes unitarios do ``ConsistencyChecker``.

Usa ``httpx.MockTransport`` (padrao do step 2) + ``SystemClient`` com mock
para exercitar o checker sem depender de instancia viva da API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from full_test.client import models
from full_test.client.system_client import SystemClient
from full_test.support.consistency import ConsistencyChecker, SnapshotEstoque


def _client_mock(handler: httpx.MockTransport) -> SystemClient:
    """Cria ``SystemClient`` cujo transport e substituido por ``handler``.

    ``sem_autenticacao()`` no ``SystemClient`` normalmente cria uma segunda
    instancia com ``httpx.Client`` real — inutil para testes unitarios.
    Aqui o override devolve um novo cliente que reusa o mesmo
    ``MockTransport``, permitindo que ``assert_status_publico`` e
    ``assert_acompanhamento_404`` tambem caiam no handler mockado.
    """
    client = SystemClient(base_url="http://test")
    client.close()
    client._client = httpx.Client(transport=handler, base_url="http://test")

    def _sem_auth_override() -> SystemClient:
        anon = SystemClient(base_url="http://test")
        anon.close()
        anon._client = httpx.Client(transport=handler, base_url="http://test")
        return anon

    client.sem_autenticacao = _sem_auth_override  # type: ignore[method-assign]
    return client


def _noop_handler(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200)


def test_transicao_valida_aceita_caminho_feliz() -> None:
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    checker.assert_transicao_valida(de="recebida", para="em_diagnostico")
    checker.assert_transicao_valida(de="finalizada", para="entregue")


def test_transicao_invalida_levanta() -> None:
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    with pytest.raises(AssertionError, match="Transicao invalida"):
        checker.assert_transicao_valida(de="recebida", para="finalizada")
    with pytest.raises(AssertionError, match="Transicao invalida"):
        checker.assert_transicao_valida(de="entregue", para="em_execucao")


def test_estado_desconhecido_levanta() -> None:
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    with pytest.raises(AssertionError, match="desconhecido"):
        checker.assert_transicao_valida(de="FOO", para="BAR")


def _ordem_com_orcamento(
    total_centavos: int,
    subtotais: list[int],
) -> models.OrdemDeServicoResponse:
    itens = [
        models.ItemDaOrdemResponse(
            id=uuid4(),
            servico_catalogo_id=uuid4(),
            item_estoque_id=None,
            descricao=f"i{i}",
            quantidade=1,
            preco_unitario_centavos=sub,
            subtotal_centavos=sub,
        )
        for i, sub in enumerate(subtotais)
    ]
    agora = datetime.now(UTC)
    return models.OrdemDeServicoResponse(
        id=uuid4(),
        cliente_id=uuid4(),
        veiculo_id=uuid4(),
        status="aguardando_aprovacao",
        itens=itens,
        orcamento=models.OrcamentoResponse(
            total_centavos=total_centavos,
            gerado_em=agora,
            itens=[],
        ),
        criado_em=agora,
        atualizado_em=agora,
    )


def test_total_orcamento_conferindo() -> None:
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    checker.assert_total_orcamento(
        _ordem_com_orcamento(total_centavos=150, subtotais=[50, 100])
    )


def test_total_orcamento_divergente_levanta() -> None:
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    with pytest.raises(AssertionError, match="diverge"):
        checker.assert_total_orcamento(
            _ordem_com_orcamento(total_centavos=999, subtotais=[50, 100])
        )


def test_subtotal_divergente_levanta() -> None:
    agora = datetime.now(UTC)
    ordem = models.OrdemDeServicoResponse(
        id=uuid4(),
        cliente_id=uuid4(),
        veiculo_id=uuid4(),
        status="aguardando_aprovacao",
        itens=[
            models.ItemDaOrdemResponse(
                id=uuid4(),
                servico_catalogo_id=uuid4(),
                item_estoque_id=None,
                descricao="x",
                quantidade=3,
                preco_unitario_centavos=100,
                subtotal_centavos=500,  # deveria ser 300
            )
        ],
        orcamento=None,
        criado_em=agora,
        atualizado_em=agora,
    )
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    with pytest.raises(AssertionError, match="subtotal"):
        checker.assert_subtotais_dos_itens(ordem)


def test_conservacao_estoque_ok() -> None:
    item_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(item_id),
                "nome": "x",
                "descricao": "y",
                "quantidade": 90,
                "preco_unitario": "10.00",
                "moeda": "BRL",
                "ativo": True,
            },
        )

    client = _client_mock(httpx.MockTransport(handler))
    client.set_token("fake")
    checker = ConsistencyChecker(client)
    checker.assert_conservacao_estoque(
        snapshot_inicial=[SnapshotEstoque(item_id=item_id, quantidade=100)],
        consumos_por_item={item_id: 10},
    )


def test_conservacao_estoque_divergente_levanta() -> None:
    item_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(item_id),
                "nome": "x",
                "descricao": "y",
                "quantidade": 85,  # esperado 90
                "preco_unitario": "10.00",
                "moeda": "BRL",
                "ativo": True,
            },
        )

    client = _client_mock(httpx.MockTransport(handler))
    client.set_token("fake")
    checker = ConsistencyChecker(client)
    with pytest.raises(AssertionError, match="nao conservado"):
        checker.assert_conservacao_estoque(
            snapshot_inicial=[SnapshotEstoque(item_id=item_id, quantidade=100)],
            consumos_por_item={item_id: 10},
        )


def test_metricas_monotonicas_aceita_crescimento() -> None:
    anterior = models.MetricasResponse(
        total=10,
        por_status={"finalizada": 2, "entregue": 1},
        tempo_medio_execucao_minutos=15.0,
    )
    atual = models.MetricasResponse(
        total=12,
        por_status={"finalizada": 3, "entregue": 2},
        tempo_medio_execucao_minutos=14.0,
    )
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    checker.assert_metricas_monotonicas(anterior=anterior, atual=atual)


def test_metricas_monotonicas_rejeita_total_regredindo() -> None:
    anterior = models.MetricasResponse(
        total=10, por_status={}, tempo_medio_execucao_minutos=None
    )
    atual = models.MetricasResponse(
        total=9, por_status={}, tempo_medio_execucao_minutos=None
    )
    checker = ConsistencyChecker(_client_mock(httpx.MockTransport(_noop_handler)))
    with pytest.raises(AssertionError, match=r"Total .* regrediu"):
        checker.assert_metricas_monotonicas(anterior=anterior, atual=atual)


def test_assert_status_publico_bate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/acompanhamento"
        return httpx.Response(
            200,
            json={
                "status": "em_execucao",
                "criado_em": "2026-04-22T10:00:00+00:00",
                "atualizado_em": "2026-04-22T11:00:00+00:00",
            },
        )

    client = _client_mock(httpx.MockTransport(handler))
    checker = ConsistencyChecker(client)
    checker.assert_status_publico(
        placa="ABC1234", documento="12345678909", status_esperado="em_execucao"
    )


def test_assert_status_publico_divergente_levanta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "recebida",
                "criado_em": "2026-04-22T10:00:00+00:00",
                "atualizado_em": "2026-04-22T11:00:00+00:00",
            },
        )

    client = _client_mock(httpx.MockTransport(handler))
    checker = ConsistencyChecker(client)
    with pytest.raises(AssertionError, match="retornou"):
        checker.assert_status_publico(
            placa="ABC1234", documento="12345678909", status_esperado="em_execucao"
        )


def test_assert_acompanhamento_404_aceita_nao_encontrado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Ordem nao encontrada"})

    client = _client_mock(httpx.MockTransport(handler))
    checker = ConsistencyChecker(client)
    checker.assert_acompanhamento_404(placa="ZZZ9999", documento="00000000000")
