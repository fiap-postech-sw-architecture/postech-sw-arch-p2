"""orcamento_json_text_to_jsonb

Revision ID: 004
Revises: 003
Create Date: 2026-06-28 10:00:00.000000

Orcamento Text -> JSONB nativo (TD-005):

A coluna ``ordens_de_servico.orcamento_json`` guardava o snapshot do VO
``Orcamento`` como ``Text`` (string produzida por ``json.dumps``). Esta
migracao converte o tipo para ``jsonb`` nativo do PostgreSQL e o mapping
passa a gravar/ler o ``dict`` cru (sem a camada manual
``json.dumps``/``json.loads``), espelhando o padrao de ``outbox.payload``.

Os valores ``Text`` existentes sao JSON validos (vieram de ``json.dumps``),
entao ``orcamento_json::jsonb`` os parseia in-place; ``NULL`` permanece
``NULL`` (``existing_nullable=True``). Sem indice GIN: nenhuma consulta
filtra por conteudo do orcamento (lido sempre junto da OS) — indexar seria
especulativo (YAGNI).

Janela de rollout: o deploy roda esta migracao ANTES do rollout do codigo
novo (Job ``pytstop-migrate`` dedicado, TD-015/ADR-019), entao o codigo
que grava ``dict`` cru so executa contra a coluna ja convertida para
``jsonb``. A breve janela em que o codigo antigo (``json.dumps`` -> Text)
poderia escrever durante o flip e aceitavel no escopo de demo da fase 2
(nao ha requisito de expand-contract zero-downtime).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "ordens_de_servico",
        "orcamento_json",
        type_=postgresql.JSONB(),
        existing_type=sa.Text(),
        postgresql_using="orcamento_json::jsonb",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "ordens_de_servico",
        "orcamento_json",
        type_=sa.Text(),
        existing_type=postgresql.JSONB(),
        postgresql_using="orcamento_json::text",
        existing_nullable=True,
    )
