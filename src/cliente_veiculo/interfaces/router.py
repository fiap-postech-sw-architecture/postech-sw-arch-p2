from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, status

from src.autenticacao.interfaces.middleware import exigir_papel
from src.cliente_veiculo.aplicacao.dtos import (
    AdicionarVeiculoDTO,
    AtualizarClienteDTO,
    CriarClienteDTO,
)
from src.cliente_veiculo.interfaces.dependencies import (
    obter_adicionar_veiculo,
    obter_atualizar_cliente,
    obter_criar_cliente,
    obter_desativar_cliente,
    obter_listar_clientes,
    obter_listar_veiculos,
    obter_obter_cliente,
    obter_remover_veiculo,
)
from src.cliente_veiculo.interfaces.schemas import (
    AdicionarVeiculoRequest,
    AtualizarClienteRequest,
    ClienteListaResponse,
    ClienteResponse,
    ClienteResumoResponse,
    CriarClienteRequest,
    VeiculoResponse,
)
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/clientes", tags=["clientes"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_cliente(
    body: CriarClienteRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteResponse:
    """Cria um novo cliente com CPF ou CNPJ e dados de contato."""
    uc = obter_criar_cliente(session)
    dto = CriarClienteDTO(
        nome=body.nome,
        documento=body.documento,
        tipo_documento=body.tipo_documento,
        contato=body.contato,
    )
    result = uc.executar(dto)
    return ClienteResponse(**asdict(result))


@router.get("/")
def listar_clientes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteListaResponse:
    """Lista clientes paginados retornando total, offset e limit."""
    uc = obter_listar_clientes(session)
    items = uc.executar(offset=offset, limit=limit)
    total = uc.contar()
    return ClienteListaResponse(
        items=[ClienteResumoResponse(**asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{cliente_id}")
def obter_cliente(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteResponse:
    """Retorna os detalhes completos do cliente incluindo veiculos."""
    uc = obter_obter_cliente(session)
    result = uc.executar(cliente_id)
    return ClienteResponse(**asdict(result))


@router.put("/{cliente_id}")
def atualizar_cliente(
    cliente_id: UUID,
    body: AtualizarClienteRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteResponse:
    """Atualiza nome e contato do cliente preservando documento e veiculos."""
    uc = obter_atualizar_cliente(session)
    dto = AtualizarClienteDTO(nome=body.nome, contato=body.contato)
    result = uc.executar(cliente_id, dto)
    return ClienteResponse(**asdict(result))


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_cliente(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> None:
    """Desativa o cliente. Rejeita quando ha ordem de servico em andamento."""
    uc = obter_desativar_cliente(session)
    uc.executar(cliente_id)


@router.post("/{cliente_id}/veiculos", status_code=status.HTTP_201_CREATED)
def adicionar_veiculo(
    cliente_id: UUID,
    body: AdicionarVeiculoRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> VeiculoResponse:
    """Adiciona um veiculo ao cliente validando a unicidade da placa."""
    uc = obter_adicionar_veiculo(session)
    dto = AdicionarVeiculoDTO(
        placa=body.placa,
        marca=body.marca,
        modelo=body.modelo,
        ano=body.ano,
    )
    result = uc.executar(cliente_id, dto)
    return VeiculoResponse(**asdict(result))


@router.get("/{cliente_id}/veiculos")
def listar_veiculos(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> list[VeiculoResponse]:
    """Lista todos os veiculos associados ao cliente informado."""
    uc = obter_listar_veiculos(session)
    items = uc.executar(cliente_id)
    return [VeiculoResponse(**asdict(v)) for v in items]


@router.delete(
    "/{cliente_id}/veiculos/{veiculo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_veiculo(
    cliente_id: UUID,
    veiculo_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> None:
    """Remove um veiculo do cliente. Rejeita se houver OS ativa no veiculo."""
    uc = obter_remover_veiculo(session)
    uc.executar(cliente_id, veiculo_id)
