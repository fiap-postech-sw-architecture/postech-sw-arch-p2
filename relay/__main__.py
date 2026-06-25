"""Entrypoint do relay: ``python -m relay``.

Espelha o bootstrap do app (logging + imperative mappings + engine) sem
subir FastAPI. Roda na MESMA imagem da API; o manifesto ``pytstop-relay``
apenas sobrescreve ``command`` para ``["python","-m","relay"]``. NAO roda
migrations (a API pod executa ``alembic upgrade head`` no boot).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime


def _bootstrap_mappings() -> None:
    """Registra os mappings imperativos + tabelas Core da outbox."""
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
    import src.compartilhado.infraestrutura.outbox_mapping  # noqa: F401


def main() -> None:
    from relay.handlers import NOME_HANDLER_EMAIL, construir_mapa_handlers
    from relay.listener import executar_relay
    from src.compartilhado.infraestrutura.database import criar_engine
    from src.compartilhado.infraestrutura.logging import configurar_logging

    configurar_logging()
    git_sha = os.environ.get("PYTSTOP_GIT_SHA", "unknown")[:12]
    git_date = os.environ.get("PYTSTOP_GIT_DATE", "unknown")
    print(f">>> pytstop relay | commit {git_sha} | {git_date}", flush=True)

    _bootstrap_mappings()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        msg = "DATABASE_URL obrigatoria para o relay."
        raise RuntimeError(msg)
    engine = criar_engine(database_url)
    try:
        executar_relay(
            engine,
            handlers=construir_mapa_handlers(engine),
            nome_handler=NOME_HANDLER_EMAIL,
            relogio=lambda: datetime.now(UTC),
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
