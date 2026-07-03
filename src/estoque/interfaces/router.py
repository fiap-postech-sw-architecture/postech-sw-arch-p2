from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Query, status

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.interfaces.middleware import exigir_papel
from src.compartilhado.interfaces.dependencies import obter_session
from src.estoque.aplicacao.dtos import (
    AjustarQuantidadeDTO,
    AtualizarItemEstoqueDTO,
    CriarItemEstoqueDTO,
)
from src.estoque.interfaces.dependencies import (
    obter_ajustar_quantidade,
    obter_atualizar_item,
    obter_criar_item,
    obter_desativar_item,
    obter_listar_itens,
    obter_obter_item,
)
from src.estoque.interfaces.schemas import (
    AjustarQuantidadeRequest,
    AtualizarItemEstoqueRequest,
    CriarItemEstoqueRequest,
    ItemEstoqueListaResponse,
    ItemEstoqueResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/estoque", tags=["Estoque"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_item(
    body: CriarItemEstoqueRequest,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> ItemEstoqueResponse:
    use_case = obter_criar_item(session)
    dto = CriarItemEstoqueDTO(
        nome=body.nome,
        descricao=body.descricao,
        quantidade=body.quantidade,
        preco_unitario=body.preco_unitario,
    )
    result = use_case.executar(dto)
    return ItemEstoqueResponse(**asdict(result))


@router.get("/")
def listar_itens(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN, Papel.MECANICO)),
    session: Session = Depends(obter_session),
) -> ItemEstoqueListaResponse:
    use_case = obter_listar_itens(session)
    items = use_case.executar(offset=offset, limit=limit)
    total = use_case.contar()
    return ItemEstoqueListaResponse(
        items=[ItemEstoqueResponse(**asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{item_id}")
def obter_item(
    item_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN, Papel.MECANICO)),
    session: Session = Depends(obter_session),
) -> ItemEstoqueResponse:
    use_case = obter_obter_item(session)
    result = use_case.executar(item_id)
    return ItemEstoqueResponse(**asdict(result))


@router.put("/{item_id}")
def atualizar_item(
    item_id: UUID,
    body: AtualizarItemEstoqueRequest,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> ItemEstoqueResponse:
    use_case = obter_atualizar_item(session)
    dto = AtualizarItemEstoqueDTO(
        nome=body.nome,
        descricao=body.descricao,
        preco_unitario=body.preco_unitario,
    )
    result = use_case.executar(item_id, dto)
    return ItemEstoqueResponse(**asdict(result))


@router.patch("/{item_id}/quantidade")
def ajustar_quantidade(
    item_id: UUID,
    body: AjustarQuantidadeRequest,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> ItemEstoqueResponse:
    use_case = obter_ajustar_quantidade(session)
    dto = AjustarQuantidadeDTO(nova_quantidade=body.nova_quantidade)
    result = use_case.executar(item_id, dto)
    return ItemEstoqueResponse(**asdict(result))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_item(
    item_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel(Papel.ADMIN)),
    session: Session = Depends(obter_session),
) -> None:
    use_case = obter_desativar_item(session)
    use_case.executar(item_id)
