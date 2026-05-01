"""add_ordens_de_servico_indices

Revision ID: 002
Revises: 001
Create Date: 2026-05-01 11:10:00.000000

Indexes que suportam as queries cross-context exists() em ``ordens_de_servico``:

- ``ix_ordens_de_servico_cliente_status``: lookup por (cliente_id, status NOT
  IN <terminais>) — usado por ``existe_os_ativa_para_cliente`` para barrar
  desativacao de cliente com OS aberta.
- ``ix_ordens_de_servico_veiculo_status``: lookup por (veiculo_id, status NOT
  IN <terminais>) — usado por ``existe_ativa_para_veiculo`` E pelo
  ``existe_os_para_veiculo`` (sem filtro de status) — PG usa o prefixo
  ``veiculo_id`` do composto via index-only scan, eliminando a necessidade de
  um indice single-column dedicado.
"""

from __future__ import annotations

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ordens_de_servico_cliente_status",
        "ordens_de_servico",
        ["cliente_id", "status"],
    )
    op.create_index(
        "ix_ordens_de_servico_veiculo_status",
        "ordens_de_servico",
        ["veiculo_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ordens_de_servico_veiculo_status", table_name="ordens_de_servico")
    op.drop_index("ix_ordens_de_servico_cliente_status", table_name="ordens_de_servico")
