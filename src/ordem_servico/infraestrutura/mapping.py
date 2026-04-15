# TODO(PR 10): replace stub with full ordem_servico mapping
from __future__ import annotations

from sqlalchemy import Column, String, Table, Uuid

from src.compartilhado.infraestrutura.database import metadata

ordens_de_servico_table = Table(
    "ordens_de_servico",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("cliente_id", Uuid, nullable=False),
    Column("veiculo_id", Uuid, nullable=False),
    Column("status", String(30), nullable=False),
)
