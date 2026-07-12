from __future__ import annotations

from dataclasses import asdict
from typing import Annotated
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Query, status

# Runtime import (nao TYPE_CHECKING): com `from __future__ import annotations`,
# o FastAPI avalia a annotation `Annotated[Session, Depends(...)]` em runtime;
# sem o nome no modulo, a resolucao da annotation falha no startup
# (PydanticUserError: not fully defined) — verificado empiricamente.
from sqlalchemy.orm import Session  # noqa: TC002

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

router = APIRouter(prefix="/api/v1/estoque", tags=["Estoque"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um item de estoque",
)
def criar_item(
    body: CriarItemEstoqueRequest,
    usuario: Annotated[dict[str, object], Depends(exigir_papel(Papel.ADMIN))],
    session: Annotated[Session, Depends(obter_session)],
) -> ItemEstoqueResponse:
    """Cria um item de estoque (nome, descricao, quantidade, preco) e retorna seu id."""
    use_case = obter_criar_item(session)
    dto = CriarItemEstoqueDTO(
        nome=body.nome,
        descricao=body.descricao,
        quantidade=body.quantidade,
        preco_unitario=body.preco_unitario,
    )
    result = use_case.executar(dto)
    return ItemEstoqueResponse(**asdict(result))


@router.get("/", summary="Lista itens de estoque paginados")
def listar_itens(
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.MECANICO))
    ],
    session: Annotated[Session, Depends(obter_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ItemEstoqueListaResponse:
    """Retorna os itens de estoque paginados (offset/limit) com o total."""
    use_case = obter_listar_itens(session)
    items = use_case.executar(offset=offset, limit=limit)
    total = use_case.contar()
    return ItemEstoqueListaResponse(
        items=[ItemEstoqueResponse(**asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{item_id}", summary="Consulta um item de estoque por id")
def obter_item(
    item_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.MECANICO))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> ItemEstoqueResponse:
    """Busca um item de estoque pelo id; 404 se nao existir."""
    use_case = obter_obter_item(session)
    result = use_case.executar(item_id)
    return ItemEstoqueResponse(**asdict(result))


@router.put(
    "/{item_id}",
    summary="Atualiza nome, descricao e preco de um item de estoque",
)
def atualizar_item(
    item_id: UUID,
    body: AtualizarItemEstoqueRequest,
    usuario: Annotated[dict[str, object], Depends(exigir_papel(Papel.ADMIN))],
    session: Annotated[Session, Depends(obter_session)],
) -> ItemEstoqueResponse:
    """Atualiza os dados cadastrais de um item (nao a quantidade); 404 se ausente."""
    use_case = obter_atualizar_item(session)
    dto = AtualizarItemEstoqueDTO(
        nome=body.nome,
        descricao=body.descricao,
        preco_unitario=body.preco_unitario,
    )
    result = use_case.executar(item_id, dto)
    return ItemEstoqueResponse(**asdict(result))


@router.patch(
    "/{item_id}/quantidade",
    summary="Ajusta a quantidade em estoque de um item",
)
def ajustar_quantidade(
    item_id: UUID,
    body: AjustarQuantidadeRequest,
    usuario: Annotated[dict[str, object], Depends(exigir_papel(Papel.ADMIN))],
    session: Annotated[Session, Depends(obter_session)],
) -> ItemEstoqueResponse:
    """Define a nova quantidade absoluta em estoque do item; 404 se nao existir."""
    use_case = obter_ajustar_quantidade(session)
    dto = AjustarQuantidadeDTO(nova_quantidade=body.nova_quantidade)
    result = use_case.executar(item_id, dto)
    return ItemEstoqueResponse(**asdict(result))


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativa (soft-delete) um item de estoque",
)
def desativar_item(
    item_id: UUID,
    usuario: Annotated[dict[str, object], Depends(exigir_papel(Papel.ADMIN))],
    session: Annotated[Session, Depends(obter_session)],
) -> None:
    """Desativa logicamente um item de estoque; 404 se nao existir."""
    use_case = obter_desativar_item(session)
    use_case.executar(item_id)
