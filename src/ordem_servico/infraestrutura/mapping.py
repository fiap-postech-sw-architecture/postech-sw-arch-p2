"""Mapeamento imperativo SQLAlchemy do agregado OrdemDeServico.

Contem as tabelas (`ordens_de_servico`, `itens_da_ordem`), a funcao
idempotente `iniciar_mapeamentos()` que registra as mapeamentos
imperativos das entidades, e os event listeners responsaveis por:

- decompor/recompor ``Dinheiro`` em colunas ``preco_unitario_valor``
  e ``preco_unitario_moeda`` na entidade ``ItemDaOrdem``;
- converter o enum ``StatusOrdem`` para sua representacao string no
  banco (coluna ``status``);
- serializar/desserializar o VO ``Orcamento`` como snapshot JSON na
  coluna ``orcamento_json``. Snapshot e preferido a tabela filha
  porque ``Orcamento`` e um VO imutavel versionado por
  ``versao_schema``: uma modelagem relacional convidaria mutacoes
  parciais e perderia a semantica atomica do snapshot;
- reativar invariantes de ``Entity`` (``_id_atribuido``) e
  ``AggregateRoot`` (``_eventos_pendentes``) apos a reidratacao via
  ORM, porque SQLAlchemy ignora ``__post_init__``.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    event,
)
from sqlalchemy.orm import registry, relationship

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.orcamento import LinhaOrcamento, Orcamento
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem

ordens_de_servico_table = Table(
    "ordens_de_servico",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("cliente_id", Uuid, ForeignKey("clientes.id"), nullable=False),
    Column("veiculo_id", Uuid, ForeignKey("veiculos.id"), nullable=False),
    Column("status", String(50), nullable=False, default="recebida"),
    Column("orcamento_json", Text, nullable=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("atualizado_em", DateTime(timezone=True), nullable=False),
)

Index("ix_ordens_de_servico_veiculo_id", ordens_de_servico_table.c.veiculo_id)
Index(
    "ix_ordens_de_servico_cliente_status",
    ordens_de_servico_table.c.cliente_id,
    ordens_de_servico_table.c.status,
)
Index(
    "ix_ordens_de_servico_veiculo_status",
    ordens_de_servico_table.c.veiculo_id,
    ordens_de_servico_table.c.status,
)

itens_da_ordem_table = Table(
    "itens_da_ordem",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "ordem_id",
        Uuid,
        ForeignKey("ordens_de_servico.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("servico_catalogo_id", Uuid, nullable=False),
    Column("item_estoque_id", Uuid, nullable=True),
    Column("descricao", String(255), nullable=False),
    Column("quantidade", Integer, nullable=False),
    Column("preco_unitario_valor", Numeric(10, 2), nullable=False),
    Column("preco_unitario_moeda", String(3), nullable=False, default="BRL"),
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:
    global _mapeamento_iniciado
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True

    mapper_registry = registry()

    mapper_registry.map_imperatively(
        ItemDaOrdem,
        itens_da_ordem_table,
        properties={
            "id": itens_da_ordem_table.c.id,
            "_servico_catalogo_id": itens_da_ordem_table.c.servico_catalogo_id,
            "_item_estoque_id": itens_da_ordem_table.c.item_estoque_id,
            "_descricao": itens_da_ordem_table.c.descricao,
            "_quantidade": itens_da_ordem_table.c.quantidade,
            "_preco_valor": itens_da_ordem_table.c.preco_unitario_valor,
            "_preco_moeda": itens_da_ordem_table.c.preco_unitario_moeda,
        },
    )

    mapper_registry.map_imperatively(
        OrdemDeServico,
        ordens_de_servico_table,
        properties={
            "id": ordens_de_servico_table.c.id,
            "_cliente_id": ordens_de_servico_table.c.cliente_id,
            "_veiculo_id": ordens_de_servico_table.c.veiculo_id,
            "_status_valor": ordens_de_servico_table.c.status,
            "_orcamento_json": ordens_de_servico_table.c.orcamento_json,
            "_criado_em": ordens_de_servico_table.c.criado_em,
            "_atualizado_em": ordens_de_servico_table.c.atualizado_em,
            "_itens": relationship(
                ItemDaOrdem,
                lazy="selectin",
                cascade="all, delete-orphan",
            ),
        },
    )

    @event.listens_for(ItemDaOrdem, "load")
    def _reconstruir_preco_item(target: ItemDaOrdem, _context: object) -> None:
        # _preco_valor / _preco_moeda sao injetados em tempo de execucao
        # pelo map_imperatively acima e invisiveis ao mypy estatico.
        valor = target._preco_valor  # type: ignore[attr-defined]  # imperative-mapped attr
        moeda = target._preco_moeda  # type: ignore[attr-defined]  # imperative-mapped attr
        object.__setattr__(
            target, "_preco_unitario", Dinheiro(valor=valor, moeda=moeda)
        )
        # SQLAlchemy nao invoca __post_init__ na reidratacao; o guard
        # de imutabilidade de Entity.__setattr__ precisa ser ativado
        # aqui para preservar a imutabilidade de id em instancias
        # carregadas (regressao PR #60 aplicada workspace-wide).
        object.__setattr__(target, "_id_atribuido", True)

    @event.listens_for(ItemDaOrdem, "before_insert")
    @event.listens_for(ItemDaOrdem, "before_update")
    def _decompor_preco_item(
        _mapper: object, _connection: object, target: ItemDaOrdem
    ) -> None:
        preco = target.preco_unitario
        target._preco_valor = preco.valor
        target._preco_moeda = preco.moeda

    @event.listens_for(OrdemDeServico, "load")
    def _reconstruir_os(target: OrdemDeServico, _context: object) -> None:
        # _status_valor / _orcamento_json sao injetados em tempo de
        # execucao pelo map_imperatively acima.
        status_str = target._status_valor  # type: ignore[attr-defined]  # imperative-mapped attr
        object.__setattr__(target, "_status", StatusOrdem(status_str))
        json_str = target._orcamento_json  # type: ignore[attr-defined]  # imperative-mapped attr
        if json_str:
            data = json.loads(json_str)
            # Snapshots antigos (versao_schema < 2) nao persistiam a moeda;
            # cair para "BRL" como fallback. Snapshots 2+ incluem "moeda"
            # por linha e um "moeda_total" para o agregado, permitindo
            # evolucao multi-moeda sem perder dados no round-trip.
            moeda_total = data.get("moeda_total", "BRL")
            linhas = tuple(
                LinhaOrcamento(
                    descricao=li["descricao"],
                    quantidade=li["quantidade"],
                    _preco_unitario=Dinheiro(
                        valor=Decimal(str(li["preco_unitario_centavos"])) / 100,
                        moeda=li.get("moeda", "BRL"),
                    ),
                    _subtotal=Dinheiro(
                        valor=Decimal(str(li["subtotal_centavos"])) / 100,
                        moeda=li.get("moeda", "BRL"),
                    ),
                )
                for li in data["itens"]
            )
            object.__setattr__(
                target,
                "_orcamento",
                Orcamento(
                    itens=linhas,
                    _total=Dinheiro(
                        valor=Decimal(str(data["total_centavos"])) / 100,
                        moeda=moeda_total,
                    ),
                    _gerado_em=datetime.fromisoformat(data["gerado_em"]),
                    versao_schema=data.get("versao_schema", 1),
                ),
            )
        else:
            object.__setattr__(target, "_orcamento", None)
        # PR #60 lesson aplicada ao agregado: reativa _id_atribuido para
        # que Entity.__setattr__ bloqueie mutacao de id em ordens
        # carregadas via ORM.
        object.__setattr__(target, "_id_atribuido", True)
        # AggregateRoot._eventos_pendentes e um field com default_factory
        # inicializado pelo __init__ do dataclass; como SQLAlchemy bypass
        # o __init__ ao reidratar, a lista precisa ser re-armada aqui
        # para que _registrar_evento funcione em metodos chamados sobre
        # instancias carregadas.
        object.__setattr__(target, "_eventos_pendentes", [])

    @event.listens_for(OrdemDeServico, "before_insert")
    @event.listens_for(OrdemDeServico, "before_update")
    def _decompor_os(
        _mapper: object, _connection: object, target: OrdemDeServico
    ) -> None:
        target._status_valor = target._status.value
        orc = target._orcamento
        if orc is not None:
            # moeda e persistida por linha e no total para permitir
            # round-trip completo sem perda (Copilot PR #62 finding:
            # reconstruir apenas com "valor" assume BRL implicitamente).
            data = {
                "total_centavos": int(orc.total.valor * 100),
                "moeda_total": orc.total.moeda,
                "gerado_em": orc.gerado_em.isoformat(),
                "versao_schema": orc.versao_schema,
                "itens": [
                    {
                        "descricao": li.descricao,
                        "quantidade": li.quantidade,
                        "preco_unitario_centavos": int(li.preco_unitario.valor * 100),
                        "subtotal_centavos": int(li.subtotal.valor * 100),
                        "moeda": li.preco_unitario.moeda,
                    }
                    for li in orc.itens
                ],
            }
            target._orcamento_json = json.dumps(data)
        else:
            target._orcamento_json = None
