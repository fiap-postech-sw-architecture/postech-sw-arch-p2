"""Notificacao padrao de erros de API nas paginas.

Extraido dos blocos ``except ValidacaoError/ConflitoEstadoError/ApiError``
que se repetiam em ordens_servico (4x) e faltavam nos dialogs de clientes/
catalogo/estoque (onde 422 aparecia como ``Erro: Validacao falhou`` sem
dizer qual campo).
"""

from __future__ import annotations

from nicegui import ui

from ui.cliente_api import ApiError, ConflitoEstadoError, ValidacaoError


def notificar_erro_api(exc: ApiError) -> None:
    """``ui.notify`` com mensagem amigavel por tipo de erro de API.

    - 422: junta as ``msg`` do detail do FastAPI (padrao de ordens_servico);
    - 409: mostra a regra de negocio violada como warning;
    - demais: mensagem generica negativa.
    """
    if isinstance(exc, ValidacaoError):
        msgs = "; ".join(str(d.get("msg", "")) for d in exc.detalhes)
        ui.notify(f"Invalido: {msgs}", type="negative")
    elif isinstance(exc, ConflitoEstadoError):
        ui.notify(f"Nao permitido: {exc.detail}", type="warning")
    else:
        ui.notify(f"Erro: {exc}", type="negative")
