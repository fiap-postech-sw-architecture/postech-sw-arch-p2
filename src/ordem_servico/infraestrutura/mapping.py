# TODO(PR 10): replace stub with full ordem_servico mapping
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Table, Uuid

from src.compartilhado.infraestrutura.database import metadata

ordens_de_servico_table = Table(
    "ordens_de_servico",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("cliente_id", Uuid, nullable=False),
    Column("veiculo_id", Uuid, nullable=False),
    Column("status", String(30), nullable=False),
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
    Column("item_estoque_id", Uuid, nullable=True),
    Column("quantidade", Integer, nullable=False),
    Column("preco_unitario_valor", Numeric(10, 2), nullable=False),
    Column("preco_unitario_moeda", String(3), nullable=False, default="BRL"),
)
