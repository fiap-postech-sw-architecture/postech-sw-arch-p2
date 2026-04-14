from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from src.compartilhado.dominio.exceptions import (
    DomainException,
    EntidadeDuplicadaException,
    EntidadeNaoEncontradaException,
    EstoqueInsuficienteException,
    FalhaAutenticacaoException,
    FalhaAutorizacaoException,
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)

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
    FalhaAutorizacaoException: 403,
}


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
    `{erro: {codigo, mensagem, id_requisicao}}`. Os codigos suportados sao 404, 401,
    403 e 409. Excecoes nao tratadas viram 500 com traceback no log e o request_id.
    """

    @app.exception_handler(DomainException)
    async def _domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        request_id = _obter_request_id(request)
        status_code = 409
        for exc_type, code in _EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break
        return JSONResponse(
            status_code=status_code,
            content=_criar_envelope(exc.codigo, exc.mensagem, request_id),
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
