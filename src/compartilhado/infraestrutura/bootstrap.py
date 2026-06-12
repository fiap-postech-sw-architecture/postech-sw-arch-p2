"""Bootstrap compartilhado dos imperative mappings de todos os bounded contexts.

Ponto de verdade unico para a ordem de registro das tabelas no metadata
SQLAlchemy. Projetado para ser chamado por: lifespan do FastAPI, env.py do
Alembic, conftest de integracao e scripts operacionais (ex.: seed_admin).

ORDERING RATIONALE: contexts a montante vem primeiro porque ``ordem_servico``
referencia ``cliente_veiculo``/``estoque``/``catalogo_servicos`` via FK. Se OS
registrar antes, o metadata fica com referencias a tabelas ainda ausentes.
``autenticacao`` vai por ultimo porque nao tem relacionamento cross-context.

Ao adicionar um novo bounded context, posicione seu ``iniciar_*()`` ANTES dos
contexts que dependem dele.
"""

from __future__ import annotations

_mapeamentos_registrados = False


def iniciar_todos_mapeamentos() -> None:
    """Registra todos os imperative mappings dos bounded contexts.

    Idempotente: chamadas subsequentes sao no-op. Seguro para warm restarts
    do uvicorn, re-entrada em testes e invocacao multipla em scripts.
    """
    global _mapeamentos_registrados  # noqa: PLW0603  # init-once flag
    if _mapeamentos_registrados:
        return

    from src.autenticacao.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_auth,
    )
    from src.catalogo_servicos.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_catalogo,
    )
    from src.cliente_veiculo.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_cliente,
    )
    from src.estoque.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_estoque,
    )
    from src.ordem_servico.infraestrutura.mapping import (
        iniciar_mapeamentos as iniciar_os,
    )

    iniciar_cliente()
    iniciar_catalogo()
    iniciar_estoque()
    iniciar_os()
    iniciar_auth()

    _mapeamentos_registrados = True
