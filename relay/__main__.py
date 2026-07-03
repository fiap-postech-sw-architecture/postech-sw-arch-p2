"""Entrypoint do relay: ``python -m relay``.

Espelha o bootstrap do app (logging + imperative mappings + engine) sem
subir FastAPI. Roda na MESMA imagem da API; o manifesto ``pytstop-relay``
apenas sobrescreve ``command`` para ``["python","-m","relay"]``. NAO roda
migrations: no cluster quem aplica ``alembic upgrade head`` e o Job dedicado
``pytstop-migrate`` antes do rollout (TD-015; ``RUN_MIGRATIONS_ON_STARTUP``
fica ``false`` no ``k8s/configmap.yaml``).
"""

from __future__ import annotations

import os
import signal
import threading
from datetime import UTC, datetime

import structlog

_log = structlog.get_logger(__name__)


def _bootstrap_mappings() -> None:
    """Registra os mappings imperativos + tabelas Core da outbox."""
    from src.compartilhado.infraestrutura.bootstrap import (
        iniciar_todos_mapeamentos,
    )

    iniciar_todos_mapeamentos()


def main() -> None:
    from relay.handlers import NOME_HANDLER_EMAIL, construir_mapa_handlers
    from relay.listener import executar_relay
    from relay.metrics import configurar_metricas
    from src.compartilhado.infraestrutura.database import criar_engine
    from src.compartilhado.infraestrutura.logging import configurar_logging

    # O relay e um daemon standalone (`python -m relay`): ao contrario da API,
    # NAO sobe uvicorn, que e quem instala um handler no root logger do stdlib.
    # `configurar_logging` (issue #86) agora instala ELE PROPRIO um StreamHandler
    # em INFO no stdout no root logger -- com o `ProcessorFormatter` que mascara
    # PII/segredos tambem nos logs stdlib. Isso cobre a visibilidade que antes
    # exigia um `basicConfig` aqui (eventos INFO do relay: outbox_profundidade,
    # entrega_pulada_fencing, entregas) E garante que nenhum log saia sem passar
    # pelo scrubber. Processo isolado da API -- nao afeta nem duplica o uvicorn.
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
    # Como PID 1 do container, o processo IGNORA SIGTERM sem handler — todo
    # rollout esperava os 30s de terminationGracePeriodSeconds e morria por
    # SIGKILL sem rodar o finally. O Event encerra o loop no proximo ciclo
    # (a entrega e at-least-once; kill abrupto ja era seguro por design).
    encerrar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: encerrar.set())
    signal.signal(signal.SIGINT, lambda *_: encerrar.set())
    try:
        executar_relay(
            engine,
            handlers=construir_mapa_handlers(engine),
            nome_handler=NOME_HANDLER_EMAIL,
            relogio=lambda: datetime.now(UTC),
            parar=encerrar.is_set,
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
