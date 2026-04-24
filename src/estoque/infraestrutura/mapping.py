from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    event,
)
from sqlalchemy.orm import registry

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata
from src.estoque.dominio.item_estoque import ItemEstoque

itens_estoque_table = Table(
    "itens_estoque",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("nome", String(255), nullable=False),
    Column("descricao", Text, nullable=False),
    Column("quantidade", Integer, nullable=False, default=0),
    Column("preco_unitario_valor", Numeric(10, 2), nullable=False),
    Column("preco_unitario_moeda", String(3), nullable=False, default="BRL"),
    Column("ativo", Boolean, nullable=False, default=True),
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:
    global _mapeamento_iniciado
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True

    mapper_registry = registry()

    # Dinheiro (preco_unitario) e decomposto em dois campos escalares
    # ``_preco_valor`` / ``_preco_moeda`` para persistencia; os listeners
    # abaixo reconstroem o VO a partir deles.
    mapper_registry.map_imperatively(
        ItemEstoque,
        itens_estoque_table,
        properties={
            "id": itens_estoque_table.c.id,
            "_nome": itens_estoque_table.c.nome,
            "_descricao": itens_estoque_table.c.descricao,
            "_quantidade": itens_estoque_table.c.quantidade,
            "_preco_valor": itens_estoque_table.c.preco_unitario_valor,
            "_preco_moeda": itens_estoque_table.c.preco_unitario_moeda,
            "_ativo": itens_estoque_table.c.ativo,
        },
    )

    @event.listens_for(ItemEstoque, "load")
    def _reconstruir_preco(target: ItemEstoque, _context: object) -> None:
        valor = target._preco_valor  # type: ignore[attr-defined]
        moeda = target._preco_moeda  # type: ignore[attr-defined]
        object.__setattr__(
            target, "_preco_unitario", Dinheiro(valor=valor, moeda=moeda)
        )
        # SQLAlchemy nao chama __post_init__ ao reidratar, entao o guard
        # de Entity.__setattr__ precisa ser ativado aqui para preservar
        # a imutabilidade de id em instancias carregadas.
        object.__setattr__(target, "_id_atribuido", True)
        # AggregateRoot._eventos_pendentes tem init=False com default_factory,
        # entao o mapper nao o inicializa na reidratacao. Sem isso,
        # reservar()/liberar() crasham com AttributeError na primeira chamada
        # apos load() (ver src/cliente_veiculo/infraestrutura/mapping.py:145
        # para o mesmo padrao em Cliente).
        object.__setattr__(target, "_eventos_pendentes", [])

    @event.listens_for(ItemEstoque, "before_insert")
    @event.listens_for(ItemEstoque, "before_update")
    def _decompor_preco(
        _mapper: object, _connection: object, target: ItemEstoque
    ) -> None:
        preco = target._preco_unitario
        target._preco_valor = preco.valor
        target._preco_moeda = preco.moeda
