"""Unitarios de ``configurar_metricas`` (TD-022/ADR-024, escopo minimo).

Contrato coberto:

- flag ``RELAY_METRICS_ENABLED`` desligada (ausente ou false) -> ``False`` sem
  efeito algum: nenhum import de OpenTelemetry, nenhum servidor, a fachada
  ``metricas`` continua no-op (os incrementos do processador nunca quebram);
- flag ligada sem o extra ``otel`` instalado -> ``False`` + warning acionavel
  (boot do relay nunca quebra por dependencia ausente);
- flag ligada com dependencias presentes (stubs em ``sys.modules``) -> ``True``
  com MeterProvider montado, os 3 ObservableGauges + 4 Counters criados no meter
  ``pytstop-relay``, a fachada ``metricas`` vinculada aos counters reais, o
  ``/metrics`` servido na porta certa e os callbacks dos gauges rodando a query
  de profundidade compartilhada (``consultar_profundidade``), uma consulta por
  callback (sem cache);
- porta invalida (nao numerica) -> ``RuntimeError`` claro no boot; porta
  ocupada (``OSError`` no ``start_http_server``) -> ``False`` + error acionavel
  sem derrubar o relay.

Os stubs simulam os modulos otel/prometheus em ``sys.modules`` para que a suite
rode identica com ou sem o extra ``otel`` instalado (o CI nao instala o extra).
Espelha ``tests/unitarios/compartilhado/test_observability.py``.
"""

from __future__ import annotations

import sys
import types

import pytest
import structlog
from structlog.testing import capture_logs

import relay.metrics as metrics_modulo
import relay.processador as processador_modulo
from relay.metrics import MetricasRelay, configurar_metricas, metricas
from relay.processador import ProfundidadeOutbox


@pytest.fixture(autouse=True)
def _logger_fresco(monkeypatch: pytest.MonkeyPatch) -> None:
    # capture_logs nao intercepta loggers ja "bound"/cacheados
    # (configurar_logging usa cache_logger_on_first_use=True). Um proxy novo por
    # teste devolve o capture deterministico em qualquer ordem da suite.
    monkeypatch.setattr(metrics_modulo, "_log", structlog.get_logger("test_metrics"))


@pytest.fixture(autouse=True)
def _facade_isolada(monkeypatch: pytest.MonkeyPatch) -> None:
    # configurar_metricas vincula o singleton de modulo `metricas`; troca por uma
    # instancia fresca por teste para nao vazar counters entre testes.
    monkeypatch.setattr(metrics_modulo, "metricas", MetricasRelay())


def _bloquear_imports_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forca ImportError em ``import opentelemetry...`` / ``import prometheus_client``.

    Remove os modulos ja importados (caso o extra esteja instalado e outro teste
    os tenha carregado) e poe ``None`` na raiz — o import system trata ``None``
    em ``sys.modules`` como import proibido e levanta ImportError.
    """
    for nome in [
        m
        for m in sys.modules
        if m == "opentelemetry"
        or m.startswith("opentelemetry.")
        or m == "prometheus_client"
        or m.startswith("prometheus_client.")
    ]:
        monkeypatch.delitem(sys.modules, nome)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    monkeypatch.setitem(sys.modules, "prometheus_client", None)


@pytest.fixture
def otel_stubs(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Instala stubs dos modulos otel/prometheus e devolve o registro de chamadas."""
    registro: dict = {
        "gauges": {},
        "counters": {},
        "servidor_porta": None,
    }

    class ResourceStub:
        @classmethod
        def create(cls, attributes: dict) -> ResourceStub:
            registro["resource_attributes"] = attributes
            return cls()

    class CounterStub:
        def __init__(self, nome: str) -> None:
            self.nome = nome
            self.total = 0

        def add(self, amount: int) -> None:
            self.total += amount

    class MeterStub:
        def create_observable_gauge(
            self, nome: str, *, callbacks: list, **_kwargs: object
        ) -> None:
            registro["gauges"][nome] = callbacks

        def create_counter(self, nome: str, **_kwargs: object) -> CounterStub:
            contador = CounterStub(nome)
            registro["counters"][nome] = contador
            return contador

    class MeterProviderStub:
        def __init__(self, *, metric_readers: list, resource: object) -> None:
            registro["provider"] = self
            registro["metric_readers"] = metric_readers
            registro["provider_resource"] = resource

        def get_meter(self, nome: str) -> MeterStub:
            registro["meter_nome"] = nome
            return MeterStub()

    class PrometheusMetricReaderStub:
        def __init__(self) -> None:
            registro["reader"] = self

    class ObservationStub:
        def __init__(self, value: float) -> None:
            self.value = value

    def start_http_server_stub(porta: int) -> None:
        registro["servidor_porta"] = porta

    simbolos_por_modulo = {
        "opentelemetry.exporter.prometheus": {
            "PrometheusMetricReader": PrometheusMetricReaderStub
        },
        "opentelemetry.metrics": {
            "CallbackOptions": object,
            "Observation": ObservationStub,
        },
        "opentelemetry.sdk.metrics": {"MeterProvider": MeterProviderStub},
        "opentelemetry.sdk.resources": {"Resource": ResourceStub},
        "prometheus_client": {"start_http_server": start_http_server_stub},
    }

    # Registra cada modulo-alvo e todos os pacotes intermediarios: o import
    # system resolve pais antes dos filhos em `from a.b.c import d`.
    instalados: dict[str, types.ModuleType] = {}
    for caminho, simbolos in simbolos_por_modulo.items():
        partes = caminho.split(".")
        for i in range(1, len(partes) + 1):
            prefixo = ".".join(partes[:i])
            if prefixo not in instalados:
                instalados[prefixo] = types.ModuleType(prefixo)
        for nome, valor in simbolos.items():
            setattr(instalados[caminho], nome, valor)
    for caminho, modulo in instalados.items():
        monkeypatch.setitem(sys.modules, caminho, modulo)

    registro["classes"] = {"observation": ObservationStub}
    return registro


# ---------------------------------------------------------------------------
# Fachada no-op (independe do extra; e o caminho quente do processador)
# ---------------------------------------------------------------------------


class TestFachadaNoOp:
    def test_incrementos_sem_vinculo_nao_quebram(self) -> None:
        # Sem configurar_metricas os counters ficam None: os incrementos que o
        # processador faz em cada transicao precisam ser no-op silenciosos.
        fachada = MetricasRelay()
        fachada.entregue()
        fachada.falha()
        fachada.dead()
        fachada.retry()
        # Nada a asseverar alem de nao levantar: o contrato e "nunca quebra".

    def test_singleton_de_modulo_e_no_op_por_padrao(self) -> None:
        # O `metricas` importado pelo processador comeca no-op (sem extra/flag).
        metricas.entregue()
        metricas.falha()
        metricas.dead()
        metricas.retry()


# ---------------------------------------------------------------------------
# Flag desligada
# ---------------------------------------------------------------------------


class TestFlagDesligada:
    def test_flag_ausente_retorna_false_sem_importar_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RELAY_METRICS_ENABLED", raising=False)
        # Import bloqueado: se o caminho off tentasse importar, o teste veria o
        # warning de dependencia ausente em vez de silencio.
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_metricas(object())  # type: ignore[arg-type]

        assert resultado is False
        assert logs == []
        # A fachada permanece no-op (counters nao vinculados).
        assert metrics_modulo.metricas._entregue is None

    @pytest.mark.parametrize("valor", ["false", "False", "0", "", "off"])
    def test_valores_desligados_retornam_false(
        self, monkeypatch: pytest.MonkeyPatch, valor: str
    ) -> None:
        monkeypatch.setenv("RELAY_METRICS_ENABLED", valor)
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_metricas(object())  # type: ignore[arg-type]

        assert resultado is False
        assert logs == []


# ---------------------------------------------------------------------------
# Flag ligada, extra ausente
# ---------------------------------------------------------------------------


class TestFlagLigadaSemDependencias:
    def test_retorna_false_e_loga_warning_acionavel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_metricas(object())  # type: ignore[arg-type]

        assert resultado is False
        warnings = [log for log in logs if log["log_level"] == "warning"]
        assert len(warnings) == 1
        # A mensagem precisa ser acionavel: dizer como instalar o extra.
        assert "--extra otel" in str(warnings[0])
        # E a fachada nao foi vinculada -> incrementos do processador sao no-op.
        assert metrics_modulo.metricas._entregue is None


# ---------------------------------------------------------------------------
# Flag ligada, dependencias presentes (stubs)
# ---------------------------------------------------------------------------


class TestFlagLigadaComDependencias:
    def test_monta_provider_gauges_counters_e_servidor(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")
        monkeypatch.delenv("RELAY_METRICS_PORT", raising=False)
        monkeypatch.setenv("PYTSTOP_GIT_SHA", "abcdef0123456789")
        engine = object()

        resultado = configurar_metricas(engine)  # type: ignore[arg-type]

        assert resultado is True
        # Resource identifica o servico no Prometheus.
        atributos = otel_stubs["resource_attributes"]
        assert atributos["service.name"] == "pytstop-relay"
        assert atributos["service.version"] == "abcdef012345"  # sha [:12]
        # Meter nomeado pytstop-relay; reader injetado no provider.
        assert otel_stubs["meter_nome"] == "pytstop-relay"
        assert otel_stubs["metric_readers"] == [otel_stubs["reader"]]
        # Os 3 gauges de profundidade registrados. O gauge de idade usa o nome
        # base `outbox_idade_mais_antigo` (sem `_segundos`): o exportador
        # Prometheus do OTel anexa o `unit="s"` -> serie
        # `outbox_idade_mais_antigo_seconds` (evita o duplo `_segundos_seconds`).
        assert set(otel_stubs["gauges"]) == {
            "outbox_pendentes",
            "outbox_idade_mais_antigo",
            "outbox_dead",
        }
        # Os 4 counters de entrega registrados.
        assert set(otel_stubs["counters"]) == {
            "outbox_entregue_total",
            "outbox_falha_total",
            "outbox_dead_total",
            "outbox_retry_total",
        }
        # /metrics servido na porta default 9100.
        assert otel_stubs["servidor_porta"] == 9100

    def test_porta_customizada_via_env(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")
        monkeypatch.setenv("RELAY_METRICS_PORT", "9200")

        assert configurar_metricas(object()) is True  # type: ignore[arg-type]
        assert otel_stubs["servidor_porta"] == 9200

    def test_fachada_vinculada_incrementa_os_counters_reais(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        # Apos configurar, a fachada `metricas` que o processador usa passa a
        # incrementar os counters OTel reais (1 add por chamada).
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")

        assert configurar_metricas(object()) is True  # type: ignore[arg-type]

        fachada = metrics_modulo.metricas
        fachada.entregue()
        fachada.entregue()
        fachada.falha()
        fachada.dead()
        fachada.retry()

        counters = otel_stubs["counters"]
        assert counters["outbox_entregue_total"].total == 2
        assert counters["outbox_falha_total"].total == 1
        assert counters["outbox_dead_total"].total == 1
        assert counters["outbox_retry_total"].total == 1

    def test_callbacks_dos_gauges_usam_a_query_compartilhada(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        # Os gauges devem ler a profundidade pela MESMA funcao do gauge structlog
        # (consultar_profundidade) — SQL nao duplicado (TD-022). Cada callback
        # consulta DIRETO (o cache TTL+lock por scrape foi removido: 3 queries
        # baratas por scrape valem menos que a maquinaria). Espia a query e
        # confere valores e contagem.
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")

        chamadas = {"n": 0}

        def _query_espiada(_engine: object) -> ProfundidadeOutbox:
            chamadas["n"] += 1
            return ProfundidadeOutbox(pendentes=7, idade_mais_antigo_s=12.5, dead=3)

        # consultar_profundidade e importada lazy de relay.processador dentro de
        # configurar_metricas; faz patch na origem (o `from ... import ...` resolve
        # o atributo do modulo no momento da chamada).
        monkeypatch.setattr(
            processador_modulo, "consultar_profundidade", _query_espiada
        )

        assert configurar_metricas(object()) is True  # type: ignore[arg-type]

        gauges = otel_stubs["gauges"]
        (pendentes,) = gauges["outbox_pendentes"][0](None)
        (idade,) = gauges["outbox_idade_mais_antigo"][0](None)
        (dead,) = gauges["outbox_dead"][0](None)
        assert pendentes.value == 7
        assert idade.value == 12.5
        assert dead.value == 3
        assert chamadas["n"] == 3, (
            "cada callback consulta a profundidade direto (sem cache): 3 gauges "
            f"-> 3 chamadas a consultar_profundidade, mas houve {chamadas['n']}"
        )

    def test_gauge_idade_omite_observacao_quando_nao_ha_pendentes(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        # idade None (sem pendentes) -> callback nao emite observacao (gauge
        # ausente, em vez de zero enganoso).
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")
        monkeypatch.setattr(
            processador_modulo,
            "consultar_profundidade",
            lambda _engine: ProfundidadeOutbox(
                pendentes=0, idade_mais_antigo_s=None, dead=0
            ),
        )

        assert configurar_metricas(object()) is True  # type: ignore[arg-type]

        gauges = otel_stubs["gauges"]
        assert gauges["outbox_idade_mais_antigo"][0](None) == []
        # pendentes/dead continuam emitindo (zero e significativo neles).
        (pendentes,) = gauges["outbox_pendentes"][0](None)
        assert pendentes.value == 0

    def test_porta_invalida_falha_no_boot_com_erro_claro(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        # Misconfig de porta deve falhar CLARO no boot (nomeando a variavel),
        # nao estourar com ValueError criptico dentro do int().
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")
        monkeypatch.setenv("RELAY_METRICS_PORT", "nove-mil-e-cem")

        with pytest.raises(RuntimeError, match="RELAY_METRICS_PORT"):
            configurar_metricas(object())  # type: ignore[arg-type]

    def test_porta_ocupada_degrada_com_log_acionavel(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        # OSError no start_http_server (porta em uso) NAO derruba o boot do
        # relay (metricas sao acessorio): loga error acionavel, retorna False
        # e nada e registrado/vinculado (fachada segue no-op).
        monkeypatch.setenv("RELAY_METRICS_ENABLED", "true")

        def start_ocupado(_porta: int) -> None:
            raise OSError(98, "address already in use")

        monkeypatch.setattr(
            sys.modules["prometheus_client"], "start_http_server", start_ocupado
        )

        with capture_logs() as logs:
            resultado = configurar_metricas(object())  # type: ignore[arg-type]

        assert resultado is False
        erros = [log for log in logs if log["log_level"] == "error"]
        assert len(erros) == 1
        # A mensagem precisa ser acionavel: apontar a variavel de porta.
        assert "RELAY_METRICS_PORT" in str(erros[0])
        # Nenhum instrumento registrado e fachada nao vinculada (no-op).
        assert otel_stubs["gauges"] == {}
        assert otel_stubs["counters"] == {}
        assert metrics_modulo.metricas._entregue is None
