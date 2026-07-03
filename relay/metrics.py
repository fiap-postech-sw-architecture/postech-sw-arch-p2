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
  ``unit="s"`` ao nome) / ``outbox_dead``: cada callback roda a MESMA query de
  profundidade que o gauge structlog (``consultar_profundidade`` em
  ``processador.py``) — SQL nao duplicado. Um scrape dispara as 3 callbacks e
  portanto 3 queries; e barato (agregacao restrita por ``status`` indexado, a
  cada scrape_interval de 15s) e dispensa o cache TTL+lock que ja viveu aqui —
  uma divergencia momentanea entre os 3 gauges e irrelevante para gauges de
  fila, e simplicidade vale mais que a micro-otimizacao.
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
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from sqlalchemy import Engine

_log = structlog.get_logger(__name__)

_VALORES_VERDADEIROS = frozenset({"true", "1"})
_PORTA_PADRAO = 9100
_NOME_METER = "pytstop-relay"


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
    structlog, uma consulta por callback) e vincula os Counters de entrega na
    fachada ``metricas``.

    Raises:
        RuntimeError: ``RELAY_METRICS_PORT`` nao numerica (misconfig deve
            falhar CLARO no boot, nao virar warning perdido).

    Returns:
        True quando as metricas foram ativadas; False quando a flag esta
        desligada, o extra ``otel`` nao esta instalado (warning logado) ou a
        porta do ``/metrics`` esta ocupada (error acionavel logado — o relay
        segue entregando sem metricas, que sao acessorio, nao missao).
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

    porta_bruta = os.environ.get("RELAY_METRICS_PORT", str(_PORTA_PADRAO))
    try:
        porta = int(porta_bruta)
    except ValueError as exc:
        msg = (
            f"config invalida no boot: RELAY_METRICS_PORT={porta_bruta!r} "
            "(esperado numero inteiro de porta)"
        )
        raise RuntimeError(msg) from exc

    # Sobe o /metrics ANTES de registrar instrumentos: se a porta estiver
    # ocupada (outro processo, pod anterior em drain), degrada para no-op sem
    # deixar provider/gauges orfaos — e sem derrubar o relay, cuja missao e
    # entregar e-mail; metricas sao acessorio.
    try:
        start_http_server(porta)
    except OSError as exc:
        _log.error(
            "metricas do relay indisponiveis: falha ao subir o /metrics — "
            "porta ocupada? ajuste RELAY_METRICS_PORT ou libere a porta",
            porta=porta,
            erro=str(exc),
        )
        return False

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
        return [Observation(consultar_profundidade(engine).pendentes)]

    def _observar_idade(
        _options: CallbackOptions,
    ) -> list[Observation]:
        # idade e None quando nao ha pendentes (min(...) FILTER -> NULL):
        # nao emite observacao nesse caso (gauge ausente, nao zero enganoso).
        idade = consultar_profundidade(engine).idade_mais_antigo_s
        return [] if idade is None else [Observation(idade)]

    def _observar_dead(
        _options: CallbackOptions,
    ) -> list[Observation]:
        return [Observation(consultar_profundidade(engine).dead)]

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

    _log.info("metricas do relay ativas: /metrics", porta=porta)
    return True
