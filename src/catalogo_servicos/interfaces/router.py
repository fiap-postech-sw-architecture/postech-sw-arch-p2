from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

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
    from uuid import UUID

    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/servicos", tags=["servicos"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_servico(
    body: CriarServicoRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    use_case = obter_criar_servico(session)
    dto = CriarServicoDTO(nome=body.nome, descricao=body.descricao, preco=body.preco)
    result = use_case.executar(dto)
    return ServicoResponse(**asdict(result))


@router.get("/")
def listar_servicos(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(
        exigir_papel("admin", "atendente", "mecanico")
    ),
    session: Session = Depends(obter_session),
) -> ServicoListaResponse:
    use_case = obter_listar_servicos(session)
    items = use_case.executar(offset=offset, limit=limit)
    total = use_case.contar()
    return ServicoListaResponse(
        items=[ServicoResponse(**asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{servico_id}")
def obter_servico(
    servico_id: UUID,
    usuario: dict[str, object] = Depends(
        exigir_papel("admin", "atendente", "mecanico")
    ),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    use_case = obter_obter_servico(session)
    result = use_case.executar(servico_id)
    return ServicoResponse(**asdict(result))


@router.put("/{servico_id}")
def atualizar_servico(
    servico_id: UUID,
    body: AtualizarServicoRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> ServicoResponse:
    use_case = obter_atualizar_servico(session)
    dto = AtualizarServicoDTO(
        nome=body.nome, descricao=body.descricao, preco=body.preco
    )
    result = use_case.executar(servico_id, dto)
    return ServicoResponse(**asdict(result))


@router.delete("/{servico_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_servico(
    servico_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> None:
    use_case = obter_desativar_servico(session)
    use_case.executar(servico_id)
