"""add_indice_item_estoque_id

Revision ID: 005
Revises: 004
Create Date: 2026-06-30 00:00:00.000000

Indice B-tree em ``itens_da_ordem.item_estoque_id`` (TD-025). A query
``existe_ativa_com_item_estoque`` (``repository.py``) faz JOIN + WHERE por
``item_estoque_id`` ao desativar um item de estoque; sem indice o Postgres faz
seq scan em ``itens_da_ordem`` -- a FK nao cria indice automaticamente e a
migration 002 so indexou ``ordens_de_servico``. Reversivel.
"""

from __future__ import annotations

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_itens_da_ordem_item_estoque_id",
        "itens_da_ordem",
        ["item_estoque_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_itens_da_ordem_item_estoque_id",
        table_name="itens_da_ordem",
    )
