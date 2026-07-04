"""Mapeamento imperativo SQLAlchemy do agregado OrdemDeServico.

Contem as tabelas (`ordens_de_servico`, `itens_da_ordem`), a funcao
idempotente `iniciar_mapeamentos()` que registra as mapeamentos
imperativos das entidades, e os event listeners responsaveis por:

- decompor/recompor ``Dinheiro`` em colunas ``preco_unitario_valor``
  e ``preco_unitario_moeda`` na entidade ``ItemDaOrdem``;
- converter o enum ``StatusOrdem`` para sua representacao string no
  banco (coluna ``status``);
- serializar/desserializar o VO ``Orcamento`` como snapshot JSONB
  nativo na coluna ``orcamento_json`` (TD-005: dict cru, sem camada
  manual json.dumps/loads — mesmo padrao de ``outbox.payload``).
  Snapshot e preferido a tabela filha
  porque ``Orcamento`` e um VO imutavel versionado por
  ``versao_schema``: uma modelagem relacional convidaria mutacoes
  parciais e perderia a semantica atomica do snapshot;
- rearmar ``AggregateRoot._eventos_pendentes`` apos a reidratacao via
  ORM, porque SQLAlchemy ignora ``__post_init__`` (a imutabilidade de
  ``id`` e garantida pelo proprio ``Entity.__setattr__``, sem flag).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Uuid,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import registry, relationship

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.orcamento import LinhaOrcamento, Orcamento
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem


def _orcamento_para_dict(orc: Orcamento) -> dict[str, Any]:
    """Serializa um ``Orcamento`` para o dict JSONB persistido.

    Reusado pela coluna ``orcamento_json`` e pelo orcamento aninhado em
    ``escopo_aprovado_json`` (#111). Moeda por linha e no total => round-trip
    sem perda (Copilot PR #62).
    """
    return {
        "total_centavos": orc.total.em_centavos,
        "moeda_total": orc.total.moeda,
        "gerado_em": orc.gerado_em.isoformat(),
        "versao_schema": orc.versao_schema,
        "itens": [
            {
                "descricao": li.descricao,
                "quantidade": li.quantidade,
                "preco_unitario_centavos": li.preco_unitario.em_centavos,
                "subtotal_centavos": li.subtotal.em_centavos,
                "moeda": li.preco_unitario.moeda,
            }
            for li in orc.itens
        ],
    }


def _orcamento_de_dict(data: Any) -> Orcamento:  # noqa: ANN401 -- JSONB e dinamico
    """Reconstroi um ``Orcamento`` do dict JSONB (``data`` e dinamico: JSONB).

    Fallbacks POR CHAVE cobrem as geracoes de snapshot: escritas novas saem
    com ``versao_schema=2`` e moeda por linha e no total; snapshots antigos
    podem nao ter moeda (fallback 'BRL') e/ou ``versao_schema`` (fallback 1).
    Ha snapshots gravados como versao 1 que JA carregam moeda — por isso o
    fallback e por chave, nao por versao. Inverso de ``_orcamento_para_dict``.
    """
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
    return Orcamento(
        itens=linhas,
        _total=Dinheiro(
            valor=Decimal(str(data["total_centavos"])) / 100,
            moeda=moeda_total,
        ),
        _gerado_em=datetime.fromisoformat(data["gerado_em"]),
        versao_schema=data.get("versao_schema", 1),
    )


ordens_de_servico_table = Table(
    "ordens_de_servico",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("cliente_id", Uuid, ForeignKey("clientes.id"), nullable=False),
    Column("veiculo_id", Uuid, ForeignKey("veiculos.id"), nullable=False),
    Column("status", String(50), nullable=False, default=StatusOrdem.RECEBIDA.value),
    # Snapshot do orcamento como JSONB nativo (TD-005). Prod/Postgres usa
    # JSONB; a variante sqlite existe so para que unit-test create_all(sqlite)
    # nao trave (sqlite nao tem o tipo JSONB). Mesmo padrao de outbox.payload.
    # none_as_null=True: orcamento ausente grava SQL NULL (nao o token JSON
    # 'null'), igual ao comportamento Text anterior e consistente com linhas
    # legadas — assim `WHERE orcamento_json IS NULL` casa "sem orcamento".
    Column(
        "orcamento_json",
        JSONB(none_as_null=True).with_variant(JSON(none_as_null=True), "sqlite"),
        nullable=True,
    ),
    # Snapshot do escopo aprovado (#111): {"orcamento": <orcamento|null>,
    # "item_ids": [...]}. Sustenta a reversao da rejeicao do complementar e o
    # guard de finalizar_servico (#122). Nullable: ordens legadas / nao aprovadas.
    Column(
        "escopo_aprovado_json",
        JSONB(none_as_null=True).with_variant(JSON(none_as_null=True), "sqlite"),
        nullable=True,
    ),
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

# Indice na FK ordem_id (migration 008): todo load de OS dispara o selectin
# dos itens com WHERE ordem_id IN (...); a FK nao cria indice sozinha e sem
# ele o Postgres faz seq scan em itens_da_ordem (mesmo racional do TD-025).
Index(
    "ix_itens_da_ordem_ordem_id",
    itens_da_ordem_table.c.ordem_id,
)

# Indice em item_estoque_id (TD-025, migration 005): a query cross-context
# existe_ativa_com_item_estoque filtra por esta coluna ao desativar um item de
# estoque. A FK nao cria indice; sem ele o Postgres faz seq scan.
Index(
    "ix_itens_da_ordem_item_estoque_id",
    itens_da_ordem_table.c.item_estoque_id,
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:
    global _mapeamento_iniciado  # noqa: PLW0603  # init-once flag
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True  # codeql[py/unused-global-variable] -- lida na guarda

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
            "_escopo_aprovado_json": ordens_de_servico_table.c.escopo_aprovado_json,
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
    @event.listens_for(ItemDaOrdem, "refresh")
    def _reconstruir_item(target: ItemDaOrdem, *_args: object) -> None:
        # Decorators empilhados: ``load`` (target, context) e ``refresh``
        # (target, context, attrs) tem aridades diferentes -> ``*_args`` absorve
        # a diferenca. O ``refresh`` e necessario porque populate_existing=True
        # (repositorio, ramo com_lock) e session.refresh disparam
        # ``refresh``, nao ``load``: sem ele o VO Dinheiro ficaria stale apos a
        # releitura sob lock (#117).
        # _preco_valor / _preco_moeda sao injetados em runtime pelo
        # map_imperatively acima e invisiveis ao mypy estatico.
        valor = target._preco_valor  # type: ignore[attr-defined]  # imperative-mapped attr
        moeda = target._preco_moeda  # type: ignore[attr-defined]  # imperative-mapped attr
        object.__setattr__(
            target, "_preco_unitario", Dinheiro(valor=valor, moeda=moeda)
        )

    @event.listens_for(ItemDaOrdem, "before_insert")
    @event.listens_for(ItemDaOrdem, "before_update")
    def _decompor_preco_item(
        _mapper: object, _connection: object, target: ItemDaOrdem
    ) -> None:
        preco = target.preco_unitario
        target._preco_valor = preco.valor
        target._preco_moeda = preco.moeda

    @event.listens_for(OrdemDeServico, "load")
    @event.listens_for(OrdemDeServico, "refresh")
    def _reconstruir_os(target: OrdemDeServico, *_args: object) -> None:
        # Decorators empilhados load+refresh (``*_args`` absorve o ``attrs`` do
        # refresh). O ``refresh`` e indispensavel: a releitura sob FOR UPDATE
        # com populate_existing=True (#117) e session.refresh disparam
        # ``refresh``, nao ``load`` — sem ele o status/orcamento reconstruidos
        # ficariam stale apos o lock, derrotando a serializacao de #82.
        # _status_valor / _orcamento_json sao injetados em runtime pelo
        # map_imperatively acima.
        status_str = target._status_valor  # type: ignore[attr-defined]  # imperative-mapped attr
        object.__setattr__(target, "_status", StatusOrdem(status_str))
        # A coluna e JSONB nativo (TD-005): o valor ja chega como dict
        # (adapter jsonb do psycopg2 no Postgres; tipo JSON do SQLAlchemy no
        # sqlite de teste). Sem json.loads — a camada manual foi removida.
        data = target._orcamento_json  # type: ignore[attr-defined]  # imperative-mapped attr
        object.__setattr__(
            target, "_orcamento", _orcamento_de_dict(data) if data else None
        )
        # Escopo aprovado (#111): {"orcamento": <orcamento>, "item_ids": [...]}.
        # Persistido SOMENTE quando ha snapshot (_orcamento_aprovado non-None),
        # entao "orcamento" nunca e null aqui e "item_ids" sempre o acompanha
        # (ver _decompor_os) — sem o ramo assimetrico orcamento=null+ids.
        escopo = target._escopo_aprovado_json  # type: ignore[attr-defined]  # imperative-mapped attr
        if escopo:
            object.__setattr__(
                target, "_orcamento_aprovado", _orcamento_de_dict(escopo["orcamento"])
            )
            object.__setattr__(
                target,
                "_itens_aprovados_ids",
                frozenset(UUID(s) for s in escopo["item_ids"]),
            )
        else:
            object.__setattr__(target, "_orcamento_aprovado", None)
            object.__setattr__(target, "_itens_aprovados_ids", frozenset())
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
        # Dict cru para a coluna JSONB (TD-005); psycopg2 + SQLAlchemy adaptam
        # para jsonb. Sem json.dumps — mesmo padrao de outbox.payload.
        target._orcamento_json = _orcamento_para_dict(orc) if orc is not None else None
        # Escopo aprovado (#111): orcamento aprovado + ids dos itens cobertos.
        # Condicionado a _orcamento_aprovado (sentinela unica de "tem snapshot"):
        # None quando nunca houve aprovacao (ordem legada / pre-orcamento).
        # INVARIANTE: item_ids sempre acompanha um orcamento non-null (evita o
        # ramo orcamento=null+ids no load).
        orc_aprovado = target._orcamento_aprovado
        if orc_aprovado is not None:
            target._escopo_aprovado_json = {
                "orcamento": _orcamento_para_dict(orc_aprovado),
                "item_ids": sorted(
                    str(item_id) for item_id in target._itens_aprovados_ids
                ),
            }
        else:
            target._escopo_aprovado_json = None
