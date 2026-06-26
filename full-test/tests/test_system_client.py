"""Unit tests for SystemClient: parsing + error mapping + retry-on-429.

Nao exige instancia viva da API. Usa ``httpx.MockTransport`` para injetar
respostas controladas e exercitar o transport layer do cliente.
"""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest
from full_test.client.errors import (
    ConflitoError,
    NaoAutenticadoError,
    NaoAutorizadoError,
    NaoEncontradoError,
    RateLimitError,
    ValidacaoError,
)
from full_test.client.system_client import SystemClient


def _client_com_mock(handler: httpx.MockTransport) -> SystemClient:
    """Retorna um ``SystemClient`` cujo transport e substituido por ``handler``."""
    client = SystemClient(base_url="http://test")
    client.close()
    client._client = httpx.Client(transport=handler, base_url="http://test")
    return client


def test_login_parseia_token_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/autenticacao/login"
        return httpx.Response(
            200,
            json={
                "access_token": "a",
                "refresh_token": "r",
                "token_type": "bearer",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        tokens = client.login(email="admin@test.local", senha="senhaforte1234")
        assert tokens.access_token == "a"
        assert tokens.refresh_token == "r"
        assert tokens.token_type == "bearer"
        assert client.token == "a"


def test_401_levanta_nao_autenticado_com_correlation_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"detail": "Token invalido"},
            headers={"X-Request-ID": "req-1"},
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        with pytest.raises(NaoAutenticadoError) as exc:
            client.listar_clientes()
        assert exc.value.correlation_id == "req-1"
        assert "Token invalido" in exc.value.detail


def test_403_levanta_nao_autorizado_usando_envelope_dominio() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "erro": {
                    "codigo": "AUTORIZACAO_FALHOU",
                    "mensagem": "Papel nao autorizado",
                    "id_requisicao": "req-2",
                }
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        with pytest.raises(NaoAutorizadoError) as exc:
            client.listar_clientes()
        assert exc.value.correlation_id == "req-2"
        assert "Papel nao autorizado" in exc.value.detail


def test_404_levanta_nao_encontrado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "erro": {
                    "codigo": "ENTIDADE_NAO_ENCONTRADA",
                    "mensagem": "Cliente nao encontrado",
                    "id_requisicao": "req-3",
                }
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        with pytest.raises(NaoEncontradoError):
            client.obter_cliente(uuid.uuid4())


def test_409_levanta_conflito_em_transicao_invalida() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "erro": {
                    "codigo": "TRANSICAO_STATUS_INVALIDA",
                    "mensagem": "OS em ENTREGUE nao aceita novas transicoes",
                    "id_requisicao": "req-4",
                }
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        with pytest.raises(ConflitoError):
            client.iniciar_diagnostico(uuid.uuid4())


def test_429_reexecuta_ate_sucesso_respeitando_retry_after() -> None:
    chamadas: list[int] = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas[0] += 1
        if chamadas[0] < 3:
            return httpx.Response(
                429,
                json={"error": "Rate limit exceeded"},
                headers={"Retry-After": "0"},
            )
        return httpx.Response(200, json={"status": "ok"})

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        resposta = client.saude()
        assert resposta == {"status": "ok"}
        assert chamadas[0] == 3


def test_429_excedido_levanta_rate_limit_com_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": "Rate limit exceeded"},
            headers={"Retry-After": "0"},
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        with pytest.raises(RateLimitError) as exc:
            client.saude()
        assert exc.value.retry_after_seconds == 0.0


def test_422_levanta_validacao_com_detail_estruturado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "ano"],
                        "msg": "Input should be greater than or equal to 1886",
                        "type": "greater_than_equal",
                    }
                ]
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        with pytest.raises(ValidacaoError) as exc:
            client.adicionar_veiculo(
                cliente_id=uuid.uuid4(),
                placa="ABC1D23",
                marca="Fiat",
                modelo="Palio",
                ano=1850,
            )
        assert "body.ano" in exc.value.detail


def test_metodo_protegido_sem_token_levanta_runtime_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Nao deveria chegar no transport")

    with (
        _client_com_mock(httpx.MockTransport(handler)) as client,
        pytest.raises(RuntimeError, match="nao autenticado"),
    ):
        # Sem set_token nem login — devemos falhar antes do transport.
        client.listar_clientes()


def test_saude_nao_exige_autenticacao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Endpoint publico NAO deve receber Authorization
        assert "authorization" not in {k.lower() for k in request.headers}
        return httpx.Response(200, json={"status": "ok"})

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        # Sem token — ainda assim saude() deve funcionar.
        assert client.saude() == {"status": "ok"}


def test_acompanhamento_envia_query_params_sem_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/acompanhamento"
        assert request.url.params["placa"] == "ABC1D23"
        assert request.url.params["documento"] == "12345678901"
        assert "authorization" not in {k.lower() for k in request.headers}
        return httpx.Response(
            200,
            json={
                "status": "recebida",
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:05:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        resp = client.consultar_acompanhamento(
            placa="ABC1D23",
            documento="12345678901",
        )
        assert resp.status == "recebida"


def test_criar_servico_serializa_preco_como_string_duas_casas() -> None:
    from decimal import Decimal

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        assert body["preco"] == "89.90"
        return httpx.Response(
            201,
            json={
                "id": str(uuid.uuid4()),
                "nome": "Troca de oleo",
                "descricao": "Servico basico",
                "preco": "89.90",
                "moeda": "BRL",
                "ativo": True,
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        servico = client.criar_servico(
            nome="Troca de oleo",
            descricao="Servico basico",
            preco=Decimal("89.9"),
        )
        assert servico.preco == Decimal("89.90")


def test_criar_ordem_parseia_centavos_como_int() -> None:
    cliente_id = uuid.uuid4()
    veiculo_id = uuid.uuid4()
    ordem_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={
                "id": str(ordem_id),
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_id),
                "status": "recebida",
                "itens": [],
                "orcamento": None,
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:00:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        ordem = client.criar_ordem(cliente_id=cliente_id, veiculo_id=veiculo_id)
        assert ordem.id == ordem_id
        assert ordem.orcamento is None
        assert ordem.itens == []


def test_criar_ordem_inclui_servicos_e_pecas_no_body() -> None:
    cliente_id = uuid.uuid4()
    veiculo_id = uuid.uuid4()
    ordem_id = uuid.uuid4()
    servico_cat_id = uuid.uuid4()
    item_est_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        assert body["cliente_id"] == str(cliente_id)
        assert body["veiculo_id"] == str(veiculo_id)
        assert body["servicos"] == [
            {"servico_catalogo_id": str(servico_cat_id), "quantidade": 2}
        ]
        assert body["pecas"] == [
            {
                "servico_catalogo_id": str(servico_cat_id),
                "item_estoque_id": str(item_est_id),
                "quantidade": 1,
            }
        ]
        return httpx.Response(
            201,
            json={
                "id": str(ordem_id),
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_id),
                "status": "recebida",
                "situacao": "Recebida",
                "itens": [
                    {
                        "id": str(uuid.uuid4()),
                        "servico_catalogo_id": str(servico_cat_id),
                        "item_estoque_id": str(item_est_id),
                        "descricao": "Peca",
                        "quantidade": 1,
                        "preco_unitario_centavos": 1000,
                        "subtotal_centavos": 1000,
                    }
                ],
                "orcamento": None,
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:00:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        ordem = client.criar_ordem(
            cliente_id=cliente_id,
            veiculo_id=veiculo_id,
            servicos=[{"servico_catalogo_id": servico_cat_id, "quantidade": 2}],
            pecas=[
                {
                    "servico_catalogo_id": servico_cat_id,
                    "item_estoque_id": item_est_id,
                    "quantidade": 1,
                }
            ],
        )
        assert ordem.id == ordem_id
        assert ordem.situacao == "Recebida"
        assert len(ordem.itens) == 1


def test_criar_ordem_sem_itens_envia_so_cliente_e_veiculo() -> None:
    cliente_id = uuid.uuid4()
    veiculo_id = uuid.uuid4()
    ordem_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        # Regressao fase-1: sem itens, o body so carrega os dois ids.
        assert set(body.keys()) == {"cliente_id", "veiculo_id"}
        return httpx.Response(
            201,
            json={
                "id": str(ordem_id),
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_id),
                "status": "recebida",
                "itens": [],
                "orcamento": None,
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:00:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        ordem = client.criar_ordem(cliente_id=cliente_id, veiculo_id=veiculo_id)
        assert ordem.id == ordem_id
        assert ordem.itens == []


def test_listar_ordens_envia_incluir_encerradas_quando_true() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/ordens-de-servico/"
        assert request.url.params["incluir_encerradas"] == "true"
        return httpx.Response(
            200,
            json={"items": [], "total": 0, "offset": 0, "limit": 20},
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        resp = client.listar_ordens(incluir_encerradas=True)
        assert resp.total == 0


def test_listar_ordens_default_nao_inclui_encerradas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["incluir_encerradas"] == "false"
        return httpx.Response(
            200,
            json={"items": [], "total": 0, "offset": 0, "limit": 20},
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        client.listar_ordens()


def test_decidir_orcamento_webhook_envia_header_e_body() -> None:
    ordem_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        assert request.url.path == (
            f"/api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento"
        )
        assert request.headers.get("X-Webhook-Token") == "tok-secreto"
        # Endpoint publico: NAO deve receber Authorization
        assert "authorization" not in {k.lower() for k in request.headers}
        body = _json.loads(request.content)
        assert body == {"decisao": "aprovada"}
        return httpx.Response(
            200,
            json={
                "status": "em_execucao",
                "situacao": "Em execução",
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:10:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        # Token de admin presente para garantir que NAO vaza no canal publico.
        client.set_token("admin-token")
        resp = client.decidir_orcamento_webhook(
            ordem_id, decisao="aprovada", webhook_token="tok-secreto"
        )
        assert resp.status == "em_execucao"
        assert resp.situacao == "Em execução"


def test_situacao_parseada_nos_models() -> None:
    cliente_id = uuid.uuid4()
    veiculo_id = uuid.uuid4()
    ordem_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": str(ordem_id),
                "cliente_id": str(cliente_id),
                "veiculo_id": str(veiculo_id),
                "status": "em_diagnostico",
                "situacao": "Em diagnóstico",
                "itens": [],
                "orcamento": None,
                "criado_em": "2026-04-22T10:00:00",
                "atualizado_em": "2026-04-22T10:05:00",
            },
        )

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("fake")
        ordem = client.obter_ordem(ordem_id)
        assert ordem.situacao == "Em diagnóstico"


def test_situacao_default_vazio_quando_payload_nao_tem() -> None:
    from full_test.client import models

    payload = {
        "id": str(uuid.uuid4()),
        "cliente_id": str(uuid.uuid4()),
        "veiculo_id": str(uuid.uuid4()),
        "status": "recebida",
        "criado_em": "2026-04-22T10:00:00",
    }
    resumo = models.OrdemResumoResponse._parse(payload)
    assert resumo.situacao == ""

    acomp = models.AcompanhamentoResponse._parse(
        {
            "status": "recebida",
            "criado_em": "2026-04-22T10:00:00",
            "atualizado_em": "2026-04-22T10:00:00",
        }
    )
    assert acomp.situacao == ""


def test_envia_correlation_id_header_em_todas_requests() -> None:
    correlation_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cid = request.headers.get("X-Correlation-ID")
        assert cid is not None
        correlation_ids.append(cid)
        return httpx.Response(200, json={"status": "ok"})

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.saude()
        client.saude()
        assert len(correlation_ids) == 2
        # IDs devem ser unicos por request
        assert correlation_ids[0] != correlation_ids[1]
        # Prefixo padrao
        assert all(c.startswith("full-test-") for c in correlation_ids)


def test_sem_autenticacao_retorna_cliente_sem_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    with _client_com_mock(httpx.MockTransport(handler)) as client:
        client.set_token("admin-token")
        with client.sem_autenticacao() as anon:
            assert anon.token is None
            # Sanity: a nova instancia e independente
            assert client.token == "admin-token"


def _contar_metodos_publicos() -> int:
    """Retorna a contagem de metodos publicos da classe SystemClient."""
    return len(
        [
            name
            for name in dir(SystemClient)
            if callable(cast("object", getattr(SystemClient, name)))
            and not name.startswith("_")
        ]
    )


def test_numero_de_metodos_publicos_cobre_46_endpoints_mais_helpers() -> None:
    # 46 endpoints + 7 helpers (close, set_token, clear_token, sem_autenticacao,
    # property token nao conta, etc). Conservador: >= 46.
    contagem = _contar_metodos_publicos()
    assert contagem >= 46, f"Esperado >= 46 metodos, encontrado {contagem}"
