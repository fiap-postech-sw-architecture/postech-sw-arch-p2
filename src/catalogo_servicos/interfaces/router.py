from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Query, status

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.interfaces.middleware import exigir_papel
from src.catalogo_servicos.aplicacao.dtos import (
    AtualizarServicoDTO,
    CriarServicoDTO,
)
from src.catalogo_servicos.interfaces.dependencies import (
    obter_atualizar_servico,
    obter_criar_servico,
    obter_desativar_servico,
    obter_listar_servicos,
    obter_obter_servico,
)
from src.catalogo_servicos.interfaces.schemas import (
    AtualizarServicoRequest,
    CriarServicoRequest,
    ServicoListaResponse,
    ServicoResponse,
)
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/servicos", tags=["servicos"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um servico no catalogo",
)
def criar_servico(
    body: CriarServicoRequest,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    """Cria um servico oferecido (nome, descricao, preco) e retorna seu id."""
    use_case = obter_criar_servico(session)
    dto = CriarServicoDTO(nome=body.nome, descricao=body.descricao, preco=body.preco)
    result = use_case.executar(dto)
    return ServicoResponse(**dataclasses.asdict(result))


@router.get("/", summary="Lista servicos do catalogo paginados")
def listar_servicos(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(
        exigir_papel(Papel.ADMIN, Papel.ATENDENTE, Papel.MECANICO)
    ),
    session: Session = Depends(obter_session),
) -> ServicoListaResponse:
    """Retorna os servicos oferecidos paginados (offset/limit) com o total."""
    use_case = obter_listar_servicos(session)
    items = use_case.executar(offset=offset, limit=limit)
    total = use_case.contar()
    return ServicoListaResponse(
        items=[ServicoResponse(**dataclasses.asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{servico_id}", summary="Consulta um servico do catalogo por id")
def obter_servico(
    servico_id: UUID,
    usuario: dict[str, object] = Depends(
        exigir_papel(Papel.ADMIN, Papel.ATENDENTE, Papel.MECANICO)
    ),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    """Busca um servico oferecido pelo id; 404 se nao existir."""
    use_case = obter_obter_servico(session)
    result = use_case.executar(servico_id)
    return ServicoResponse(**dataclasses.asdict(result))


@router.put("/{servico_id}", summary="Atualiza nome, descricao e preco de um servico")
def atualizar_servico(
    servico_id: UUID,
    body: AtualizarServicoRequest,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    """Atualiza os dados de um servico oferecido; 404 se nao existir."""
    use_case = obter_atualizar_servico(session)
    dto = AtualizarServicoDTO(
        nome=body.nome, descricao=body.descricao, preco=body.preco
    )
    result = use_case.executar(servico_id, dto)
    return ServicoResponse(**dataclasses.asdict(result))


@router.delete(
    "/{servico_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativa (soft-delete) um servico do catalogo",
)
def desativar_servico(
    servico_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> None:
    """Desativa logicamente um servico oferecido; 404 se nao existir."""
    use_case = obter_desativar_servico(session)
    use_case.executar(servico_id)
