"""DTOs da camada de aplicacao do contexto Ordem de Servico.

Contratos imutaveis de entrada (comandos) e saida (projecoes de leitura)
dos casos de uso. Todos sao ``@dataclass(frozen=True, slots=True)`` e
usam tipos primitivos ou outros DTOs — nenhum value object de dominio
(``Dinheiro``, ``StatusOrdem``, etc.) vaza atraves dessas fronteiras.
Valores monetarios sao expostos em centavos para eliminar ambiguidade
de precisao decimal no API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class ServicoDaOrdemDTO:
    """Linha de servico solicitada na abertura da OS (RF-020).

    ``quantidade`` default 1: a maioria dos servicos e contratada uma
    unica vez por OS. A descricao da linha e resolvida pelo caso de uso
    a partir do nome do servico no catalogo.
    """

    servico_catalogo_id: UUID
    quantidade: int = 1


@dataclass(frozen=True, slots=True)
class PecaDaOrdemDTO:
    """Linha de peca solicitada na abertura da OS (RF-020).

    ``servico_catalogo_id`` e obrigatorio porque toda linha de item da
    ordem referencia o servico que consome a peca (invariante de
    ``ItemDaOrdem``). A descricao e resolvida a partir do nome da peca
    no estoque; o preco vem do estoque, nao do servico.
    """

    servico_catalogo_id: UUID
    item_estoque_id: UUID
    quantidade: int


@dataclass(frozen=True, slots=True)
class CriarOrdemDTO:
    """Comando de entrada do caso de uso ``CriarOrdem``.

    ``servicos`` e ``pecas`` sao opcionais (RF-020): vazios reproduzem o
    comportamento da fase 1 (OS aberta sem itens). Tuplas preservam a
    imutabilidade do comando.
    """

    cliente_id: UUID
    veiculo_id: UUID
    servicos: tuple[ServicoDaOrdemDTO, ...] = ()
    pecas: tuple[PecaDaOrdemDTO, ...] = ()


@dataclass(frozen=True, slots=True)
class AdicionarItemDTO:
    """Comando de montagem de uma linha de item (``AdicionarItem`` e RF-020).

    ``item_estoque_id`` e opcional: itens puramente de servico (mao-de-obra)
    nao tem contrapartida no estoque. ``descricao`` ``None`` significa
    "resolver do nome do servico/peca via port" — caminho usado pela
    criacao com itens (RF-020), em que o payload nao carrega descricao
    livre; o endpoint de adicionar item continua exigindo descricao no
    schema HTTP.
    """

    servico_catalogo_id: UUID
    item_estoque_id: UUID | None
    descricao: str | None
    quantidade: int


@dataclass(frozen=True, slots=True)
class CancelarOrdemDTO:
    """Comando de entrada do caso de uso ``CancelarOrdem`` com o motivo obrigatorio."""

    motivo: str


@dataclass(frozen=True, slots=True)
class ItemDaOrdemDTO:
    """Projecao de leitura de um item da ordem com precos em centavos.

    Os campos ``servico_nome`` e ``item_estoque_nome`` ficam ``None``
    quando o caso de uso emite o DTO direto do agregado: o agregado so
    guarda IDs cross-context. A query ``EnriquecerOrdemDeServico``
    resolve os nomes via ``CatalogoPort`` / ``EstoquePort`` antes do DTO
    atravessar a fronteira HTTP.
    """

    id: UUID
    servico_catalogo_id: UUID
    item_estoque_id: UUID | None
    descricao: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int
    servico_nome: str | None = None
    item_estoque_nome: str | None = None


@dataclass(frozen=True, slots=True)
class LinhaOrcamentoDTO:
    """Projecao de uma linha do orcamento congelado com subtotal em centavos."""

    descricao: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int


@dataclass(frozen=True, slots=True)
class OrcamentoDTO:
    """Projecao do orcamento gerado com total, instante de geracao e linhas."""

    total_centavos: int
    gerado_em: datetime
    itens: list[LinhaOrcamentoDTO]


@dataclass(frozen=True, slots=True)
class OrdemDeServicoDTO:
    """Projecao completa da ordem; retorno padrao dos casos de uso de escrita.

    ``cliente_nome`` e ``veiculo_placa`` ficam ``None`` quando o caso
    de uso emite o DTO direto do agregado: ele so guarda IDs cross-context.
    A query ``EnriquecerOrdemDeServico`` resolve os nomes via
    ``ClientePort`` antes do DTO atravessar a fronteira HTTP.
    """

    id: UUID
    cliente_id: UUID
    veiculo_id: UUID
    status: str
    itens: list[ItemDaOrdemDTO]
    orcamento: OrcamentoDTO | None
    criado_em: datetime
    atualizado_em: datetime
    cliente_nome: str | None = None
    veiculo_placa: str | None = None


@dataclass(frozen=True, slots=True)
class OrdemResumoDTO:
    """Projecao enxuta usada em listagens paginadas de ordens.

    ``cliente_nome`` e ``veiculo_placa`` seguem o mesmo contrato do
    DTO completo: ficam ``None`` ate a query de enriquecimento batch
    resolve-los via ``ClientePort`` antes do response HTTP.
    """

    id: UUID
    cliente_id: UUID
    veiculo_id: UUID
    status: str
    criado_em: datetime
    cliente_nome: str | None = None
    veiculo_placa: str | None = None


@dataclass(frozen=True, slots=True)
class AcompanhamentoDTO:
    """Projecao publica de acompanhamento de uma ordem por placa + documento."""

    status: str
    criado_em: datetime
    atualizado_em: datetime


@dataclass(frozen=True, slots=True)
class MetricasDTO:
    """Projecao de metricas agregadas: total, contagem por status e tempo medio."""

    total: int
    por_status: dict[str, int]
    tempo_medio_execucao_minutos: float | None = None
