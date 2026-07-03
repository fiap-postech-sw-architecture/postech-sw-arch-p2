from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003

import structlog
from fastapi import APIRouter, Depends, Query, status

from src.autenticacao.interfaces.middleware import exigir_papel
from src.cliente_veiculo.aplicacao.dtos import (
    AdicionarVeiculoDTO,
    AtualizarClienteDTO,
    CriarClienteDTO,
    RegistrarConsentimentoDTO,
)
from src.cliente_veiculo.interfaces.dependencies import (
    obter_adicionar_veiculo,
    obter_atualizar_cliente,
    obter_criar_cliente,
    obter_desativar_cliente,
    obter_excluir_dados,
    obter_exportar_dados,
    obter_listar_clientes,
    obter_listar_veiculos,
    obter_obter_cliente,
    obter_registrar_consentimento,
    obter_remover_veiculo,
    obter_revogar_consentimento,
)
from src.cliente_veiculo.interfaces.schemas import (
    AdicionarVeiculoRequest,
    AtualizarClienteRequest,
    ClienteListaResponse,
    ClienteResponse,
    ClienteResumoResponse,
    ConsentimentoRequest,
    ConsentimentoResponse,
    CriarClienteRequest,
    DadosPessoaisResponse,
    VeiculoResponse,
)
from src.compartilhado.interfaces.auditoria import ator_de
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/clientes", tags=["clientes"])
_log = structlog.get_logger(__name__)


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_cliente(
    body: CriarClienteRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteResponse:
    uc = obter_criar_cliente(session)
    dto = CriarClienteDTO(
        nome=body.nome,
        documento=body.documento,
        tipo_documento=body.tipo_documento,
        contato=body.contato,
    )
    result = uc.executar(dto)
    return ClienteResponse(**dataclasses.asdict(result))


@router.get("/")
def listar_clientes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteListaResponse:
    uc = obter_listar_clientes(session)
    items = uc.executar(offset=offset, limit=limit)
    total = uc.contar()
    return ClienteListaResponse(
        items=[ClienteResumoResponse(**dataclasses.asdict(item)) for item in items],
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
    uc = obter_obter_cliente(session)
    result = uc.executar(cliente_id)
    return ClienteResponse(**dataclasses.asdict(result))


@router.put("/{cliente_id}")
def atualizar_cliente(
    cliente_id: UUID,
    body: AtualizarClienteRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ClienteResponse:
    uc = obter_atualizar_cliente(session)
    dto = AtualizarClienteDTO(nome=body.nome, contato=body.contato)
    result = uc.executar(cliente_id, dto)
    return ClienteResponse(**dataclasses.asdict(result))


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_cliente(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> None:
    uc = obter_desativar_cliente(session)
    uc.executar(cliente_id)


@router.post("/{cliente_id}/veiculos", status_code=status.HTTP_201_CREATED)
def adicionar_veiculo(
    cliente_id: UUID,
    body: AdicionarVeiculoRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> VeiculoResponse:
    uc = obter_adicionar_veiculo(session)
    dto = AdicionarVeiculoDTO(
        placa=body.placa,
        marca=body.marca,
        modelo=body.modelo,
        ano=body.ano,
    )
    result = uc.executar(cliente_id, dto)
    return VeiculoResponse(**dataclasses.asdict(result))


@router.get("/{cliente_id}/veiculos")
def listar_veiculos(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> list[VeiculoResponse]:
    uc = obter_listar_veiculos(session)
    items = uc.executar(cliente_id)
    return [VeiculoResponse(**dataclasses.asdict(v)) for v in items]


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
    uc = obter_remover_veiculo(session)
    uc.executar(cliente_id, veiculo_id)


def _exportar_dados_pessoais_e_auditar(
    cliente_id: UUID,
    usuario: dict[str, object],
    session: Session,
    via: str,
) -> DadosPessoaisResponse:
    """Executa o export LGPD e registra a trilha de auditoria (#76).

    Compartilhado pelos dois GETs de dados pessoais; `via` distingue a rota
    de origem no log. O audit e emitido APOS o efeito (404 nao audita).
    """
    uc = obter_exportar_dados(session)
    result = uc.executar(cliente_id)
    _log.info(
        "dados_pessoais_exportados_via_admin",
        cliente_id=str(cliente_id),
        ator=ator_de(usuario),
        via=via,
    )
    return DadosPessoaisResponse(**dataclasses.asdict(result))


@router.get("/{cliente_id}/dados-pessoais")
def obter_dados_pessoais(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> DadosPessoaisResponse:
    return _exportar_dados_pessoais_e_auditar(cliente_id, usuario, session, "obter")


@router.get("/{cliente_id}/dados-pessoais/exportar")
def exportar_dados_pessoais(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> DadosPessoaisResponse:
    return _exportar_dados_pessoais_e_auditar(cliente_id, usuario, session, "exportar")


@router.delete(
    "/{cliente_id}/dados-pessoais",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_dados_pessoais(
    cliente_id: UUID,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> None:
    uc = obter_excluir_dados(session)
    uc.executar(cliente_id)
    # Auditoria LGPD (#76): erasure (destrutivo, admin-only) registra ator +
    # alvo APOS o efeito. ClienteNaoEncontrado levanta antes, entao 404 nao audita.
    _log.info(
        "dados_pessoais_excluidos_via_admin",
        cliente_id=str(cliente_id),
        ator=ator_de(usuario),
    )


@router.post(
    "/{cliente_id}/consentimento",
    status_code=status.HTTP_201_CREATED,
)
def registrar_consentimento(
    cliente_id: UUID,
    body: ConsentimentoRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> ConsentimentoResponse:
    uc = obter_registrar_consentimento(session)
    dto = RegistrarConsentimentoDTO(tipo=body.tipo)
    result = uc.executar(cliente_id, dto)
    # Auditoria LGPD (#76): base legal (consentimento) registra ator + alvo
    # APOS o efeito, no mesmo padrao do export de dados pessoais.
    _log.info(
        "consentimento_registrado_via_admin",
        cliente_id=str(cliente_id),
        tipo=result.tipo,
        ator=ator_de(usuario),
    )
    return ConsentimentoResponse(**dataclasses.asdict(result))


@router.delete(
    "/{cliente_id}/consentimento",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revogar_consentimento(
    cliente_id: UUID,
    tipo: str = Query(min_length=1, max_length=50),
    usuario: dict[str, object] = Depends(exigir_papel("admin", "atendente")),
    session: Session = Depends(obter_session),
) -> None:
    # Mesma canonicalizacao do ConsentimentoRequest.tipo: garante que o grant
    # registrado em lowercase seja encontrado na revogacao.
    tipo = tipo.strip().lower()
    uc = obter_revogar_consentimento(session)
    uc.executar(cliente_id, tipo)
    # Auditoria LGPD (#76): revogacao registra ator + alvo APOS o efeito.
    _log.info(
        "consentimento_revogado_via_admin",
        cliente_id=str(cliente_id),
        tipo=tipo,
        ator=ator_de(usuario),
    )
