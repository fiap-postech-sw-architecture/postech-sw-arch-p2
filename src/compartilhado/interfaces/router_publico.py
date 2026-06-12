"""Router publico compartilhado entre bounded contexts.

Contem endpoints que precisam ficar FORA do middleware de auth:

- ``/api/v1/saude`` — health probe para Kubernetes/load balancer
- ``/api/v1/acompanhamento`` — consulta publica de OS por placa+documento
  com rate limiting (10/minute por IP) para mitigar enumeration

O endpoint de acompanhamento delega ao use case
``ConsultarAcompanhamento`` via factory lazy-importada do contexto
Ordem de Servico. A factory em ``ordem_servico/interfaces/dependencies``
mantem o wiring com infraestrutura centralizado no composition root,
seguindo o mesmo padrao dos outros routers. O import lazy dentro do
handler preserva a direcao do onion (compartilhado nao importa
ordem_servico em tempo de load).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from starlette.requests import Request  # noqa: TC002

from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter
from src.ordem_servico.interfaces.schemas import AcompanhamentoResponse

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(tags=["publico"])


@router.get("/api/v1/saude", summary="Health probe")
def saude() -> dict[str, str]:
    """Health probe para Kubernetes/load balancer. Retorna 200 quando o app sobe."""
    return {"status": "ok"}


@router.get(
    "/api/v1/acompanhamento",
    summary="Consulta publica de ordem por placa + documento",
    response_model=AcompanhamentoResponse,
    responses={
        404: {"description": "Nenhuma ordem encontrada para o par placa+documento."},
        429: {"description": "Rate limit excedido (10/minute por IP)."},
    },
)
@limiter.limit("10/minute")
def acompanhamento(
    request: Request,
    placa: str = Query(
        min_length=7,
        max_length=8,
        description="Placa do veiculo (7 chars sem hifen ou 8 com hifen).",
    ),
    documento: str = Query(
        min_length=11,
        max_length=18,
        description="CPF (11 digitos) ou CNPJ (14 digitos), com ou sem mascara.",
    ),
    session: Session = Depends(obter_session),
) -> AcompanhamentoResponse:
    """Retorna status/timestamps da ordem mais recente para o par informado.

    Raises:
        HTTPException 404: placa+documento nao casam com nenhuma ordem.

    O 404 e emitido tanto para placa inexistente quanto para documento
    incorreto — resposta de shape constante previne oracle attacks
    (um atacante nao consegue distinguir os dois cenarios pelo corpo
    da resposta; rate limit de 10/min por IP complementa a mitigacao).
    """
    from src.ordem_servico.interfaces.dependencies import (
        obter_consultar_acompanhamento,
    )

    uc = obter_consultar_acompanhamento(session)
    resultado = uc.executar(placa=placa, documento=documento)
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem nao encontrada",
        )
    return AcompanhamentoResponse.model_validate(resultado)
