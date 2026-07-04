from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from src.autenticacao.dominio.exceptions import (
    CredenciaisInvalidasException,
    EmailDuplicadoException,
)
from src.compartilhado.dominio.exceptions import (
    DomainException,
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
    EstoqueInsuficienteException,
    FalhaAutenticacaoException,
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)
from src.compartilhado.infraestrutura.logging import configurar_logging
from src.compartilhado.interfaces.error_handler import registrar_error_handlers

if TYPE_CHECKING:
    from collections.abc import Iterator


def _criar_app_com_excecao(exc: Exception) -> TestClient:
    app = FastAPI()
    registrar_error_handlers(app)

    @app.get("/test")
    def _endpoint() -> None:
        raise exc

    return TestClient(app, raise_server_exceptions=False)


_CASOS_EXCECAO = [
    pytest.param(EntidadeNaoEncontradaException(), 404, id="nao-encontrada-404"),
    pytest.param(ViolacaoRegraDeNegocioException(), 409, id="violacao-regra-409"),
    pytest.param(TransicaoStatusInvalidaException(), 409, id="transicao-invalida-409"),
    pytest.param(EstoqueInsuficienteException(), 409, id="estoque-insuficiente-409"),
    pytest.param(EntidadeDuplicadaException(), 409, id="entidade-duplicada-409"),
    pytest.param(FalhaAutenticacaoException(), 401, id="autenticacao-401"),
]


@pytest.mark.parametrize(("exc", "status_code"), _CASOS_EXCECAO)
def test_mapeamento_excecao_para_status(exc: Exception, status_code: int) -> None:
    client = _criar_app_com_excecao(exc)
    resp = client.get("/test")
    assert resp.status_code == status_code
    body = resp.json()
    assert "erro" in body
    assert "codigo" in body["erro"]
    assert "mensagem" in body["erro"]


# Subclasses (contexto auth) NAO estao no mapa: o status vem do ancestral pela
# resolucao por MRO (mais especifico primeiro), nao da ordem de insercao do dict.
_CASOS_SUBCLASSE = [
    pytest.param(CredenciaisInvalidasException(), 401, id="credenciais-401"),
    pytest.param(EmailDuplicadoException(), 409, id="email-duplicado-409"),
]


@pytest.mark.parametrize(("exc", "status_code"), _CASOS_SUBCLASSE)
def test_subclasse_resolve_status_do_ancestral_por_mro(
    exc: Exception, status_code: int
) -> None:
    client = _criar_app_com_excecao(exc)
    resp = client.get("/test")
    assert resp.status_code == status_code


def test_dominio_excecao_default_409_quando_fora_do_mapa() -> None:
    # DomainException "pura" (sem entrada no mapa e sem ancestral mapeado) cai
    # no default 409.
    client = _criar_app_com_excecao(DomainException(codigo="X", mensagem="y"))
    resp = client.get("/test")
    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "X"


def test_dominio_excecao_emite_warning_estruturado(
    pipeline_buffer: io.StringIO,
) -> None:
    # Negacoes de dominio (aqui 404) tambem logam: codigo/status/request_id
    # estruturados, sem a mensagem (que pode carregar dado do request).
    client = _criar_app_com_excecao(EntidadeNaoEncontradaException())
    client.get("/test")
    log = pipeline_buffer.getvalue()
    assert "dominio_excecao_tratada" in log
    assert "ENTIDADE_NAO_ENCONTRADA" in log
    assert '"status": 404' in log
    assert "request_id" in log


def test_excecao_generica_retorna_500() -> None:
    client = _criar_app_com_excecao(RuntimeError("boom"))
    resp = client.get("/test")
    assert resp.status_code == 500
    body = resp.json()
    assert body["erro"]["codigo"] == "ERRO_INTERNO"


def test_value_error_retorna_422() -> None:
    client = _criar_app_com_excecao(ValueError("CPF invalido"))
    resp = client.get("/test")
    assert resp.status_code == 422
    body = resp.json()
    assert body["erro"]["codigo"] == "VALOR_INVALIDO"
    assert body["erro"]["mensagem"] == "CPF invalido"
    assert "id_requisicao" in body["erro"]


def test_value_error_envelope_tem_campos_padrao() -> None:
    client = _criar_app_com_excecao(ValueError("Qualquer mensagem"))
    resp = client.get("/test")
    body = resp.json()
    assert set(body["erro"].keys()) == {"codigo", "mensagem", "id_requisicao"}


def test_value_error_mensagem_vazia_preserva_envelope() -> None:
    client = _criar_app_com_excecao(ValueError())
    resp = client.get("/test")
    assert resp.status_code == 422
    body = resp.json()
    assert body["erro"]["codigo"] == "VALOR_INVALIDO"
    assert body["erro"]["mensagem"] == ""


def test_value_error_com_pii_na_mensagem_redigida_no_corpo() -> None:
    # O handler nao pode ecoar str(exc) cru: uma invariante de VO que inclui
    # o valor recebido (CPF/e-mail) vazaria PII no corpo do 422.
    client = _criar_app_com_excecao(
        ValueError("CPF invalido: 123.456.789-00 (contato joao@example.com)")
    )
    resp = client.get("/test")
    assert resp.status_code == 422
    corpo = resp.text
    assert "123.456.789-00" not in corpo
    assert "joao@example.com" not in corpo
    assert resp.json()["erro"]["codigo"] == "VALOR_INVALIDO"


def test_value_error_request_id_fallback_quando_ausente() -> None:
    client = _criar_app_com_excecao(ValueError("CPF invalido"))
    resp = client.get("/test")
    body = resp.json()
    assert body["erro"]["id_requisicao"] == "desconhecido"


def test_request_id_fallback_quando_ausente() -> None:
    # Sem SecurityHeadersMiddleware, request.state nao recebe request_id
    # e o error handler deve cair no fallback "desconhecido".
    client = _criar_app_com_excecao(EntidadeNaoEncontradaException())
    resp = client.get("/test")
    body = resp.json()
    assert body["erro"]["id_requisicao"] == "desconhecido"


@pytest.fixture
def pipeline_buffer() -> Iterator[io.StringIO]:
    """Configura o pipeline real e captura o stdout do root logger.

    O handler 500 usa `logging` stdlib; com o ProcessorFormatter no root
    o log flui para este buffer ja scrubado. Restaura o estado no teardown.
    """
    root = logging.getLogger()
    handlers_anteriores = root.handlers[:]
    nivel_anterior = root.level
    config_anterior = structlog.get_config()

    buffer = io.StringIO()
    configurar_logging(stream=buffer)
    try:
        yield buffer
    finally:
        root.handlers = handlers_anteriores
        root.setLevel(nivel_anterior)
        structlog.configure(**config_anterior)


def test_handler_500_mascara_pii_no_traceback(pipeline_buffer: io.StringIO) -> None:
    # Regressao da issue #86: o handler 500 loga o traceback via stdlib; com o
    # ProcessorFormatter no root o traceback sai mascarado em vez de cru.
    client = _criar_app_com_excecao(
        RuntimeError("falha com CPF 123.456.789-00 e email cliente@example.com")
    )
    resp = client.get("/test")
    assert resp.status_code == 500

    saida = pipeline_buffer.getvalue()
    assert saida, "handler 500 nao emitiu log"
    assert "123.456.789-00" not in saida
    assert "cliente@example.com" not in saida


def test_handler_422_value_error_mascara_pii(pipeline_buffer: io.StringIO) -> None:
    # _value_error_handler tambem loga com exc_info via stdlib (error_handler:82).
    client = _criar_app_com_excecao(ValueError("CPF invalido 987.654.321-00"))
    resp = client.get("/test")
    assert resp.status_code == 422

    saida = pipeline_buffer.getvalue()
    assert "987.654.321-00" not in saida


class _PlacaSchema(BaseModel):
    """Schema minimo para exercitar o 422 de validacao do Pydantic."""

    placa: str = Field(max_length=8)


def _criar_app_com_schema() -> TestClient:
    # Em escopo de modulo (nao local): com `from __future__ import annotations`
    # o FastAPI resolve o tipo do body via get_type_hints, que so enxerga
    # globals do modulo.
    app = FastAPI()
    registrar_error_handlers(app)

    @app.post("/veiculos")
    def _endpoint(body: _PlacaSchema) -> dict[str, str]:
        return {"placa": body.placa}

    return TestClient(app, raise_server_exceptions=False)


class TestRequestValidationSemEcoDeInput:
    """422 de schema (Pydantic) nao ecoa o input cru (TD-033, issue #126).

    O detail default do FastAPI carrega `input` (valor recebido), `ctx` e
    `url`; o handler custom reduz cada item ao trio estavel type/loc/msg.
    """

    def test_422_de_schema_mantem_contrato_detail_sem_input(self) -> None:
        client = _criar_app_com_schema()
        resposta = client.post("/veiculos", json={"placa": "ZZZ-99999"})

        assert resposta.status_code == 422
        corpo = resposta.json()
        assert "ZZZ-99999" not in resposta.text  # valor nunca volta no corpo
        detalhes = corpo["detail"]
        assert isinstance(detalhes, list)
        assert detalhes
        assert set(detalhes[0]) == {"type", "loc", "msg"}
        assert detalhes[0]["type"] == "string_too_long"
        assert detalhes[0]["loc"] == ["body", "placa"]
        # `id_requisicao` e chave IRMA de `detail` (correlacao com logs sem
        # quebrar o contrato da UI, que segue lendo a lista).
        assert corpo["id_requisicao"] == "desconhecido"

    def test_422_de_schema_loga_warning_sem_o_valor(
        self, pipeline_buffer: io.StringIO
    ) -> None:
        client = _criar_app_com_schema()
        client.post("/veiculos", json={"placa": "ZZZ-99999"})
        log = pipeline_buffer.getvalue()
        assert "validacao_schema_tratada_422" in log
        # O `type` do erro (regra violada) e logado; o valor cru nunca.
        assert "string_too_long" in log
        assert "ZZZ-99999" not in log
