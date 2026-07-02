"""escopo_aprovado_json em ordens_de_servico

Revision ID: 007
Revises: 006
Create Date: 2026-07-02 00:00:00.000000

Adiciona a coluna JSONB ``escopo_aprovado_json`` a ``ordens_de_servico`` (#111):
snapshot do escopo aprovado pelo cliente (orcamento + ids dos itens cobertos).
Sustenta a reversao da rejeicao do orcamento complementar (restaura o orcamento
aprovado e remove os itens nao aprovados, liberando as reservas) e o guard de
``finalizar_servico`` (#122). Nullable: ordens existentes / ainda nao aprovadas
ficam NULL — o dominio trata NULL como "sem snapshot" e preserva o comportamento
antigo. Reversivel (drop da coluna).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "ordens_de_servico",
        sa.Column("escopo_aprovado_json", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ordens_de_servico", "escopo_aprovado_json")
