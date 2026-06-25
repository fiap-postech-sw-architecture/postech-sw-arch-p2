"""Operacoes de DLQ da outbox (RF-018): listar e reenfileirar linhas mortas.

Consumido pelo CLI (``scripts/outbox_dlq.py``) e pelo endpoint admin
(``router_admin``). ``reenfileirar`` zera ``tentativas`` e volta
``status='pendente'`` com ``proxima_tentativa_em=now()`` para reentrega
imediata no proximo ciclo do relay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy import Engine


def listar_dead(engine: Engine, limite: int = 100) -> list[dict[str, Any]]:
    """Lista as linhas ``dead`` (mais recentes primeiro).

    Cada linha inclui ``tem_sucessores_pendentes`` (F4): indica se existe
    linha posterior (``id`` maior) do mesmo agregado ainda ``pendente`` — ou
    seja, se este ``dead`` deixou um gap na ordenacao por agregado que pode
    exigir reenfileiramento.
    """
    with engine.begin() as conn:
        linhas = conn.execute(
            text(
                "SELECT o.id, o.agregado_id, o.tipo, o.tentativas, "
                "o.ultimo_erro, o.criado_em, o.status, "
                "EXISTS ( "
                "  SELECT 1 FROM outbox s "
                "  WHERE s.agregado_id = o.agregado_id "
                "    AND s.id > o.id AND s.status = 'pendente' "
                ") AS tem_sucessores_pendentes "
                "FROM outbox o WHERE o.status = 'dead' "
                "ORDER BY o.id DESC LIMIT :limite"
            ),
            {"limite": limite},
        ).all()
    return [
        {
            "id": row.id,
            "agregado_id": str(row.agregado_id),
            "tipo": row.tipo,
            "tentativas": row.tentativas,
            "ultimo_erro": row.ultimo_erro,
            "criado_em": row.criado_em.isoformat() if row.criado_em else None,
            "status": row.status,
            "tem_sucessores_pendentes": bool(row.tem_sucessores_pendentes),
        }
        for row in linhas
    ]


def reenfileirar(engine: Engine, outbox_id: int) -> bool:
    """Volta a linha ``dead`` para ``pendente`` (zera tentativas). True se afetou."""
    with engine.begin() as conn:
        resultado = conn.execute(
            text(
                "UPDATE outbox SET status='pendente', tentativas=0, "
                "proxima_tentativa_em=:agora, ultimo_erro=NULL, entregue_em=NULL "
                "WHERE id = :id AND status = 'dead'"
            ),
            {"id": outbox_id, "agora": datetime.now(UTC)},
        )
    return resultado.rowcount == 1
