"""Router publico compartilhado entre bounded contexts.

Contem endpoints que precisam ficar FORA do middleware de auth:

- ``/api/v1/saude`` — health probe para Kubernetes/load balancer
- ``/api/v1/acompanhamento`` — consulta publica de OS por placa+documento
  com rate limiting (10/minute por IP) para mitigar enumeration
- ``/api/v1/publico/ordens-de-servico/{id}/decisao-orcamento`` — canal
  externo de aprovacao/recusa de orcamento (RF-022), autenticado por
  assinatura HMAC por requisicao (``X-Webhook-Signature`` +
  ``X-Webhook-Timestamp``, TD-027; evolui o token estatico da ADR-021),
  fora do RBAC/JWT interno, com o mesmo rate limiting

Os endpoints de OS delegam aos use cases via factories lazy-importadas
do contexto Ordem de Servico. As factories em
``ordem_servico/interfaces/dependencies`` mantem o wiring com
infraestrutura centralizado no composition root, seguindo o mesmo
padrao dos outros routers. O wiring de use case usa import
lazy dentro do handler; os response models (``ordem_servico/interfaces/
schemas.py``) sao importados em tempo de load — dependencia de interface
aceita e restrita a este modulo (o dominio/aplicacao de compartilhado
segue sem conhecer contexto algum).
"""

from __future__ import annotations

import hmac
import os
import time
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from starlette.requests import Request  # noqa: TC002

from src.compartilhado.infraestrutura.webhook_signature import (
    JANELA_ANTI_REPLAY_SEGUNDOS,
    assinar_payload_webhook,
)
from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter
from src.ordem_servico.interfaces.schemas import (
    AcompanhamentoRequest,
    AcompanhamentoResponse,
    DecisaoOrcamentoRequest,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_log = structlog.get_logger(__name__)

router = APIRouter(tags=["publico"])


@router.get("/api/v1/saude", summary="Health probe")
@limiter.exempt  # type: ignore[untyped-decorator]  # slowapi 0.1.9 nao tem stubs
async def saude() -> dict[str, str]:
    """Health probe para Kubernetes/load balancer. Retorna 200 quando o app sobe.

    ``async def`` de proposito: as rotas de API do app sao sync (``def``), entao
    o FastAPI as roda no threadpool do anyio (~40 workers). Sob carga que satura
    esse pool (ex.: teste de carga do HPA), uma ``saude`` sync ficaria na fila
    ATRAS do threadpool cheio e estouraria o ``timeoutSeconds`` das probes ->
    liveness reinicia o pod EXATAMENTE no pico (restart storm que derrota o
    HPA: menos replicas durante o spike). Como ``async``, esta rota corre
    direto no event loop -- ocioso enquanto o trabalho sync esta no threadpool
    -- e responde em microssegundos mesmo com o pool saturado. Assim a liveness
    mede a semantica certa ("event loop vivo?" = processo saudavel), nao "o
    threadpool esta livre?" (um sinal de CARGA, que a readiness/HPA ja tratam).

    ISENTA do rate limit global (issue #81). As probes de liveness E readiness
    do kubelet batem nesta rota, e TODAS saem de um unico IP (o no), que e a
    chave do limiter (``key_func=get_remote_address``). Sob HPA, com varios
    pods, o agregado de probes do mesmo IP estouraria o limite global
    (``60/minute``) -> o kubelet receberia 429 no health check -> o pod seria
    morto e reiniciado (restart storm auto-reforcante: escalar piora, o que
    derrota o proprio HPA). ``@limiter.exempt`` registra esta rota no
    ``_exempt_routes`` do limiter; o ``SlowAPIMiddleware`` (``_should_exempt``)
    entao a deixa passar SEM aplicar os ``default_limits``. A isencao e
    CIRURGICA: so a saude e isenta — as rotas reais de API seguem com o limite
    (proprio ``@limiter.limit`` ou o default global).
    """
    return {"status": "ok"}


@router.post(
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
    corpo: AcompanhamentoRequest,
    session: Session = Depends(obter_session),
) -> AcompanhamentoResponse:
    """Retorna status/timestamps da ordem mais recente para o par informado.

    Raises:
        HTTPException 404: placa+documento nao casam com nenhuma ordem.

    E ``POST`` (nao ``GET``) de proposito: placa e documento sao PII e viajam
    no CORPO, para nao ficarem gravados na URL — access log de proxy/ingress,
    historico de browser, logs de client HTTP (issue #180). A consulta e
    idempotente/somente-leitura; o metodo POST aqui e escolha de privacidade,
    nao de mutacao.

    O 404 e emitido tanto para placa inexistente quanto para documento
    incorreto — resposta de shape constante previne oracle attacks
    (um atacante nao consegue distinguir os dois cenarios pelo corpo
    da resposta; rate limit de 10/min por IP complementa a mitigacao).
    """
    from src.ordem_servico.interfaces.dependencies import (
        obter_consultar_acompanhamento,
    )

    uc = obter_consultar_acompanhamento(session)
    resultado = uc.executar(placa=corpo.placa, documento=corpo.documento)
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ordem nao encontrada",
        )
    return AcompanhamentoResponse.model_validate(resultado)


async def validar_assinatura_webhook(
    request: Request,
    ordem_id: UUID,
    x_webhook_timestamp: str | None = Header(
        default=None,
        description="Unix epoch (segundos) incluido no material assinado (TD-027).",
    ),
    x_webhook_signature: str | None = Header(
        default=None,
        description="HMAC-SHA256 hex de {ordem_id}.{timestamp}. + body (TD-027).",
    ),
) -> None:
    """Valida a assinatura HMAC do canal externo de decisao (TD-027 / RF-022).

    Evolui o token estatico estilo bearer (ADR-021) para uma assinatura por
    requisicao: a chave continua sendo ``ORCAMENTO_WEBHOOK_TOKEN``, mas agora ela
    NAO trafega -- o chamador envia ``X-Webhook-Signature`` (HMAC sobre
    ``{ordem_id}.{timestamp}.`` + body) e ``X-Webhook-Timestamp``. Isso **limita**
    **replay** (a janela de timestamp expira a assinatura capturada; replay
    residual dentro da janela e aceito -- TLS + rate-limit mitigam, nonce-store
    fora de escopo) e fecha **adulteracao** do corpo, sem expor o segredo.

    Regras:
    - ``ORCAMENTO_WEBHOOK_TOKEN`` ausente/vazia no servidor -> 503 (canal
      desabilitado; nunca canal aberto sem credencial).
    - timestamp/assinatura ausente -> 401.
    - timestamp nao-numerico ou fora de +/- ``JANELA_ANTI_REPLAY_SEGUNDOS`` -> 401.
    - assinatura divergente -> 401 (comparacao em tempo constante).

    A env var e lida a cada request (rotacao do Secret sem rebuild).
    """
    # Cada rejeicao e logada com um `motivo` generico + a `ordem_id`; a
    # assinatura recebida NUNCA e logada (evita registrar material sensivel /
    # tentativa de forja). WARNING: sao falhas de autenticacao do canal externo.
    segredo = os.environ.get("ORCAMENTO_WEBHOOK_TOKEN", "")
    if not segredo:
        _log.warning(
            "webhook_auth_falhou", motivo="segredo_nao_configurado", ordem_id=ordem_id
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canal externo de decisao de orcamento desabilitado",
        )
    if not x_webhook_timestamp or not x_webhook_signature:
        _log.warning(
            "webhook_auth_falhou", motivo="cabecalhos_ausentes", ordem_id=ordem_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura do webhook ausente (X-Webhook-Timestamp/Signature)",
        )
    try:
        ts = int(x_webhook_timestamp)
    except ValueError:
        _log.warning(
            "webhook_auth_falhou", motivo="timestamp_nao_numerico", ordem_id=ordem_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Webhook-Timestamp invalido",
        ) from None
    if abs(int(time.time()) - ts) > JANELA_ANTI_REPLAY_SEGUNDOS:
        _log.warning(
            "webhook_auth_falhou", motivo="timestamp_fora_da_janela", ordem_id=ordem_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Webhook-Timestamp fora da janela anti-replay",
        )
    body = await request.body()
    esperado = assinar_payload_webhook(
        segredo, str(ordem_id), x_webhook_timestamp, body
    )
    # Comparacao em BYTES: compare_digest com str levanta TypeError se o
    # header vier com nao-ASCII (viraria 500); em bytes e so assinatura
    # divergente -> 401 (BUG #171).
    if not hmac.compare_digest(esperado.encode(), x_webhook_signature.encode()):
        _log.warning(
            "webhook_auth_falhou", motivo="assinatura_divergente", ordem_id=ordem_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura do webhook invalida",
        )


@router.post(
    "/api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento",
    summary="Decisao externa (aprovacao/recusa) do orcamento",
    response_model=AcompanhamentoResponse,
    dependencies=[Depends(validar_assinatura_webhook)],
    responses={
        401: {
            "description": (
                "Assinatura HMAC ausente/invalida ou timestamp fora da "
                "janela anti-replay (X-Webhook-Timestamp/Signature)."
            )
        },
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
