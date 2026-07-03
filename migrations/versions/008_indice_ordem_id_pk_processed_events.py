"""indice_ordem_id_e_pk_processed_events

Revision ID: 008
Revises: 007
Create Date: 2026-07-03 00:00:00.000000

Dois acertos de fechamento da revisao pos-entrega:

1. Indice B-tree em ``itens_da_ordem.ordem_id``: todo load de OS dispara o
   ``selectin`` dos itens com ``WHERE ordem_id IN (...)``; a FK nao cria
   indice sozinha e sem ele o Postgres faz seq scan em ``itens_da_ordem``
   (mesmo racional do TD-025/migration 005, que indexou ``item_estoque_id``).

2. ``processed_events`` ganha PRIMARY KEY composta ``(outbox_id, handler)``
   no lugar da UNIQUE homonima: tabela sem PK quebra logical replication e
   ferramentas de ops. O ``INSERT ... ON CONFLICT DO NOTHING`` do relay nao
   nomeia arbiter, portanto continua valido com a PK. Reversivel.
"""

from __future__ import annotations

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "ix_itens_da_ordem_ordem_id",
        "itens_da_ordem",
        ["ordem_id"],
    )
    op.drop_constraint(
        "uq_processed_events",
        "processed_events",
        type_="unique",
    )
    op.create_primary_key(
        "pk_processed_events",
        "processed_events",
        ["outbox_id", "handler"],
    )


def downgrade() -> None:
    op.drop_constraint("pk_processed_events", "processed_events", type_="primary")
    op.create_unique_constraint(
        "uq_processed_events",
        "processed_events",
        ["outbox_id", "handler"],
    )
    op.drop_index("ix_itens_da_ordem_ordem_id", table_name="itens_da_ordem")
