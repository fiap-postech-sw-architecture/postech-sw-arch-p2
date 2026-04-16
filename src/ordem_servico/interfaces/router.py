"""Router HTTP do contexto Ordem de Servico.

Expoe 15 endpoints cobrindo o ciclo de vida completo da OS: criacao,
CRUD de itens, 9 transicoes de estado (diagnostico, orcamento,
aprovacao, execucao, entrega, cancelamento + 3 variantes de
complementar), alem de listagem, consulta detalhada e metricas.

Todos os endpoints protegidos usam ``Depends(exigir_papel(...))`` com
role sets alinhados ao focus-checklist de ``incremental-step-11.md``:

- admin-only: criar_ordem, aprovar_orcamento, cancelar_ordem,
  rejeitar_complementar, metricas
- admin + mecanico: item mgmt, workflow transitions, aprovar_complementar
- admin + atendente + mecanico: listar_ordens, obter_ordem

O endpoint publico ``/api/v1/acompanhamento`` vive em
``src/compartilhado/interfaces/router_publico.py`` para ficar fora do
middleware de auth (rate-limited a 10/minute).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

from src.autenticacao.interfaces.middleware import exigir_papel
from src.compartilhado.interfaces.dependencies import obter_session
from src.ordem_servico.aplicacao.dtos import (
    AdicionarItemDTO,
    CancelarOrdemDTO,
    CriarOrdemDTO,
)
from src.ordem_servico.interfaces.dependencies import (
    obter_adicionar_item,
    obter_aprovar_complementar,
    obter_aprovar_orcamento,
    obter_cancelar_ordem,
    obter_criar_ordem,
    obter_finalizar_servico,
    obter_gerar_complementar,
    obter_gerar_orcamento,
    obter_iniciar_diagnostico,
    obter_listar_ordens,
    obter_metricas,
    obter_obter_ordem,
    obter_registrar_entrega,
    obter_rejeitar_complementar,
    obter_remover_item,
)
from src.ordem_servico.interfaces.schemas import (
    AdicionarItemRequest,
    CancelarOrdemRequest,
    CriarOrdemRequest,
    MetricasResponse,
    OrdemDeServicoResponse,
    OrdemListaResponse,
    OrdemResumoResponse,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from src.ordem_servico.aplicacao.dtos import OrdemDeServicoDTO

router = APIRouter(prefix="/api/v1/ordens-de-servico", tags=["ordens-de-servico"])


def _to_ordem_response(dto: OrdemDeServicoDTO) -> OrdemDeServicoResponse:
    """Mapeia o DTO de aplicacao para a resposta Pydantic via ``model_validate``.

    Centraliza o mapeamento para evitar ``**dto.__dict__`` splat
    (fragil: silencia campos novos no DTO ou quebra se houver campo
    privado). Usa ``from_attributes=True`` configurado em
    ``OrdemDeServicoResponse``.
    """
    return OrdemDeServicoResponse.model_validate(dto)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma nova ordem de servico",
    response_model=OrdemDeServicoResponse,
)
def criar_ordem(
    body: CriarOrdemRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Abre uma ordem de servico para o par ``cliente + veiculo`` informado."""
    uc = obter_criar_ordem(session)
    dto = CriarOrdemDTO(cliente_id=body.cliente_id, veiculo_id=body.veiculo_id)
    result = uc.executar(dto)
    return _to_ordem_response(result)


@router.get(
    "/",
    summary="Lista ordens paginadas",
    response_model=OrdemListaResponse,
)
def listar_ordens(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(
        exigir_papel("admin", "atendente", "mecanico")
    ),
    session: Session = Depends(obter_session),
) -> OrdemListaResponse:
    """Retorna pagina determinista (criado_em DESC, id) com ``total`` p/ paginacao."""
    uc = obter_listar_ordens(session)
    items = uc.executar(offset=offset, limit=limit)
    total = uc.contar()
    return OrdemListaResponse(
        items=[OrdemResumoResponse.model_validate(i) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/metricas",
    summary="Projecao agregada de ordens (total + por status + tempo medio)",
    response_model=MetricasResponse,
)
def metricas(
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> MetricasResponse:
    """Retorna total, contagem por status e tempo medio de execucao em minutos."""
    uc = obter_metricas(session)
    result = uc.executar()
    return MetricasResponse.model_validate(result)


@router.get(
    "/{ordem_id}",
    summary="Consulta detalhada de uma ordem por id",
    response_model=OrdemDeServicoResponse,
)
def obter_ordem(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(
        exigir_papel("admin", "atendente", "mecanico")
    ),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Retorna a projecao completa da ordem (itens + orcamento + timestamps)."""
    uc = obter_obter_ordem(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/itens",
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona um item a uma ordem",
    response_model=OrdemDeServicoResponse,
)
def adicionar_item(
    ordem_id: UUID,
    body: AdicionarItemRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Valida servico via ``CatalogoPort`` e adiciona o item a ordem."""
    uc = obter_adicionar_item(session)
    dto = AdicionarItemDTO(
        servico_catalogo_id=body.servico_catalogo_id,
        item_estoque_id=body.item_estoque_id,
        descricao=body.descricao,
        quantidade=body.quantidade,
    )
    result = uc.executar(ordem_id, dto)
    return _to_ordem_response(result)


@router.delete(
    "/{ordem_id}/itens/{item_id}",
    summary="Remove um item da ordem e retorna a ordem atualizada",
    response_model=OrdemDeServicoResponse,
)
def remover_item(
    ordem_id: UUID,
    item_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Remove o item por id; retorna a ordem atualizada (status, lista de itens).

    Retorna 200 + body por consistencia com os outros endpoints de mutacao
    (convencao do PR #62: toda mutacao devolve ``OrdemDeServicoResponse``).
    """
    uc = obter_remover_item(session)
    result = uc.executar(ordem_id, item_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/diagnostico",
    summary="RECEBIDA -> EM_DIAGNOSTICO",
    response_model=OrdemDeServicoResponse,
)
def iniciar_diagnostico(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Transita a ordem para ``EM_DIAGNOSTICO`` e emite ``DiagnosticoIniciadoEvent``."""
    uc = obter_iniciar_diagnostico(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/orcamento",
    summary="EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO",
    response_model=OrdemDeServicoResponse,
)
def gerar_orcamento(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Calcula o orcamento e transita a ordem para ``AGUARDANDO_APROVACAO``."""
    uc = obter_gerar_orcamento(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/aprovacao",
    summary="AGUARDANDO_APROVACAO -> EM_EXECUCAO",
    response_model=OrdemDeServicoResponse,
)
def aprovar_orcamento(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Aprova o orcamento, reserva estoque e transita para ``EM_EXECUCAO``."""
    uc = obter_aprovar_orcamento(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/finalizacao",
    summary="EM_EXECUCAO -> FINALIZADA",
    response_model=OrdemDeServicoResponse,
)
def finalizar_servico(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Transita a ordem para ``FINALIZADA`` e emite ``ServicoFinalizadoEvent``."""
    uc = obter_finalizar_servico(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/entrega",
    summary="FINALIZADA -> ENTREGUE",
    response_model=OrdemDeServicoResponse,
)
def registrar_entrega(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Transita a ordem para ``ENTREGUE`` e emite ``EntregaRegistradaEvent``."""
    uc = obter_registrar_entrega(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/cancelamento",
    summary="Qualquer estado ativo -> CANCELADA",
    response_model=OrdemDeServicoResponse,
)
def cancelar_ordem(
    ordem_id: UUID,
    body: CancelarOrdemRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Cancela a ordem e libera reservas de estoque ativas (se houver)."""
    uc = obter_cancelar_ordem(session)
    result = uc.executar(ordem_id, CancelarOrdemDTO(motivo=body.motivo))
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/orcamento-complementar",
    summary="EM_EXECUCAO -> AGUARDANDO_APROVACAO_COMPLEMENTAR",
    response_model=OrdemDeServicoResponse,
)
def gerar_complementar(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Regenera o orcamento apos novos itens e transita para aprovacao complementar."""
    uc = obter_gerar_complementar(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/aprovacao-complementar",
    summary="AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO (aprovado)",
    response_model=OrdemDeServicoResponse,
)
def aprovar_complementar(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "mecanico")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Aprova o orcamento complementar e retorna a ordem a ``EM_EXECUCAO``."""
    uc = obter_aprovar_complementar(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)


@router.post(
    "/{ordem_id}/rejeicao-complementar",
    summary="AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO (rejeitado)",
    response_model=OrdemDeServicoResponse,
)
def rejeitar_complementar(
    ordem_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> OrdemDeServicoResponse:
    """Rejeita o orcamento complementar e retorna a ordem a ``EM_EXECUCAO``."""
    uc = obter_rejeitar_complementar(session)
    result = uc.executar(ordem_id)
    return _to_ordem_response(result)
