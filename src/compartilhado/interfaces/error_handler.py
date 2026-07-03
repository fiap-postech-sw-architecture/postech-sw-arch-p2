from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.compartilhado.dominio.exceptions import (
    DomainException,
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
    EstoqueInsuficienteException,
    FalhaAutenticacaoException,
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)
from src.compartilhado.infraestrutura.logging import redigir_pii_erro

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request

logger = logging.getLogger(__name__)

_EXCEPTION_STATUS_MAP: dict[type[DomainException], int] = {
    EntidadeNaoEncontradaException: 404,
    ViolacaoRegraDeNegocioException: 409,
    TransicaoStatusInvalidaException: 409,
    EstoqueInsuficienteException: 409,
    EntidadeDuplicadaException: 409,
    FalhaAutenticacaoException: 401,
}

# DomainException fora do mapa acima e, por definicao, uma regra de negocio
# violada -> 409 Conflict e o default mais fiel (nunca 500: a excecao e
# esperada e carrega codigo/mensagem proprios).
_STATUS_DEFAULT = 409


def _obter_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "desconhecido")


def _criar_envelope(codigo: str, mensagem: str, request_id: str) -> dict[str, object]:
    return {
        "erro": {
            "codigo": codigo,
            "mensagem": mensagem,
            "id_requisicao": request_id,
        }
    }


def registrar_error_handlers(app: FastAPI) -> None:
    """Registra handlers que mapeiam DomainException para envelopes HTTP.

    Cada DomainException levantada no request vira um JSONResponse com o envelope
    `{erro: {codigo, mensagem, id_requisicao}}`. Os codigos suportados sao 401,
    404, 409 e 422. ValueError (invariantes de value object/aggregate) vira
    422 VALOR_INVALIDO -- ver issue #83. Excecoes nao tratadas viram 500 com traceback
    no log e o request_id.
    """

    @app.exception_handler(DomainException)
    async def _domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        request_id = _obter_request_id(request)
        status_code = _STATUS_DEFAULT
        for exc_type, code in _EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break
        return JSONResponse(
            status_code=status_code,
            content=_criar_envelope(exc.codigo, exc.mensagem, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # O detail default do FastAPI/Pydantic ecoa o `input` cru (e um `ctx`
        # de conteudo variavel) de cada campo invalido -- PII enviada num campo
        # malformado voltaria no corpo do 422 (TD-033). Mantemos o contrato
        # `{"detail": [...]}` (a UI consome a lista) mas cada item carrega so o
        # trio estavel type/loc/msg: as msgs do Pydantic descrevem a REGRA
        # violada, nao o valor recebido.
        request_id = _obter_request_id(request)
        detalhes = [
            {"type": erro.get("type"), "loc": erro.get("loc"), "msg": erro.get("msg")}
            for erro in exc.errors()
        ]
        logger.warning(
            "Erro de validacao de schema tratado como 422 (request_id=%s): %s",
            request_id,
            [(d["type"], d["loc"]) for d in detalhes],
        )
        # `id_requisicao` como chave IRMA de `detail`: correlaciona o 422 com
        # os logs sem quebrar o contrato da UI (que le a lista de `detail`).
        return JSONResponse(
            status_code=422,
            content={"detail": detalhes, "id_requisicao": request_id},
        )

    @app.exception_handler(ValueError)
    async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        request_id = _obter_request_id(request)
        logger.warning(
            "ValueError tratado como 422 (request_id=%s): %s",
            request_id,
            exc,
            exc_info=exc,
        )
        # str(exc) pode ecoar o valor recebido (ex.: CPF cru numa invariante
        # de value object) -- redige PII antes de devolver ao cliente.
        return JSONResponse(
            status_code=422,
            content=_criar_envelope(
                "VALOR_INVALIDO", redigir_pii_erro(str(exc)), request_id
            ),
        )

    @app.exception_handler(Exception)
    async def _generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _obter_request_id(request)
        logger.exception("Erro interno (request_id=%s)", request_id)
        return JSONResponse(
            status_code=500,
            content=_criar_envelope(
                "ERRO_INTERNO",
                "Erro interno do servidor",
                request_id,
            ),
        )
