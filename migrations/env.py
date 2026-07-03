from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Carrega o metadata compartilhado e registra os mapeamentos imperativos de
# cada bounded context. Sem isso, ``target_metadata`` fica vazio e o Alembic
# autogenerate nao detecta as tabelas, levando a migrations stub.
from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
from src.compartilhado.infraestrutura.database import metadata

iniciar_todos_mapeamentos()

target_metadata = metadata


def get_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url", ""),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
