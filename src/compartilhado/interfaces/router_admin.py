"""Endpoints administrativos da Transactional Outbox / DLQ (RF-018).

Protegidos pelo guard de role admin (mesma autenticacao JWT da API). Em
producao a DLQ tambem e operavel pela CLI (``scripts/outbox_dlq.py``);
aqui ela e exposta via HTTP para inspecao/reenfileiramento pela banca.

Engine compartilhado (F8): os endpoints reusam o Engine ja criado no
``lifespan`` do app (``request.app.state.engine``) — o MESMO que serve
``obter_session``. Assim ha um unico Engine/pool no processo, com resolucao
de DB-URL unica (a do startup), sem churn de pool por request nem um segundo
singleton para gerir/descartar. A CLI (processo curto) cria o seu proprio
Engine — so o endpoint, de vida longa, reaproveita o do app.

Excecao arquitetural aceita (mesmo racional do ``router_publico``): este
modulo de INTERFACE do kernel compartilhado importa ``exigir_papel`` do
contexto ``autenticacao`` — dependencia kernel->contexto restrita a esta
camada de borda; dominio/aplicacao de compartilhado seguem sem conhecer
contexto algum.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request  # noqa: TC002

from src.autenticacao.interfaces.middleware import exigir_papel
from src.compartilhado.infraestrutura.outbox_dlq import listar_dead, reenfileirar
from src.compartilhado.interfaces.auditoria import ator_de as _ator_de

if TYPE_CHECKING:
    from sqlalchemy import Engine

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin/outbox", tags=["admin"])


def _engine_do_app(request: Request) -> Engine:
    """Retorna o Engine criado no ``lifespan`` (``app.state.engine``).

    503 se ausente: o app so aceita requisicoes apos o startup configurar o
    engine, entao a ausencia indica boot incompleto (nunca cria um engine aqui).
    """
    engine: Engine | None = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Engine nao configurado",
        )
    return engine


@router.get("/dead", dependencies=[Depends(exigir_papel("admin"))])
def listar_dlq(request: Request) -> list[dict[str, Any]]:
    """Lista as linhas da outbox em ``dead`` (DLQ)."""
    return listar_dead(_engine_do_app(request))


@router.post("/dead/{outbox_id}/reenfileirar")
def reenfileirar_dlq(
    outbox_id: int,
    request: Request,
    usuario: Annotated[dict[str, object], Depends(exigir_papel("admin"))],
) -> dict[str, Any]:
    """Reenfileira uma linha ``dead`` (volta a ``pendente``, zera tentativas).

    Acao que muta estado (ressuscita um evento morto) — apos CONFIRMAR a
    mutacao (a linha existia em ``dead``), emite log de auditoria
    ``outbox_reenfileirado_via_admin`` registrando QUEM (o admin autenticado,
    via ``sub`` do JWT) e QUAL ``outbox_id``. O 404 (linha inexistente ou nao
    ``dead``) nao muta nada e portanto NAO gera audit — o evento reflete so o
    que de fato aconteceu.
    """
    if not reenfileirar(_engine_do_app(request), outbox_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linha {outbox_id} nao encontrada em status 'dead'",
        )
    _log.info(
        "outbox_reenfileirado_via_admin",
        outbox_id=outbox_id,
        ator=_ator_de(usuario),
    )
    return {"reenfileirado": True, "id": outbox_id}
