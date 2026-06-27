"""Prova do TD-016: rate limit COMPARTILHADO entre replicas via Redis.

Duas instancias independentes de ``Limiter`` (simulando dois pods/replicas)
apontando para o MESMO ``storage_uri`` Redis enforcam um limite AGREGADO: a
contagem de uma replica e visivel para a outra. Sem o backend compartilhado
cada processo teria seu proprio contador em memoria e o limite global nunca
seria respeitado entre replicas.

Roda contra um Redis real (testcontainer ``redis:7``), seguindo a mesma
convencao dos demais testes de integracao do repo (Postgres via
testcontainers): o container e instanciado dentro de uma fixture e o teste
roda apenas via ``make test-integ`` com Docker disponivel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import Limiter

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.integracao


@pytest.fixture
def redis_url() -> Generator[str]:
    """Sobe um Redis dedicado e deriva ``redis://<host>:<port>``."""
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield f"redis://{host}:{port}"


def _criar_pod(storage_uri: str) -> FastAPI:
    """Monta um app FastAPI com um ``Limiter`` proprio, anexado exatamente
    como ``configurar_rate_limiting`` faz (state.limiter + middleware +
    handler), compartilhando o ``storage_uri`` informado."""
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    app = FastAPI()
    lim = Limiter(
        key_func=lambda: "k",
        default_limits=["3/minute"],
        storage_uri=storage_uri,
    )
    app.state.limiter = lim
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

    @app.get("/x")
    def x() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_duas_replicas_compartilham_contador_via_redis(redis_url: str) -> None:
    app_a = _criar_pod(redis_url)
    app_b = _criar_pod(redis_url)

    # Pod A consome as 3 requisicoes permitidas pelo limite "3/minute".
    cliente_a = TestClient(app_a)
    for _ in range(3):
        resp = cliente_a.get("/x")
        assert resp.status_code == 200

    # Pod B faz a 4a requisicao GLOBAL. Como o contador vive no Redis
    # compartilhado, o segundo pod VE a contagem do primeiro e bloqueia.
    cliente_b = TestClient(app_b)
    resp_b = cliente_b.get("/x")
    assert resp_b.status_code == 429
