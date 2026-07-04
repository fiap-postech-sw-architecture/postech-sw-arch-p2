from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from ui.cliente_api import (
    AcessoNegadoError,
    ApiError,
    BackendInacessivelError,
    BackendIndisponivelError,
    ClienteApi,
    ConflitoEstadoError,
    NaoAutenticadoError,
    RateLimitExcedidoError,
    ValidacaoError,
)
from ui.estado import Sessao, StateStore

# {"alg":"HS256","typ":"JWT"} base64 sem padding — header estruturalmente
# valido exigido pelo pyjwt para decodificar, mesmo sem verificar assinatura.
_HEADER_B64 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"


@pytest.fixture
def store() -> StateStore:
    return StateStore()


def _transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_adiciona_bearer_token_quando_autenticado(store: StateStore) -> None:
    store.salvar_sessao(Sessao("tok", "ref", "a@b", "admin"))
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    api = ClienteApi(
        base_url="http://x",
        store=store,
        transport=_transport(handler),
    )
    api.get("/api/v1/saude")
    assert capturado["authorization"] == "Bearer tok"


def test_nao_adiciona_auth_quando_sem_sessao(store: StateStore) -> None:
    capturado: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado.update(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.get("/api/v1/saude")
    assert "authorization" not in capturado


def test_mapeia_422_para_validacao_error(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"detail": [{"loc": ["body", "email"], "msg": "invalid"}]}
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ValidacaoError) as exc:
        api.post("/api/v1/clientes", json_body={})
    assert exc.value.detalhes[0]["msg"] == "invalid"


def test_mapeia_403_para_acesso_negado(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "atendente"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "admin required"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(AcessoNegadoError):
        api.post("/api/v1/servicos", json_body={"nome": "x"})


def test_mapeia_409_para_conflito_estado_preserva_detail(store: StateStore) -> None:
    """409 e o codigo do backend pra ViolacaoRegraDeNegocio /
    TransicaoStatusInvalida / EstoqueInsuficiente / EntidadeDuplicada.
    O detail do FastAPI carrega a regra violada — UI usa pra mostrar mensagem
    util ('Itens nao podem ser modificados em AGUARDANDO_APROVACAO') em vez
    de 'Conflict' generico."""
    store.salvar_sessao(Sessao("t", "r", "a@b", "admin"))
    detail = (
        "Itens so podem ser modificados em RECEBIDA ou EM_DIAGNOSTICO. "
        "Status atual: aguardando_aprovacao"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": detail})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ConflitoEstadoError) as exc:
        api.post("/api/v1/ordens-de-servico/abc/itens", json_body={"x": 1})
    assert exc.value.detail == detail
    # Mensagem de excecao e o detail (sem prefixo extra) pra que UI consiga
    # propagar direto via str(exc) caso queira.
    assert str(exc.value) == detail


def test_mapeia_409_sem_detail_usa_fallback(store: StateStore) -> None:
    """Backend pode emitir 409 sem detail (caso raro). Mensagem fallback
    nao deve quebrar — UI ainda deve conseguir str(exc) sem KeyError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ConflitoEstadoError) as exc:
        api.post("/api/v1/x", json_body={})
    assert "Acao nao permitida" in str(exc.value)


def test_mapeia_429_para_rate_limit(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(RateLimitExcedidoError) as exc:
        api.get("/api/v1/acompanhamento")
    assert exc.value.retry_after == 30


def test_conexao_falha_levanta_backend_inacessivel(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    api = ClienteApi(
        base_url="http://nonexistent",
        store=store,
        transport=_transport(handler),
    )
    with pytest.raises(BackendInacessivelError):
        api.get("/api/v1/saude")


def test_mapeia_401_para_nao_autenticado(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "invalid token"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")


def test_mapeia_5xx_para_backend_indisponivel(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "service unavailable"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(BackendIndisponivelError):
        api.get("/api/v1/saude")


def test_401_dispara_refresh_e_retenta_uma_vez(store: StateStore) -> None:
    store.salvar_sessao(Sessao("expired", "valid-refresh", "a@b", "admin"))
    chamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "novo-token",
                    "refresh_token": "novo-refresh",
                    "token_type": "bearer",
                },
            )
        if request.headers.get("authorization") == "Bearer expired":
            return httpx.Response(401, json={"detail": "token expired"})
        if request.headers.get("authorization") == "Bearer novo-token":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(500)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    resultado = api.get("/api/v1/clientes")
    assert resultado == {"ok": True}
    assert "GET /api/v1/clientes" in chamadas[0]
    assert "POST /api/v1/autenticacao/refresh" in chamadas[1]
    assert "GET /api/v1/clientes" in chamadas[2]
    assert store.token_atual() == "novo-token"


def test_refresh_falhar_limpa_sessao_e_levanta_nao_autenticado(
    store: StateStore,
) -> None:
    store.salvar_sessao(Sessao("expired", "also-expired", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(401)
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")
    assert store.token_atual() is None


def test_401_no_proprio_refresh_nao_entra_em_loop(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "admin"))
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.post("/api/v1/autenticacao/refresh", json_body={"refresh_token": "r"})
    assert chamadas == 1


def test_login_salva_sessao_e_decodifica_papel(store: StateStore) -> None:
    # JWT payload base64 com papel=admin e email=a@b
    # {"email":"a@b","papel":"admin"} base64 sem padding:
    payload_b64 = "eyJlbWFpbCI6ImFAYiIsInBhcGVsIjoiYWRtaW4ifQ"
    # header {"alg":"HS256","typ":"JWT"} valido: pyjwt parseia o header
    # mesmo com verify_signature=False; a assinatura pode ser fake.
    fake_jwt = f"{_HEADER_B64}.{payload_b64}.yyy"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": fake_jwt,
                "refresh_token": "r",
                "token_type": "bearer",
            },
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.login(email="a@b", senha="secret123456")
    assert store.token_atual() == fake_jwt
    assert store.email_atual() == "a@b"
    assert store.papel_atual() == "admin"


def test_logout_limpa_sessao_mesmo_se_backend_falhar(store: StateStore) -> None:
    store.salvar_sessao(Sessao("t", "r", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.logout()  # nao deve levantar
    assert store.token_atual() is None


def test_login_sem_papel_no_jwt_levanta_nao_autenticado(store: StateStore) -> None:
    # Payload sem "papel": {"email":"a@b"} -> base64 urlsafe sem padding.
    payload_b64 = "eyJlbWFpbCI6ImFAYiJ9"
    fake_jwt = f"{_HEADER_B64}.{payload_b64}.yyy"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": fake_jwt,
                "refresh_token": "r",
                "token_type": "bearer",
            },
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.login(email="a@b", senha="secret123456")
    # Sessao NAO deve ter sido salva
    assert store.token_atual() is None


def test_tentar_login_sem_salvar_retorna_200_quando_credenciais_ok(
    store: StateStore,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "b"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    assert api.tentar_login_sem_salvar(email="a@b", senha="secret123456") == 200
    # NAO altera a sessao — proposito do metodo.
    assert store.token_atual() is None


def test_tentar_login_sem_salvar_retorna_401_quando_credenciais_invalidas(
    store: StateStore,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    assert api.tentar_login_sem_salvar(email="a@b", senha="x") == 401
    assert store.token_atual() is None


def test_tentar_login_sem_salvar_retorna_none_quando_backend_offline(
    store: StateStore,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    assert api.tentar_login_sem_salvar(email="a@b", senha="x") is None


def test_cliente_api_helpers_de_clientes(store: StateStore) -> None:
    chamadas: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/api/v1/clientes":
            return httpx.Response(
                200, json={"items": [], "total": 0, "offset": 0, "limit": 20}
            )
        if request.method == "POST":
            return httpx.Response(201, json={"id": "x"})
        return httpx.Response(200, json={})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.listar_clientes(offset=0, limit=20)
    api.criar_cliente(
        {"nome": "Joao", "documento": "11144477735", "tipo_documento": "cpf"}
    )
    assert ("GET", "/api/v1/clientes") in chamadas
    assert ("POST", "/api/v1/clientes") in chamadas


# ----- helpers: testes por endpoint -----


def _api_que_registra(
    store: StateStore,
) -> tuple[ClienteApi, list[tuple[str, str, dict[str, object] | None]]]:
    """Cria um ClienteApi que registra (metodo, caminho, body) em cada chamada."""
    registro: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            import json as _json

            body = _json.loads(request.content)
        registro.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"ok": True})

    return ClienteApi(
        base_url="http://x", store=store, transport=_transport(handler)
    ), registro


def test_obter_cliente_usa_uuid_no_path(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.obter_cliente("abc-123")
    assert registro == [("GET", "/api/v1/clientes/abc-123", None)]


def test_atualizar_cliente_usa_put_com_body(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.atualizar_cliente("c1", {"nome": "Novo Nome", "contato": "x@y.com"})
    assert registro == [
        ("PUT", "/api/v1/clientes/c1", {"nome": "Novo Nome", "contato": "x@y.com"})
    ]


def test_desativar_cliente_usa_delete(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.desativar_cliente("c1")
    assert registro == [("DELETE", "/api/v1/clientes/c1", None)]


def test_helpers_veiculos_montam_paths_correto(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.listar_veiculos("c1")
    api.adicionar_veiculo(
        "c1", {"placa": "ABC1D23", "marca": "X", "modelo": "Y", "ano": 2020}
    )
    api.remover_veiculo("c1", "v1")
    assert [r[:2] for r in registro] == [
        ("GET", "/api/v1/clientes/c1/veiculos"),
        ("POST", "/api/v1/clientes/c1/veiculos"),
        ("DELETE", "/api/v1/clientes/c1/veiculos/v1"),
    ]


def test_helpers_servicos_crud(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.listar_servicos(offset=10, limit=50)
    api.criar_servico({"nome": "S", "descricao": "d", "preco": 1.0})
    api.atualizar_servico("s1", {"nome": "S2", "descricao": "d", "preco": 2.0})
    api.desativar_servico("s1")
    assert [r[:2] for r in registro] == [
        ("GET", "/api/v1/servicos"),
        ("POST", "/api/v1/servicos"),
        ("PUT", "/api/v1/servicos/s1"),
        ("DELETE", "/api/v1/servicos/s1"),
    ]


def test_helpers_estoque_crud(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.listar_estoque()
    api.criar_item_estoque(
        {"nome": "I", "descricao": "d", "preco_unitario": 1.0, "quantidade": 1}
    )
    api.atualizar_item_estoque(
        "i1", {"nome": "I2", "descricao": "d", "preco_unitario": 2.0}
    )
    api.ajustar_quantidade("i1", 42)
    api.desativar_item_estoque("i1")
    assert [r[:2] for r in registro] == [
        ("GET", "/api/v1/estoque"),
        ("POST", "/api/v1/estoque"),
        ("PUT", "/api/v1/estoque/i1"),
        ("PATCH", "/api/v1/estoque/i1/quantidade"),
        ("DELETE", "/api/v1/estoque/i1"),
    ]
    # PATCH deve enviar nova_quantidade no body
    assert registro[3][2] == {"nova_quantidade": 42}


def test_helpers_lgpd(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.exportar_dados_cliente("c1")
    api.excluir_dados_cliente("c1")
    api.registrar_consentimento("c1", "marketing")
    api.revogar_consentimento("c1", "marketing")
    assert [r[:2] for r in registro] == [
        ("GET", "/api/v1/clientes/c1/dados-pessoais/exportar"),
        ("DELETE", "/api/v1/clientes/c1/dados-pessoais"),
        ("POST", "/api/v1/clientes/c1/consentimento"),
        ("DELETE", "/api/v1/clientes/c1/consentimento"),
    ]
    # registrar_consentimento envia tipo no body
    assert registro[2][2] == {"tipo": "marketing"}


def test_acompanhamento_publico_envia_pii_no_corpo(store: StateStore) -> None:
    # Issue #180: placa/documento sao PII e vao no CORPO (POST), nunca na URL.
    import json as _json

    metodos: list[str] = []
    urls: list[str] = []
    corpos: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        metodos.append(request.method)
        urls.append(str(request.url))
        corpos.append(_json.loads(request.content) if request.content else {})
        return httpx.Response(200, json={"status": "recebida"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    api.acompanhamento_publico(placa="ABC1D23", documento="11144477735")
    assert metodos == ["POST"]
    assert corpos == [{"placa": "ABC1D23", "documento": "11144477735"}]
    # a PII nunca aparece na URL/query string.
    assert "ABC1D23" not in urls[0]
    assert "11144477735" not in urls[0]


def test_helpers_ordens_de_servico(store: StateStore) -> None:
    api, registro = _api_que_registra(store)
    api.listar_ordens(offset=5, limit=15)
    api.obter_ordem("o1")
    api.criar_ordem("c1", "v1")
    api.adicionar_item_ordem(
        "o1", {"servico_catalogo_id": "s1", "descricao": "x", "quantidade": 1}
    )
    api.remover_item_ordem("o1", "it1")
    api.executar_transicao("o1", "/diagnostico")
    api.executar_transicao("o1", "/cancelamento", {"motivo": "teste cancelar"})
    api.metricas_ordens()
    assert [r[:2] for r in registro] == [
        ("GET", "/api/v1/ordens-de-servico"),
        ("GET", "/api/v1/ordens-de-servico/o1"),
        ("POST", "/api/v1/ordens-de-servico"),
        ("POST", "/api/v1/ordens-de-servico/o1/itens"),
        ("DELETE", "/api/v1/ordens-de-servico/o1/itens/it1"),
        ("POST", "/api/v1/ordens-de-servico/o1/diagnostico"),
        ("POST", "/api/v1/ordens-de-servico/o1/cancelamento"),
        ("GET", "/api/v1/ordens-de-servico/metricas"),
    ]
    # criar_ordem envia cliente_id + veiculo_id
    assert registro[2][2] == {"cliente_id": "c1", "veiculo_id": "v1"}
    # executar_transicao com body envia o body; sem body envia None
    assert registro[5][2] is None
    assert registro[6][2] == {"motivo": "teste cancelar"}


def _api_que_registra_query(
    store: StateStore,
) -> tuple[ClienteApi, list[dict[str, str]]]:
    """Cria um ClienteApi que registra os query params crus de cada GET.

    Os params do httpx ja vem como strings (``"true"``/``"false"`` para bool,
    porque httpx serializa bool em lowercase) — espelha o que o backend recebe
    na query string.
    """
    chamadas: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(dict(request.url.params))
        return httpx.Response(
            200, json={"items": [], "total": 0, "offset": 0, "limit": 20}
        )

    return ClienteApi(
        base_url="http://x", store=store, transport=_transport(handler)
    ), chamadas


def test_listar_ordens_default_nao_inclui_encerradas(store: StateStore) -> None:
    """RF-023: por padrao a UI lista igual a fase 1 — ``incluir_encerradas``
    vai como ``false`` (default do backend exclui FINALIZADA/ENTREGUE/
    CANCELADA)."""
    api, chamadas = _api_que_registra_query(store)
    api.listar_ordens(offset=5, limit=15)
    assert chamadas == [{"offset": "5", "limit": "15", "incluir_encerradas": "false"}]


def test_listar_ordens_incluir_encerradas_envia_true(store: StateStore) -> None:
    """RF-023: com o toggle ligado a UI pede as OS encerradas (anexadas pela
    ordenacao do backend)."""
    api, chamadas = _api_que_registra_query(store)
    api.listar_ordens(incluir_encerradas=True)
    assert chamadas == [{"offset": "0", "limit": "20", "incluir_encerradas": "true"}]


def test_criar_ordem_sem_itens_envia_so_cliente_e_veiculo(store: StateStore) -> None:
    """Regressao fase 1 (RF-020): sem servicos/pecas o corpo continua byte-
    identico ao da fase 1 — apenas cliente_id + veiculo_id. O backend usa
    ``extra='forbid'``; chaves vazias quebrariam a criacao simples."""
    api, registro = _api_que_registra(store)
    api.criar_ordem("c1", "v1")
    assert registro == [
        ("POST", "/api/v1/ordens-de-servico", {"cliente_id": "c1", "veiculo_id": "v1"})
    ]


def test_criar_ordem_com_servicos_e_pecas_inclui_no_corpo(store: StateStore) -> None:
    """RF-020: criacao inline de OS ja com servicos e pecas. Ambas as listas
    sao enviadas no corpo quando fornecidas."""
    api, registro = _api_que_registra(store)
    servicos = [{"servico_catalogo_id": "s1", "quantidade": 2}]
    pecas = [{"servico_catalogo_id": "s1", "item_estoque_id": "i1", "quantidade": 3}]
    api.criar_ordem("c1", "v1", servicos=servicos, pecas=pecas)
    assert registro == [
        (
            "POST",
            "/api/v1/ordens-de-servico",
            {
                "cliente_id": "c1",
                "veiculo_id": "v1",
                "servicos": servicos,
                "pecas": pecas,
            },
        )
    ]


def test_criar_ordem_so_servicos_omite_pecas(store: StateStore) -> None:
    """RF-020: ``extra='forbid'`` no backend — so manda a chave que tem valor.
    Passando apenas ``servicos`` o corpo nao deve conter ``pecas``."""
    api, registro = _api_que_registra(store)
    servicos = [{"servico_catalogo_id": "s1", "quantidade": 1}]
    api.criar_ordem("c1", "v1", servicos=servicos)
    assert registro == [
        (
            "POST",
            "/api/v1/ordens-de-servico",
            {"cliente_id": "c1", "veiculo_id": "v1", "servicos": servicos},
        )
    ]


# ----- Edge cases de _interpretar_resposta / helpers privados -----


def test_status_204_no_content_retorna_dict_vazio(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    # DELETE normalmente retorna 204; o helper deve aceitar corpo vazio.
    resultado = api.delete("/api/v1/clientes/qualquer")
    assert resultado == {}


def test_status_inesperado_levanta_api_error_generico(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 418 I'm a teapot: fora do range mapeado (2xx/401/403/422/429/5xx).
        return httpx.Response(418, json={"detail": "teapot"})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(ApiError) as exc:
        api.get("/api/v1/saude")
    assert "418" in str(exc.value)


def test_refresh_falha_quando_nao_ha_refresh_token(store: StateStore) -> None:
    # Sessao existe mas sem refresh_token (cenario corrompido).
    # Forcamos o 401 mas como store nao tem refresh, o fluxo nao tenta refresh
    # e propaga NaoAutenticadoError.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")


def test_refresh_falha_quando_sessao_tem_email_mas_papel_none(
    store: StateStore,
) -> None:
    # Simula sessao onde papel_atual retorna None mas refresh_token existe.
    # Nesse caso _tentar_refresh aborta para nao escalar privilegios.
    store.salvar_sessao(Sessao("expired", "valid-refresh", "a@b", "admin"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/autenticacao/refresh":
            return httpx.Response(
                200,
                json={
                    "access_token": "novo",
                    "refresh_token": "novo-r",
                },
            )
        return httpx.Response(401)

    # Monkey-patch do papel_atual para retornar None (simula corrupcao).
    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    original = store.papel_atual
    store.papel_atual = lambda: None  # type: ignore[method-assign]
    try:
        with pytest.raises(NaoAutenticadoError):
            api.get("/api/v1/clientes")
    finally:
        store.papel_atual = original  # type: ignore[method-assign]


def test_refresh_conexao_falha_retorna_false(store: StateStore) -> None:
    store.salvar_sessao(Sessao("expired", "r", "a@b", "admin"))
    tentativas = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas["count"] += 1
        if request.url.path == "/api/v1/autenticacao/refresh":
            # Simula rede caida especificamente no refresh.
            raise httpx.ConnectError("sem rede")
        return httpx.Response(401)

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(NaoAutenticadoError):
        api.get("/api/v1/clientes")


def test_200_com_content_type_nao_json_propaga_erro(store: StateStore) -> None:
    """Backend so deve devolver 200 com JSON. Texto puro indica resposta
    fora do contrato — o cliente propaga o ``json.JSONDecodeError`` cru em vez
    de retornar um stub (diferente do 422, que tem fallback deliberado em
    ``_detalhes_validacao`` para nao mascarar o erro original de proxy)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"hello plain text",
            headers={"content-type": "text/plain"},
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(json.JSONDecodeError):
        api.get("/api/v1/saude")


def test_403_sem_json_body_nao_quebra_extrair_detail(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 403 sem body JSON — _extrair_detail deve retornar None silenciosamente.
        return httpx.Response(
            403, content=b"forbidden", headers={"content-type": "text/html"}
        )

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(AcessoNegadoError) as exc:
        api.get("/api/v1/servicos")
    # Sem detail extraido, o papel_necessario fica None.
    assert exc.value.papel_necessario is None


def test_403_com_detail_nao_string_ignora(store: StateStore) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # detail como dict em vez de string — _extrair_detail retorna None.
        return httpx.Response(403, json={"detail": {"complex": "object"}})

    api = ClienteApi(base_url="http://x", store=store, transport=_transport(handler))
    with pytest.raises(AcessoNegadoError) as exc:
        api.get("/api/v1/saude")
    assert exc.value.papel_necessario is None
