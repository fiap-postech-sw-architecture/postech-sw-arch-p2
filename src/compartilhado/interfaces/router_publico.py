from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Publico"])


@router.get("/api/v1/saude")
def saude() -> dict[str, str]:
    """Health probe para Kubernetes/load balancer. Retorna 200 quando o app sobe."""
    return {"status": "ok"}
