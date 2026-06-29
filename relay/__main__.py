"""Entrypoint do relay: ``python -m relay``.

Espelha o bootstrap do app (logging + imperative mappings + engine) sem
subir FastAPI. Roda na MESMA imagem da API; o manifesto ``pytstop-relay``
apenas sobrescreve ``command`` para ``["python","-m","relay"]``. NAO roda
migrations: no cluster quem aplica ``alembic upgrade head`` e o Job dedicado
``pytstop-migrate`` antes do rollout (TD-015; ``RUN_MIGRATIONS_ON_STARTUP``
fica ``false`` no ``k8s/configmap.yaml``).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime

import structlog

_log = structlog.get_logger(__name__)


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
    from relay.metrics import configurar_metricas
    from src.compartilhado.infraestrutura.database import criar_engine
    from src.compartilhado.infraestrutura.logging import configurar_logging

    # O relay e um daemon standalone (`python -m relay`): ao contrario da API,
    # NAO sobe uvicorn, que e quem instala um handler no root logger do stdlib.
    # `configurar_logging` roteia o structlog pelo stdlib (LoggerFactory), entao
    # sem um handler no root os eventos INFO do relay (outbox_profundidade,
    # entrega_pulada_fencing, entregas) ficariam no nivel WARNING-default e nao
    # chegariam ao stdout / `kubectl logs`. Instala um StreamHandler em INFO no
    # stdout (idempotente: so age se o root ainda nao tem handler) ANTES de
    # configurar o structlog. Processo isolado da API — nao afeta nem duplica o
    # logging do uvicorn (entrypoint/outro processo).
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(message)s")
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
    # Metricas OTel via Prometheus (TD-022/ADR-024): gated por
    # RELAY_METRICS_ENABLED (default off), igual a API liga o OTel pelo
    # OTEL_ENABLED. Sobe /metrics ANTES do loop para que o Prometheus ja
    # encontre o alvo no primeiro scrape.
    metricas_ativas = configurar_metricas(engine)
    if not metricas_ativas:
        _log.info("relay sem metricas OTel (RELAY_METRICS_ENABLED desligado)")
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
