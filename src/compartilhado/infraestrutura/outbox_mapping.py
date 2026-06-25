"""Tabelas Core da Transactional Outbox (RF-018) + helpers transacionais.

``outbox`` e ``processed_events`` sao tabelas Core (sem agregado de
dominio mapeado): a UoW e o relay escrevem/leem via SQLAlchemy Core na
session/connection da transacao corrente. Registradas no ``metadata``
compartilhado para entrarem no ``create_all`` (testes) e no autogenerate
do Alembic.

``inserir_na_outbox`` faz o INSERT dos registros serializados;
``pg_notify_outbox`` emite ``pg_notify('outbox_novo','')`` — NOTIFY e
transacional, entao a notificacao so chega ao relay quando o COMMIT da
mesma transacao concluir. Ambos no-op em backend nao-Postgres (SQLite de
teste nao tem ``pg_notify``; o INSERT funciona, o NOTIFY e pulado).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.compartilhado.infraestrutura.database import metadata

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.orm import Session

    from src.compartilhado.aplicacao.outbox import OutboxRegistro

CANAL_NOTIFY = "outbox_novo"

outbox_table = Table(
    "outbox",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("agregado_id", Uuid, nullable=False),
    Column("tipo", String(255), nullable=False),
    # Prod/Postgres usa JSONB; a variante sqlite so existe para que
    # unit-test create_all(sqlite) nao trave (a tabela outbox nunca e usada em sqlite).
    Column("payload", JSONB().with_variant(JSON(), "sqlite"), nullable=False),
    Column("status", String(20), nullable=False, default="pendente"),
    Column("tentativas", Integer, nullable=False, default=0),
    Column(
        "proxima_tentativa_em",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    ),
    Column(
        "criado_em",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    ),
    Column("entregue_em", DateTime(timezone=True), nullable=True),
    Column("ultimo_erro", Text, nullable=True),
)

Index(
    "ix_outbox_claim",
    outbox_table.c.status,
    outbox_table.c.proxima_tentativa_em,
)

# Suporta o subquery de head-of-line por agregado da query de claim (F2):
# `NOT EXISTS (... WHERE p.agregado_id = o.agregado_id AND p.id < o.id
#  AND p.status NOT IN ('entregue','dead'))`.
Index(
    "ix_outbox_agregado_ordering",
    outbox_table.c.agregado_id,
    outbox_table.c.id,
    outbox_table.c.status,
)

processed_events_table = Table(
    "processed_events",
    metadata,
    Column("outbox_id", BigInteger, nullable=False),
    Column("handler", String(255), nullable=False),
    Column(
        "processado_em",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    ),
    UniqueConstraint("outbox_id", "handler", name="uq_processed_events"),
)


def inserir_na_outbox(session: Session, registros: Sequence[OutboxRegistro]) -> None:
    """INSERT dos registros na ``outbox`` usando a transacao da session.

    ``payload`` (``dict`` JSON-serializavel produzido por
    ``serializar_integration_event``) e passado cru para a coluna JSONB; o
    driver psycopg2 + SQLAlchemy fazem a adaptacao para ``jsonb``. Nao
    commita — o caller (UoW) controla a fronteira transacional.
    """
    if not registros:
        return
    session.execute(
        outbox_table.insert(),
        [
            {
                "agregado_id": r.agregado_id,
                "tipo": r.tipo,
                "payload": r.payload,
            }
            for r in registros
        ],
    )


def pg_notify_outbox(session: Session) -> None:
    """Emite ``pg_notify('outbox_novo','')`` na transacao corrente (so Postgres).

    NOTIFY e transacional: a mensagem so e entregue aos ``LISTEN``ers
    quando esta transacao comita. No-op em backend nao-Postgres.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    session.execute(text("SELECT pg_notify(:canal, '')"), {"canal": CANAL_NOTIFY})
