"""create_outbox_and_processed_events

Revision ID: 003
Revises: 002
Create Date: 2026-06-24 09:00:00.000000

Transactional Outbox (RF-018 / TD-008):

- ``outbox``: fila duravel de integration events; ``id`` bigserial da a
  ordem global de entrega. Indice ``ix_outbox_claim`` (status,
  proxima_tentativa_em) suporta a query de claim do relay
  (``status='pendente' AND proxima_tentativa_em <= now()``); indice
  ``ix_outbox_agregado_ordering`` (agregado_id, id, status) suporta o
  subquery de head-of-line por agregado (``NOT EXISTS`` de predecessora
  nao-terminal do mesmo agregado).
- ``processed_events``: idempotencia por ``(outbox_id, handler)`` — o
  relay checa antes de invocar o handler e grava apos sucesso.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("agregado_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pendente",
        ),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "proxima_tentativa_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entregue_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_claim",
        "outbox",
        ["status", "proxima_tentativa_em"],
    )
    op.create_index(
        "ix_outbox_agregado_ordering",
        "outbox",
        ["agregado_id", "id", "status"],
    )
    op.create_table(
        "processed_events",
        sa.Column("outbox_id", sa.BigInteger(), nullable=False),
        sa.Column("handler", sa.String(length=255), nullable=False),
        sa.Column(
            "processado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("outbox_id", "handler", name="uq_processed_events"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_index("ix_outbox_agregado_ordering", table_name="outbox")
    op.drop_index("ix_outbox_claim", table_name="outbox")
    op.drop_table("outbox")
