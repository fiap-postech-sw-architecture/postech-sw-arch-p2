"""Excecoes tipadas levantadas pelo ``SystemClient``.

Mapeiam os status HTTP retornados pelo handler de excecoes da API
(``src/compartilhado/interfaces/error_handler.py``). O envelope de erro
padrao e ``{"erro": {"codigo", "mensagem", "id_requisicao"}}``; 422 e
RateLimitExceeded usam shape proprio (``{"detail": ...}``), tratados no
``SystemClient._raise_for_status``.
"""

from __future__ import annotations


class SystemClientError(Exception):
    """Erro base do SystemClient. Carrega status HTTP + corpo estruturado."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        correlation_id: str | None,
    ) -> None:
        super().__init__(f"[{status_code}] {detail} (req_id={correlation_id})")
        self.status_code = status_code
        self.detail = detail
        self.correlation_id = correlation_id


class NaoAutenticadoError(SystemClientError):
    """401: token ausente, invalido, expirado ou revogado."""


class NaoAutorizadoError(SystemClientError):
    """403: papel nao autorizado (violou matriz RBAC)."""


class NaoEncontradoError(SystemClientError):
    """404: recurso inexistente."""


class ValidacaoError(SystemClientError):
    """400 / 422: payload invalido ou regra de dominio violada na entrada."""


class ConflitoError(SystemClientError):
    """409: transicao invalida de estado, FK quebrada, email duplicado."""


class RateLimitError(SystemClientError):
    """429: rate limit excedido. Expor ``retry_after_seconds`` quando presente."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        correlation_id: str | None,
        retry_after_seconds: float | None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail,
            correlation_id=correlation_id,
        )
        self.retry_after_seconds = retry_after_seconds


class ErroInternoError(SystemClientError):
    """5xx: erro do servidor."""


_STATUS_TO_ERROR: dict[int, type[SystemClientError]] = {
    400: ValidacaoError,
    401: NaoAutenticadoError,
    403: NaoAutorizadoError,
    404: NaoEncontradoError,
    409: ConflitoError,
    422: ValidacaoError,
}


def erro_para(status_code: int) -> type[SystemClientError]:
    """Retorna a classe de erro adequada para o ``status_code``.

    5xx -> ``ErroInternoError``. Status nao mapeados -> ``SystemClientError``.
    """
    if 500 <= status_code < 600:
        return ErroInternoError
    return _STATUS_TO_ERROR.get(status_code, SystemClientError)
