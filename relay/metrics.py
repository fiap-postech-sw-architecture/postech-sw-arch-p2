"""Instrumentacao OpenTelemetry do relay exposta via Prometheus (TD-022/ADR-024).

O relay (``python -m relay``) e um daemon sem FastAPI — a auto-instrumentacao
HTTP da API (``observability.py``) nao o alcanca. Este modulo monta um
``MeterProvider`` proprio com um ``PrometheusMetricReader`` (que registra os
instrumentos no ``REGISTRY`` default do ``prometheus_client``) e sobe um
servidor HTTP ``/metrics`` via ``start_http_server`` — scrapeado pelo Prometheus
do cluster (``k8s/prometheus.yaml``).

Metricas (meter ``pytstop-relay``):

- ObservableGauges ``outbox_pendentes`` / ``outbox_idade_mais_antigo``
  (exportado como ``outbox_idade_mais_antigo_seconds`` — o exportador anexa o
  ``unit="s"`` ao nome) / ``outbox_dead``: callback roda a MESMA query de
  profundidade que o gauge
  structlog (``consultar_profundidade`` em ``processador.py``) — SQL nao
  duplicado. Os 3 callbacks de UM scrape compartilham um unico ``ProfundidadeOutbox``
  via um cache TTL curto (``_CacheProfundidade``): cada coleta do Prometheus
  dispara as 3 callbacks quase simultaneamente; sem o cache seriam 3
  ``engine.begin()`` + 3 agregacoes de tabela cheia por scrape, e os 3 gauges
  poderiam refletir 3 snapshots diferentes. Com TTL bem abaixo do intervalo de
  scrape (15s), cada scrape ainda le um valor fresco, mas as 3 callbacks dentro
  dele veem UMA query e um snapshot consistente.
- Counters ``outbox_entregue_total`` / ``outbox_falha_total`` /
  ``outbox_dead_total`` / ``outbox_retry_total``: incrementados pelo processador
  nas transicoes de entrega/retry/DLQ via a fachada ``metricas`` (modulo-level).

Default OFF: sem ``RELAY_METRICS_ENABLED`` truthy a funcao retorna antes de
qualquer import de OpenTelemetry — custo zero para compose, CI e testes. Os
imports sao lazy (dentro da funcao) porque o extra ``otel`` fica fora do extra
``test`` de proposito (espelha ``observability.py``): o CI nao instala o SDK, e
a fachada ``metricas`` e um no-op enquanto ``configurar_metricas`` nao injeta os
counters reais — entao os incrementos no processador nunca quebram com o extra
ausente ou as metricas desligadas. Flag ligada sem o extra instalado degrada
para warning + no-op.
"""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Engine

    from relay.processador import ProfundidadeOutbox

_log = structlog.get_logger(__name__)

_VALORES_VERDADEIROS = frozenset({"true", "1"})
_PORTA_PADRAO = 9100
_NOME_METER = "pytstop-relay"
# TTL do snapshot de profundidade compartilhado pelas 3 callbacks de um scrape.
# Bem abaixo do scrape_interval do Prometheus (15s, k8s/prometheus.yaml): cada
# scrape recalcula (valor fresco), mas as 3 callbacks quase simultaneas dentro
# dele reusam um unico ProfundidadeOutbox (1 query, snapshot consistente).
_TTL_PROFUNDIDADE_S = 2.0


class _CacheProfundidade:
    """Cache TTL thread-safe de ``ProfundidadeOutbox`` por scrape.

    O servidor HTTP do ``prometheus_client`` faz scrape de uma thread propria e
    dispara as 3 callbacks dos gauges quase simultaneamente. Este cache faz as 3
    compartilharem uma unica chamada a ``consultar_profundidade`` (1 query +
    snapshot consistente) e so recomputa quando o valor fica mais velho que o
    TTL — comodamente abaixo do intervalo de scrape, entao cada scrape ainda le
    um valor fresco.
    """

    def __init__(
        self,
        consultar: Callable[[], ProfundidadeOutbox],
        *,
        ttl_s: float = _TTL_PROFUNDIDADE_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._consultar = consultar
        self._ttl_s = ttl_s
        self._relogio = relogio
        self._lock = threading.Lock()
        self._em_cache: tuple[float, ProfundidadeOutbox] | None = None

    def obter(self) -> ProfundidadeOutbox:
        agora = self._relogio()
        with self._lock:
            if self._em_cache is not None and agora - self._em_cache[0] < self._ttl_s:
                return self._em_cache[1]
            valor = self._consultar()
            self._em_cache = (agora, valor)
            return valor


class _Counter(Protocol):
    """Superficie minima de um Counter OTel usada pela fachada."""

    # corpo `pass` (nao `...`) evita o FP CodeQL py/ineffectual-statement
    def add(self, amount: int) -> None:
        pass


class MetricasRelay:
    """Fachada dos counters do relay; no-op ate ``configurar_metricas`` injetar.

    O processador chama ``entregue()`` / ``falha()`` / ``dead()`` / ``retry()``
    em cada transicao. Enquanto as metricas estao desligadas (ou o extra ``otel``
    ausente) os counters ficam ``None`` e os metodos sao no-op — os incrementos no
    caminho quente do processador nunca quebram nem custam nada.
    """

    def __init__(self) -> None:
        self._entregue: _Counter | None = None
        self._falha: _Counter | None = None
        self._dead: _Counter | None = None
        self._retry: _Counter | None = None

    def _vincular(
        self,
        *,
        entregue: _Counter,
        falha: _Counter,
        dead: _Counter,
        retry: _Counter,
    ) -> None:
        self._entregue = entregue
        self._falha = falha
        self._dead = dead
        self._retry = retry

    def entregue(self) -> None:
        if self._entregue is not None:
            self._entregue.add(1)

    def falha(self) -> None:
        if self._falha is not None:
            self._falha.add(1)

    def dead(self) -> None:
        if self._dead is not None:
            self._dead.add(1)

    def retry(self) -> None:
        if self._retry is not None:
            self._retry.add(1)


# Singleton modulo-level importado pelo processador (`from relay.metrics import
# metricas`). No-op por padrao; `configurar_metricas` vincula os counters reais.
metricas = MetricasRelay()


def _habilitado() -> bool:
    return (
        os.environ.get("RELAY_METRICS_ENABLED", "false").strip().lower()
        in _VALORES_VERDADEIROS
    )


def configurar_metricas(engine: Engine) -> bool:
    """Liga as metricas OTel do relay expostas via Prometheus (TD-022/ADR-024).

    Le ``RELAY_METRICS_ENABLED`` (default ``"false"``); quando ligada, monta um
    ``MeterProvider`` (service.name=pytstop-relay, service.version=
    PYTSTOP_GIT_SHA curto) com um ``PrometheusMetricReader`` — o reader registra
    os instrumentos no ``REGISTRY`` default do ``prometheus_client`` — e sobe um
    servidor HTTP ``/metrics`` na porta ``RELAY_METRICS_PORT`` (default
    ``9100``) via ``start_http_server``. Registra os ObservableGauges de
    profundidade (callback = ``consultar_profundidade``, mesma query do gauge
    structlog; as 3 callbacks compartilham um snapshot por scrape via
    ``_CacheProfundidade`` — 1 query, gauges coerentes) e vincula os Counters de
    entrega na fachada ``metricas``.

    Returns:
        True quando as metricas foram ativadas; False quando a flag esta
        desligada ou o extra ``otel`` nao esta instalado (warning logado).
    """
    if not _habilitado():
        return False

    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from opentelemetry.metrics import CallbackOptions, Observation
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        from prometheus_client import start_http_server
    except ImportError:
        _log.warning(
            "metricas do relay ignoradas: RELAY_METRICS_ENABLED=true mas o extra "
            "'otel' nao esta instalado; instale com `uv sync --extra otel`",
        )
        return False

    from relay.processador import consultar_profundidade

    # As 3 callbacks de profundidade compartilham um snapshot por scrape: 1 query
    # em vez de 3 e os 3 gauges coerentes entre si (TTL << scrape_interval).
    cache_profundidade = _CacheProfundidade(lambda: consultar_profundidade(engine))

    porta = int(os.environ.get("RELAY_METRICS_PORT", str(_PORTA_PADRAO)))
    resource = Resource.create(
        {
            "service.name": _NOME_METER,
            # Mesmo SHA curto do banner de boot e dos logs (logging.py).
            "service.version": os.environ.get("PYTSTOP_GIT_SHA", "unknown")[:12],
        }
    )
    # O reader registra no REGISTRY default do prometheus_client; o
    # start_http_server abaixo serve esse mesmo registry em /metrics.
    reader = PrometheusMetricReader()
    provider = MeterProvider(metric_readers=[reader], resource=resource)
    meter = provider.get_meter(_NOME_METER)

    def _observar_pendentes(
        _options: CallbackOptions,
    ) -> list[Observation]:
        return [Observation(cache_profundidade.obter().pendentes)]

    def _observar_idade(
        _options: CallbackOptions,
    ) -> list[Observation]:
        # idade e None quando nao ha pendentes (min(...) FILTER -> NULL):
        # nao emite observacao nesse caso (gauge ausente, nao zero enganoso).
        idade = cache_profundidade.obter().idade_mais_antigo_s
        return [] if idade is None else [Observation(idade)]

    def _observar_dead(
        _options: CallbackOptions,
    ) -> list[Observation]:
        return [Observation(cache_profundidade.obter().dead)]

    meter.create_observable_gauge(
        "outbox_pendentes",
        callbacks=[_observar_pendentes],
        description="Eventos da outbox em status pendente.",
    )
    # Nome SEM o sufixo `_segundos`: o exportador Prometheus do OTel anexa o
    # `unit` ("s" -> `_seconds`) ao nome da serie. O nome base + sufixo exportam
    # como `outbox_idade_mais_antigo_seconds` (idiomatico, como os demais gauges
    # de segundos); manter `_segundos` no nome geraria `..._segundos_seconds`.
    meter.create_observable_gauge(
        "outbox_idade_mais_antigo",
        callbacks=[_observar_idade],
        unit="s",
        description="Idade (segundos) do evento pendente mais antigo.",
    )
    meter.create_observable_gauge(
        "outbox_dead",
        callbacks=[_observar_dead],
        description="Eventos da outbox na DLQ (status dead).",
    )

    metricas._vincular(
        entregue=meter.create_counter(
            "outbox_entregue_total",
            description="Eventos entregues com sucesso pelo relay.",
        ),
        falha=meter.create_counter(
            "outbox_falha_total",
            description="Falhas de entrega (handler levantou excecao).",
        ),
        dead=meter.create_counter(
            "outbox_dead_total",
            description="Eventos promovidos para a DLQ (status dead).",
        ),
        retry=meter.create_counter(
            "outbox_retry_total",
            description="Entregas reagendadas com backoff (retry).",
        ),
    )

    start_http_server(porta)
    _log.info("metricas do relay ativas: /metrics", porta=porta)
    return True
