"""widen_veiculos_placa_para_tombstone

Revision ID: 006
Revises: 005
Create Date: 2026-06-30 00:00:00.000000

Alarga ``veiculos.placa`` de ``String(7)`` para ``String(64)`` (issue #72): a
anonimizacao LGPD (``ClienteRepository.anonimizar_dados``) escreve o tombstone
unico ``ANONIMIZADO:{veiculo_id}`` (~49 chars) que nao cabe em 7. Mantem UNIQUE e
NOT NULL. Reversivel: o downgrade FALHA de forma barulhenta
(``StringDataRightTruncation``) se existir algum tombstone de ~49 chars -- so
reverte um schema sem anonimizacoes (placas reais cabem em 7).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "veiculos",
        "placa",
        existing_type=sa.String(7),
        type_=sa.String(64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "veiculos",
        "placa",
        existing_type=sa.String(64),
        type_=sa.String(7),
        existing_nullable=False,
    )
