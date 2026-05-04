"""Schemas Pydantic (request/response) do router Ordem de Servico.

Estes schemas sao o contrato HTTP e ficam deliberadamente separados
dos DTOs da camada de aplicacao (``src/ordem_servico/aplicacao/dtos.py``):
os DTOs sao frozen dataclasses consumidos pelos use cases, enquanto
os schemas sao modelos Pydantic que validam payload HTTP e serializam
respostas. O router faz a traducao entre os dois via
``model_validate(dto)`` (leitura usando ``from_attributes=True``) e
construcao explicita de DTOs a partir de campos do ``Request``.

Todas as requests declaram ``extra='forbid'`` para rejeitar payloads
desconhecidos (protecao contra payload smuggling). Campos monetarios
sao expressos em centavos inteiros para evitar ambiguidade decimal no
wire format.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CriarOrdemRequest(BaseModel):
    """Request body do endpoint ``POST /api/v1/ordens-de-servico``."""

    model_config = ConfigDict(extra="forbid")

    cliente_id: UUID = Field(description="Identificador do cliente dono do veiculo.")
    veiculo_id: UUID = Field(description="Identificador do veiculo a ser atendido.")


class AdicionarItemRequest(BaseModel):
    """Request body do endpoint ``POST /api/v1/ordens-de-servico/{id}/itens``."""

    model_config = ConfigDict(extra="forbid")

    servico_catalogo_id: UUID = Field(
        description="Identificador do ServicoOferecido no contexto Catalogo."
    )
    item_estoque_id: UUID | None = Field(
        default=None,
        description="Item de estoque consumido (None se for servico puro).",
    )
    descricao: str = Field(
        min_length=1,
        max_length=255,
        description="Descricao livre do item (visivel ao cliente).",
    )
    quantidade: int = Field(gt=0, description="Quantidade em unidades (> 0).")


class CancelarOrdemRequest(BaseModel):
    """Request body do endpoint ``POST /api/v1/ordens-de-servico/{id}/cancelamento``."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(
        min_length=1,
        max_length=500,
        description="Motivo livre do cancelamento (obrigatorio, <= 500 chars).",
    )


class ItemDaOrdemResponse(BaseModel):
    """Projecao de leitura de um item da ordem (centavos para moeda).

    Inclui ``servico_nome`` e ``item_estoque_nome`` resolvidos no router via
    lookup direto da session — assim a UI exibe ``Troca de oleo`` /
    ``Filtro de oleo`` em vez de UUIDs sem precisar de chamadas extras pro
    catalogo/estoque. Ambos sao nullable: pos anonimizacao/exclusao cascata
    do servico/item, a OS continua valida mas o nome perdido vira ``None``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    servico_catalogo_id: UUID
    servico_nome: str | None = Field(
        default=None,
        description="Nome do servico no catalogo, resolvido server-side.",
    )
    item_estoque_id: UUID | None
    item_estoque_nome: str | None = Field(
        default=None,
        description=(
            "Nome do item de estoque, resolvido server-side. None quando a "
            "linha e mao de obra (sem item_estoque_id)."
        ),
    )
    descricao: str
    quantidade: int
    preco_unitario_centavos: int = Field(description="Preco unitario em centavos.")
    subtotal_centavos: int = Field(description="Subtotal do item em centavos.")


class LinhaOrcamentoResponse(BaseModel):
    """Projecao de uma linha do orcamento congelado."""

    model_config = ConfigDict(from_attributes=True)

    descricao: str
    quantidade: int
    preco_unitario_centavos: int = Field(description="Preco unitario em centavos.")
    subtotal_centavos: int = Field(description="Subtotal da linha em centavos.")


class OrcamentoResponse(BaseModel):
    """Projecao do orcamento (total + instante + linhas)."""

    model_config = ConfigDict(from_attributes=True)

    total_centavos: int = Field(description="Soma dos subtotais em centavos.")
    gerado_em: datetime
    itens: list[LinhaOrcamentoResponse]


class OrdemDeServicoResponse(BaseModel):
    """Projecao completa de uma ordem (retorno padrao dos endpoints de mutacao).

    ``cliente_nome`` e ``veiculo_placa`` sao resolvidos server-side via
    ``EnriquecerOrdemDeServico`` e podem ficar ``None`` se o cliente
    ou o veiculo tiverem sido removidos depois da OS ser criada.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cliente_id: UUID
    cliente_nome: str | None = Field(
        default=None,
        description="Nome do cliente, resolvido server-side. None se o cliente "
        "tiver sido removido apos a OS ser criada.",
    )
    veiculo_id: UUID
    veiculo_placa: str | None = Field(
        default=None,
        description="Placa do veiculo, resolvida server-side. None se o "
        "veiculo tiver sido removido apos a OS ser criada.",
    )
    status: str = Field(
        description="StatusOrdem.value (ex: 'recebida', 'em_diagnostico')."
    )
    itens: list[ItemDaOrdemResponse]
    orcamento: OrcamentoResponse | None
    criado_em: datetime
    atualizado_em: datetime


class OrdemResumoResponse(BaseModel):
    """Projecao enxuta para listagens paginadas."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cliente_id: UUID
    cliente_nome: str | None = Field(
        default=None,
        description="Nome do cliente, resolvido server-side em batch.",
    )
    veiculo_id: UUID
    veiculo_placa: str | None = Field(
        default=None,
        description="Placa do veiculo, resolvida server-side em batch.",
    )
    status: str
    criado_em: datetime


class OrdemListaResponse(BaseModel):
    """Pagina de ``OrdemResumoResponse`` + metadata de paginacao."""

    items: list[OrdemResumoResponse]
    total: int = Field(description="Total de ordens persistidas no sistema.")
    offset: int = Field(description="Offset da pagina atual (>= 0).")
    limit: int = Field(description="Tamanho da pagina atual (1..100).")


class AcompanhamentoResponse(BaseModel):
    """Projecao publica de acompanhamento (endpoint rate-limited).

    Contem apenas status + timestamps; nao expoe cliente_id, veiculo_id,
    itens ou orcamento por razoes de privacidade (LGPD).
    """

    model_config = ConfigDict(from_attributes=True)

    status: str
    criado_em: datetime
    atualizado_em: datetime


class MetricasResponse(BaseModel):
    """Projecao agregada de metricas de ordens."""

    model_config = ConfigDict(from_attributes=True)

    total: int = Field(description="Total de ordens persistidas.")
    por_status: dict[str, int] = Field(
        description="Contagem de ordens por status (chaves sao StatusOrdem.value)."
    )
    tempo_medio_execucao_minutos: float | None = Field(
        default=None,
        description=(
            "Tempo medio em minutos entre criacao e atualizacao de ordens "
            "finalizadas/entregues. None se nao houver ordens finalizadas."
        ),
    )
