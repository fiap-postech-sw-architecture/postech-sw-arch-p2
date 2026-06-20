"""Dataclasses tipadas que espelham os corpos de resposta da API.

Os modelos aqui sao pura stdlib (``@dataclass(frozen=True, slots=True)``) e NAO
importam de ``src/``. O harness mantem-se desacoplado dos internals da aplicacao
e o formato de wire fica explicito:

- Catalogo (``preco``) e Estoque (``preco_unitario``) usam ``Decimal`` como
  string no JSON (ex: ``"89.90"``).
- OrdemDeServico usa centavos como ``int`` (ex: ``8990``).

Cada classe expoe um ``_parse(payload)`` classmethod que converte ids para UUID,
timestamps para datetime e precos para Decimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> TokenResponse:
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]),
            token_type=str(payload.get("token_type", "bearer")),
        )


@dataclass(frozen=True, slots=True)
class UsuarioResponse:
    id: UUID
    email: str
    papel: str

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> UsuarioResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            email=str(payload["email"]),
            papel=str(payload["papel"]),
        )


@dataclass(frozen=True, slots=True)
class VeiculoResponse:
    id: UUID
    placa: str
    marca: str
    modelo: str
    ano: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> VeiculoResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            placa=str(payload["placa"]),
            marca=str(payload["marca"]),
            modelo=str(payload["modelo"]),
            ano=int(payload["ano"]),
        )


@dataclass(frozen=True, slots=True)
class ClienteResponse:
    id: UUID
    nome: str
    documento_formatado: str
    documento_mascarado: str
    tipo_documento: str
    contato: str
    ativo: bool
    veiculos: list[VeiculoResponse] = field(default_factory=list)

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ClienteResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            nome=str(payload["nome"]),
            documento_formatado=str(payload["documento_formatado"]),
            documento_mascarado=str(payload["documento_mascarado"]),
            tipo_documento=str(payload["tipo_documento"]),
            contato=str(payload["contato"]),
            ativo=bool(payload["ativo"]),
            veiculos=[VeiculoResponse._parse(v) for v in payload.get("veiculos", [])],
        )


@dataclass(frozen=True, slots=True)
class ClienteResumoResponse:
    id: UUID
    nome: str
    documento_mascarado: str
    tipo_documento: str
    contato: str
    ativo: bool

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ClienteResumoResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            nome=str(payload["nome"]),
            documento_mascarado=str(payload["documento_mascarado"]),
            tipo_documento=str(payload["tipo_documento"]),
            contato=str(payload["contato"]),
            ativo=bool(payload["ativo"]),
        )


@dataclass(frozen=True, slots=True)
class ClienteListaResponse:
    items: list[ClienteResumoResponse]
    total: int
    offset: int
    limit: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ClienteListaResponse:
        return cls(
            items=[ClienteResumoResponse._parse(i) for i in payload.get("items", [])],
            total=int(payload["total"]),
            offset=int(payload["offset"]),
            limit=int(payload["limit"]),
        )


@dataclass(frozen=True, slots=True)
class DadosPessoaisResponse:
    """LGPD: exportacao de dados pessoais do cliente."""

    id: UUID
    nome: str
    documento_formatado: str
    tipo_documento: str
    contato: str
    veiculos: list[dict[str, Any]]
    ativo: bool

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> DadosPessoaisResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            nome=str(payload["nome"]),
            documento_formatado=str(payload["documento_formatado"]),
            tipo_documento=str(payload["tipo_documento"]),
            contato=str(payload["contato"]),
            veiculos=list(payload.get("veiculos", [])),
            ativo=bool(payload["ativo"]),
        )


@dataclass(frozen=True, slots=True)
class ConsentimentoResponse:
    id: UUID
    cliente_id: UUID
    tipo: str
    concedido_em: str
    revogado_em: str | None
    ativo: bool

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ConsentimentoResponse:
        revogado = payload.get("revogado_em")
        return cls(
            id=_as_uuid(payload["id"]),
            cliente_id=_as_uuid(payload["cliente_id"]),
            tipo=str(payload["tipo"]),
            concedido_em=str(payload["concedido_em"]),
            revogado_em=None if revogado is None else str(revogado),
            ativo=bool(payload["ativo"]),
        )


@dataclass(frozen=True, slots=True)
class ServicoResponse:
    id: UUID
    nome: str
    descricao: str
    preco: Decimal
    moeda: str
    ativo: bool

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ServicoResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            nome=str(payload["nome"]),
            descricao=str(payload["descricao"]),
            preco=_as_decimal(payload["preco"]),
            moeda=str(payload["moeda"]),
            ativo=bool(payload["ativo"]),
        )


@dataclass(frozen=True, slots=True)
class ServicoListaResponse:
    items: list[ServicoResponse]
    total: int
    offset: int
    limit: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ServicoListaResponse:
        return cls(
            items=[ServicoResponse._parse(i) for i in payload.get("items", [])],
            total=int(payload["total"]),
            offset=int(payload["offset"]),
            limit=int(payload["limit"]),
        )


@dataclass(frozen=True, slots=True)
class ItemEstoqueResponse:
    id: UUID
    nome: str
    descricao: str
    quantidade: int
    preco_unitario: Decimal
    moeda: str
    ativo: bool

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ItemEstoqueResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            nome=str(payload["nome"]),
            descricao=str(payload["descricao"]),
            quantidade=int(payload["quantidade"]),
            preco_unitario=_as_decimal(payload["preco_unitario"]),
            moeda=str(payload["moeda"]),
            ativo=bool(payload["ativo"]),
        )


@dataclass(frozen=True, slots=True)
class ItemEstoqueListaResponse:
    items: list[ItemEstoqueResponse]
    total: int
    offset: int
    limit: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ItemEstoqueListaResponse:
        return cls(
            items=[ItemEstoqueResponse._parse(i) for i in payload.get("items", [])],
            total=int(payload["total"]),
            offset=int(payload["offset"]),
            limit=int(payload["limit"]),
        )


@dataclass(frozen=True, slots=True)
class ItemDaOrdemResponse:
    id: UUID
    servico_catalogo_id: UUID
    item_estoque_id: UUID | None
    descricao: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> ItemDaOrdemResponse:
        item_est = payload.get("item_estoque_id")
        return cls(
            id=_as_uuid(payload["id"]),
            servico_catalogo_id=_as_uuid(payload["servico_catalogo_id"]),
            item_estoque_id=None if item_est is None else _as_uuid(item_est),
            descricao=str(payload["descricao"]),
            quantidade=int(payload["quantidade"]),
            preco_unitario_centavos=int(payload["preco_unitario_centavos"]),
            subtotal_centavos=int(payload["subtotal_centavos"]),
        )


@dataclass(frozen=True, slots=True)
class LinhaOrcamentoResponse:
    descricao: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> LinhaOrcamentoResponse:
        return cls(
            descricao=str(payload["descricao"]),
            quantidade=int(payload["quantidade"]),
            preco_unitario_centavos=int(payload["preco_unitario_centavos"]),
            subtotal_centavos=int(payload["subtotal_centavos"]),
        )


@dataclass(frozen=True, slots=True)
class OrcamentoResponse:
    total_centavos: int
    gerado_em: datetime
    itens: list[LinhaOrcamentoResponse]

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> OrcamentoResponse:
        return cls(
            total_centavos=int(payload["total_centavos"]),
            gerado_em=_as_datetime(payload["gerado_em"]),
            itens=[LinhaOrcamentoResponse._parse(i) for i in payload.get("itens", [])],
        )


@dataclass(frozen=True, slots=True)
class OrdemDeServicoResponse:
    id: UUID
    cliente_id: UUID
    veiculo_id: UUID
    status: str
    itens: list[ItemDaOrdemResponse]
    orcamento: OrcamentoResponse | None
    criado_em: datetime
    atualizado_em: datetime
    # RF-021: rotulo legivel computado pela API (challenge labels). Default ""
    # mantem o parse tolerante a payloads de fase-1 (sem o campo).
    situacao: str = ""

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> OrdemDeServicoResponse:
        orcamento_raw = payload.get("orcamento")
        return cls(
            id=_as_uuid(payload["id"]),
            cliente_id=_as_uuid(payload["cliente_id"]),
            veiculo_id=_as_uuid(payload["veiculo_id"]),
            status=str(payload["status"]),
            itens=[ItemDaOrdemResponse._parse(i) for i in payload.get("itens", [])],
            orcamento=(
                None
                if orcamento_raw is None
                else OrcamentoResponse._parse(orcamento_raw)
            ),
            criado_em=_as_datetime(payload["criado_em"]),
            atualizado_em=_as_datetime(payload["atualizado_em"]),
            situacao=str(payload.get("situacao", "")),
        )


@dataclass(frozen=True, slots=True)
class OrdemResumoResponse:
    id: UUID
    cliente_id: UUID
    veiculo_id: UUID
    status: str
    criado_em: datetime
    # RF-021: rotulo legivel computado pela API; default "" tolera fase-1.
    situacao: str = ""

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> OrdemResumoResponse:
        return cls(
            id=_as_uuid(payload["id"]),
            cliente_id=_as_uuid(payload["cliente_id"]),
            veiculo_id=_as_uuid(payload["veiculo_id"]),
            status=str(payload["status"]),
            criado_em=_as_datetime(payload["criado_em"]),
            situacao=str(payload.get("situacao", "")),
        )


@dataclass(frozen=True, slots=True)
class OrdemListaResponse:
    items: list[OrdemResumoResponse]
    total: int
    offset: int
    limit: int

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> OrdemListaResponse:
        return cls(
            items=[OrdemResumoResponse._parse(i) for i in payload.get("items", [])],
            total=int(payload["total"]),
            offset=int(payload["offset"]),
            limit=int(payload["limit"]),
        )


@dataclass(frozen=True, slots=True)
class AcompanhamentoResponse:
    status: str
    criado_em: datetime
    atualizado_em: datetime
    # RF-021: rotulo legivel exposto tambem na consulta publica; default ""
    # tolera payloads de fase-1 (sem o campo).
    situacao: str = ""

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> AcompanhamentoResponse:
        return cls(
            status=str(payload["status"]),
            criado_em=_as_datetime(payload["criado_em"]),
            atualizado_em=_as_datetime(payload["atualizado_em"]),
            situacao=str(payload.get("situacao", "")),
        )


@dataclass(frozen=True, slots=True)
class MetricasResponse:
    total: int
    por_status: dict[str, int]
    tempo_medio_execucao_minutos: float | None

    @classmethod
    def _parse(cls, payload: dict[str, Any]) -> MetricasResponse:
        tempo = payload.get("tempo_medio_execucao_minutos")
        return cls(
            total=int(payload["total"]),
            por_status={
                str(k): int(v) for k, v in payload.get("por_status", {}).items()
            },
            tempo_medio_execucao_minutos=None if tempo is None else float(tempo),
        )
