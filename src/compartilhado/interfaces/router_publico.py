"""Router publico compartilhado entre bounded contexts.

Contem endpoints que precisam ficar FORA do middleware de auth:

- ``/api/v1/saude`` — health probe para Kubernetes/load balancer
- ``/api/v1/acompanhamento`` — consulta publica de OS por placa+documento
  com rate limiting (10/minute por IP) para mitigar enumeration
- ``/api/v1/publico/ordens-de-servico/{id}/decisao-orcamento`` — canal
  externo de aprovacao/recusa de orcamento (RF-022), autenticado por
  token estatico dedicado em ``X-Webhook-Token`` (ADR-021), fora do
  RBAC/JWT interno, com o mesmo rate limiting

Os endpoints de OS delegam aos use cases via factories lazy-importadas
do contexto Ordem de Servico. As factories em
``ordem_servico/interfaces/dependencies`` mantem o wiring com
infraestrutura centralizado no composition root, seguindo o mesmo
padrao dos outros routers. O import lazy dentro do handler preserva a
direcao do onion (compartilhado nao importa ordem_servico em tempo de
load).
"""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from starlette.requests import Request  # noqa: TC002

from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter
from src.ordem_servico.interfaces.schemas import (
    AcompanhamentoResponse,
    DecisaoOrcamentoRequest,
)

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


def validar_token_webhook(
    x_webhook_token: str | None = Header(
        default=None,
        description="Token estatico do canal externo de decisao (ADR-021).",
    ),
) -> None:
    """Valida o token estatico do canal externo de decisao de orcamento.

    Regras (ADR-021):

    - ``ORCAMENTO_WEBHOOK_TOKEN`` ausente/vazia no servidor -> 503: canal
      desabilitado e indisponibilidade configurada do servidor, nao erro
      de credencial do chamador — e nunca canal aberto sem credencial.
    - Header ausente ou divergente -> 401. Comparacao em tempo constante
      (``secrets.compare_digest`` sobre bytes) para nao vazar prefixos do
      token por timing.

    A env var e lida a cada request (mesmo padrao do ``JWT_SECRET`` em
    ``autenticacao/interfaces/dependencies.py``), permitindo rotacao do
    Secret sem rebuild e simplificando testes.
    """
    esperado = os.environ.get("ORCAMENTO_WEBHOOK_TOKEN", "")
    if not esperado:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canal externo de decisao de orcamento desabilitado",
        )
    recebido = x_webhook_token or ""
    if not secrets.compare_digest(recebido.encode(), esperado.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de webhook ausente ou invalido",
        )


@router.post(
    "/api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento",
    summary="Decisao externa (aprovacao/recusa) do orcamento",
    response_model=AcompanhamentoResponse,
    dependencies=[Depends(validar_token_webhook)],
    responses={
        401: {"description": "Header X-Webhook-Token ausente ou divergente."},
        404: {"description": "Ordem nao encontrada."},
        409: {
            "description": (
                "Ordem fora de aguardando_aprovacao / "
                "aguardando_aprovacao_complementar."
            )
        },
        429: {"description": "Rate limit excedido (10/minute por IP)."},
        503: {
            "description": (
                "ORCAMENTO_WEBHOOK_TOKEN nao configurado no servidor "
                "(canal externo desabilitado)."
            )
        },
    },
)
@limiter.limit("10/minute")
def decisao_orcamento(
    request: Request,
    ordem_id: UUID,
    body: DecisaoOrcamentoRequest,
    session: Session = Depends(obter_session),
) -> AcompanhamentoResponse:
    """Canal externo de aprovacao/recusa do orcamento (RF-022, ADR-021).

    ``aprovada`` transita a OS para ``em_execucao`` pelo caminho inicial
    ou complementar conforme o estado corrente; ``recusada`` cancela a
    OS com motivo fixo. A resposta reusa a projecao publica do
    acompanhamento (status/situacao + timestamps): nada de itens,
    orcamento ou dados do cliente atravessa o canal externo (LGPD).
    """
    from src.ordem_servico.interfaces.dependencies import (
        obter_decidir_orcamento,
    )

    uc = obter_decidir_orcamento(session)
    resultado = uc.executar(ordem_id, decisao=body.decisao)
    return AcompanhamentoResponse.model_validate(resultado)
