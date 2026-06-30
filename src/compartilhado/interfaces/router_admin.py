"""Endpoints administrativos da Transactional Outbox / DLQ (RF-018).

Protegidos pelo guard de role admin (mesma autenticacao JWT da API). Em
producao a DLQ tambem e operavel pela CLI (``scripts/outbox_dlq.py``);
aqui ela e exposta via HTTP para inspecao/reenfileiramento pela banca.

Engine compartilhado (F8): criar/`dispose` um Engine POR REQUEST churna o
pool do Postgres a cada chamada admin. O endpoint reusa um Engine cacheado
em nivel de modulo (lazy singleton), descartado no shutdown via
``encerrar_engine_admin`` (chamado pelo ``lifespan`` do app). A CLI
(processo curto) cria o seu proprio Engine — so o endpoint, de vida longa,
usa o cache.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.autenticacao.interfaces.middleware import exigir_papel
from src.compartilhado.infraestrutura.database import criar_engine
from src.compartilhado.infraestrutura.outbox_dlq import listar_dead, reenfileirar
from src.compartilhado.interfaces.auditoria import ator_de as _ator_de

if TYPE_CHECKING:
    from sqlalchemy import Engine

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin/outbox", tags=["admin"])

# Engine cacheado em nivel de modulo (F8): construido na primeira chamada,
# reusado nas seguintes. Evita churn do pool por request.
_engine_admin: Engine | None = None


def _engine() -> Engine:
    """Retorna o Engine admin cacheado, construindo-o na primeira chamada."""
    global _engine_admin  # noqa: PLW0603 — singleton de modulo deliberado
    if _engine_admin is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DATABASE_URL nao configurada",
            )
        _engine_admin = criar_engine(url)
    return _engine_admin


def encerrar_engine_admin() -> None:
    """Descarta o Engine admin cacheado (chamado no shutdown do app)."""
    global _engine_admin  # noqa: PLW0603 — singleton de modulo deliberado
    if _engine_admin is not None:
        _engine_admin.dispose()
        _engine_admin = None


@router.get("/dead", dependencies=[Depends(exigir_papel("admin"))])
def listar_dlq() -> list[dict[str, Any]]:
    """Lista as linhas da outbox em ``dead`` (DLQ)."""
    return listar_dead(_engine())


@router.post("/dead/{outbox_id}/reenfileirar")
def reenfileirar_dlq(
    outbox_id: int,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
) -> dict[str, Any]:
    """Reenfileira uma linha ``dead`` (volta a ``pendente``, zera tentativas).

    Acao que muta estado (ressuscita um evento morto) — apos CONFIRMAR a
    mutacao (a linha existia em ``dead``), emite log de auditoria
    ``outbox_reenfileirado_via_admin`` registrando QUEM (o admin autenticado,
    via ``sub`` do JWT) e QUAL ``outbox_id``. O 404 (linha inexistente ou nao
    ``dead``) nao muta nada e portanto NAO gera audit — o evento reflete so o
    que de fato aconteceu.
    """
    if not reenfileirar(_engine(), outbox_id):
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
