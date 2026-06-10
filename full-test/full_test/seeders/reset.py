"""Reset: TRUNCATE CASCADE das tabelas do app em ordem que respeita FK.

Ordem espelha a usada em ``tests/integracao/test_api_e2e.py`` (dependentes
antes de referenciados). Se novas tabelas aparecerem, esta tupla precisa
ser atualizada (convencao documentada no README).
"""

from __future__ import annotations

from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
from src.compartilhado.infraestrutura.database import (
    criar_engine,
    criar_session_factory,
)

_TABELAS = (
    "itens_da_ordem",
    "ordens_de_servico",
    "servicos_oferecidos",
    "itens_estoque",
    "consentimentos",
    "veiculos",
    "clientes",
    "tokens_revogados",
    "usuarios",
)


def resetar(database_url: str) -> None:
    from sqlalchemy import text

    iniciar_todos_mapeamentos()
    engine = criar_engine(database_url)
    try:
        factory = criar_session_factory(engine)
        with factory() as session:
            for tabela in _TABELAS:
                session.execute(
                    text(f"TRUNCATE TABLE {tabela} RESTART IDENTITY CASCADE")
                )
            session.commit()
    finally:
        engine.dispose()
