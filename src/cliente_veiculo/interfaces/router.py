from __future__ import annotations

import dataclasses
from typing import Annotated
from uuid import UUID  # noqa: TC003

import structlog
from fastapi import APIRouter, Depends, Query, status

# Runtime import (nao TYPE_CHECKING): com `from __future__ import annotations`,
# o FastAPI avalia a annotation `Annotated[Session, Depends(...)]` em runtime;
# sem o nome no modulo, a resolucao da annotation falha no startup
# (PydanticUserError: not fully defined) — verificado empiricamente.
from sqlalchemy.orm import Session  # noqa: TC002

from src.autenticacao.dominio.papel import Papel
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

router = APIRouter(prefix="/api/v1/clientes", tags=["clientes"])
_log = structlog.get_logger(__name__)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um cliente (CPF ou CNPJ)",
)
def criar_cliente(
    body: CriarClienteRequest,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> ClienteResponse:
    """Cria um cliente com documento unico (CPF/CNPJ); 409 se ja cadastrado."""
    uc = obter_criar_cliente(session)
    dto = CriarClienteDTO(
        nome=body.nome,
        documento=body.documento,
        tipo_documento=body.tipo_documento,
        contato=body.contato,
    )
    result = uc.executar(dto)
    return ClienteResponse(**dataclasses.asdict(result))


@router.get("/", summary="Lista clientes paginados")
def listar_clientes(
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ClienteListaResponse:
    """Retorna os clientes paginados (offset/limit) com o total; documento mascarado."""
    uc = obter_listar_clientes(session)
    items = uc.executar(offset=offset, limit=limit)
    total = uc.contar()
    return ClienteListaResponse(
        items=[ClienteResumoResponse(**dataclasses.asdict(item)) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{cliente_id}", summary="Consulta um cliente por id")
def obter_cliente(
    cliente_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> ClienteResponse:
    """Busca um cliente pelo id, com seus veiculos; 404 se nao existir."""
    uc = obter_obter_cliente(session)
    result = uc.executar(cliente_id)
    return ClienteResponse(**dataclasses.asdict(result))


@router.put("/{cliente_id}", summary="Atualiza nome e contato de um cliente")
def atualizar_cliente(
    cliente_id: UUID,
    body: AtualizarClienteRequest,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> ClienteResponse:
    """Atualiza nome/contato do cliente; 404 se ausente, 409 se inativo/anonimizado."""
    uc = obter_atualizar_cliente(session)
    dto = AtualizarClienteDTO(nome=body.nome, contato=body.contato)
    result = uc.executar(cliente_id, dto)
    return ClienteResponse(**dataclasses.asdict(result))


@router.delete(
    "/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativa (soft-delete) um cliente sem OS ativa",
)
def desativar_cliente(
    cliente_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> None:
    """Desativa um cliente (terminal); 404 se ausente, 409 se possuir OS ativa."""
    uc = obter_desativar_cliente(session)
    uc.executar(cliente_id)


@router.post(
    "/{cliente_id}/veiculos",
    status_code=status.HTTP_201_CREATED,
    summary="Adiciona um veiculo a um cliente",
)
def adicionar_veiculo(
    cliente_id: UUID,
    body: AdicionarVeiculoRequest,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> VeiculoResponse:
    """Anexa um veiculo (placa unica global); 409 se placa em uso ou cliente inativo."""
    uc = obter_adicionar_veiculo(session)
    dto = AdicionarVeiculoDTO(
        placa=body.placa,
        marca=body.marca,
        modelo=body.modelo,
        ano=body.ano,
    )
    result = uc.executar(cliente_id, dto)
    return VeiculoResponse(**dataclasses.asdict(result))


@router.get("/{cliente_id}/veiculos", summary="Lista os veiculos de um cliente")
def listar_veiculos(
    cliente_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> list[VeiculoResponse]:
    """Retorna todos os veiculos do cliente; 404 se o cliente nao existir."""
    uc = obter_listar_veiculos(session)
    items = uc.executar(cliente_id)
    return [VeiculoResponse(**dataclasses.asdict(v)) for v in items]


@router.delete(
    "/{cliente_id}/veiculos/{veiculo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove um veiculo de um cliente",
)
def remover_veiculo(
    cliente_id: UUID,
    veiculo_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> None:
    """Remove um veiculo do cliente; 404 se ausente, 409 se houver OS vinculada."""
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


@router.get(
    "/{cliente_id}/dados-pessoais",
    summary="Consulta os dados pessoais de um cliente (LGPD acesso)",
)
def obter_dados_pessoais(
    cliente_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> DadosPessoaisResponse:
    """Retorna os dados pessoais do cliente (LGPD acesso), auditando a consulta."""
    return _exportar_dados_pessoais_e_auditar(cliente_id, usuario, session, "obter")


@router.get(
    "/{cliente_id}/dados-pessoais/exportar",
    summary="Exporta os dados pessoais de um cliente (LGPD portabilidade)",
)
def exportar_dados_pessoais(
    cliente_id: UUID,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> DadosPessoaisResponse:
    """Exporta os dados pessoais do cliente (LGPD portabilidade), auditando o acesso."""
    return _exportar_dados_pessoais_e_auditar(cliente_id, usuario, session, "exportar")


@router.delete(
    "/{cliente_id}/dados-pessoais",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Anonimiza os dados de um cliente (LGPD erasure)",
)
def excluir_dados_pessoais(
    cliente_id: UUID,
    usuario: Annotated[dict[str, object], Depends(exigir_papel(Papel.ADMIN))],
    session: Annotated[Session, Depends(obter_session)],
) -> None:
    """Anonimiza os dados do cliente (LGPD erasure); 409 se houver OS ativa."""
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
    summary="Registra um consentimento LGPD do cliente",
)
def registrar_consentimento(
    cliente_id: UUID,
    body: ConsentimentoRequest,
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> ConsentimentoResponse:
    """Registra a base legal de consentimento por tipo; 409 se ja houver ativo."""
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
    summary="Revoga um consentimento LGPD do cliente",
)
def revogar_consentimento(
    cliente_id: UUID,
    tipo: Annotated[str, Query(min_length=1, max_length=50)],
    usuario: Annotated[
        dict[str, object], Depends(exigir_papel(Papel.ADMIN, Papel.ATENDENTE))
    ],
    session: Annotated[Session, Depends(obter_session)],
) -> None:
    """Revoga o consentimento do tipo informado; 404 se nao houver consentimento."""
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
