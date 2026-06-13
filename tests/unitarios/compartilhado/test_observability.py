"""Unitarios de ``configurar_otel`` (ADR-020, escopo minimo).

Contrato coberto:

- flag ``OTEL_ENABLED`` desligada (ausente ou false) -> ``False`` sem efeito
  algum — nenhum import de OpenTelemetry, nenhum log;
- flag ligada sem o extra ``otel`` instalado -> ``False`` + warning logado
  (boot nunca quebra por dependencia ausente);
- flag ligada com dependencias presentes (stubs em ``sys.modules``) ->
  ``True`` com FastAPI/SQLAlchemy instrumentados no app/engine certos,
  ``/api/v1/saude`` excluida e exporter apontando para o endpoint OTLP.

Os stubs simulam os modulos otel em ``sys.modules`` para que a suite rode
identica com ou sem o extra ``otel`` instalado (CI nao instala o extra).
"""

from __future__ import annotations

import atexit
import sys
import types

import pytest
import structlog
from fastapi import FastAPI
from structlog.testing import capture_logs

import src.compartilhado.infraestrutura.observability as observability_modulo
from src.compartilhado.infraestrutura.observability import configurar_otel


@pytest.fixture(autouse=True)
def _logger_fresco(monkeypatch: pytest.MonkeyPatch) -> None:
    # capture_logs nao intercepta loggers ja "bound" e cacheados
    # (configurar_logging usa cache_logger_on_first_use=True). Um proxy novo
    # por teste devolve o capture deterministico em qualquer ordem da suite.
    monkeypatch.setattr(
        observability_modulo, "_log", structlog.get_logger("test_observability")
    )


def _bloquear_imports_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forca ImportError em qualquer ``import opentelemetry...``.

    Remove modulos otel ja importados (caso o extra esteja instalado e outro
    teste os tenha carregado) e poe ``None`` na raiz — o import system trata
    ``None`` em ``sys.modules`` como import proibido e levanta ImportError.
    """
    for nome in [
        m for m in sys.modules if m == "opentelemetry" or m.startswith("opentelemetry.")
    ]:
        monkeypatch.delitem(sys.modules, nome)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)


@pytest.fixture
def otel_stubs(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Instala stubs dos modulos otel em ``sys.modules`` e devolve o registro
    de chamadas que eles gravam."""
    registro: dict = {}

    class ResourceStub:
        def __init__(self, attributes: dict) -> None:
            self.attributes = attributes

        @classmethod
        def create(cls, attributes: dict) -> ResourceStub:
            registro["resource_attributes"] = attributes
            return cls(attributes)

    class TracerProviderStub:
        def __init__(self, resource: ResourceStub) -> None:
            registro["provider"] = self
            registro["provider_resource"] = resource
            self.processors: list = []

        def add_span_processor(self, processor: object) -> None:
            self.processors.append(processor)

        def shutdown(self) -> None:
            registro["shutdown_chamado"] = True

    class BatchSpanProcessorStub:
        def __init__(self, exporter: object) -> None:
            self.exporter = exporter
            registro["batch_exporter"] = exporter

    class OTLPSpanExporterStub:
        def __init__(self, endpoint: str, insecure: bool) -> None:
            registro["endpoint"] = endpoint
            registro["insecure"] = insecure

    class FastAPIInstrumentorStub:
        @staticmethod
        def instrument_app(app: FastAPI, **kwargs: object) -> None:
            registro["fastapi_app"] = app
            registro["fastapi_kwargs"] = kwargs

    class SQLAlchemyInstrumentorStub:
        def instrument(self, **kwargs: object) -> None:
            registro["sqlalchemy_kwargs"] = kwargs

    simbolos_por_modulo = {
        "opentelemetry.sdk.resources": {"Resource": ResourceStub},
        "opentelemetry.sdk.trace": {"TracerProvider": TracerProviderStub},
        "opentelemetry.sdk.trace.export": {
            "BatchSpanProcessor": BatchSpanProcessorStub
        },
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": {
            "OTLPSpanExporter": OTLPSpanExporterStub
        },
        "opentelemetry.instrumentation.fastapi": {
            "FastAPIInstrumentor": FastAPIInstrumentorStub
        },
        "opentelemetry.instrumentation.sqlalchemy": {
            "SQLAlchemyInstrumentor": SQLAlchemyInstrumentorStub
        },
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

    registro["classes"] = {
        "exporter": OTLPSpanExporterStub,
        "batch": BatchSpanProcessorStub,
        "provider": TracerProviderStub,
    }
    return registro


class TestFlagDesligada:
    def test_flag_ausente_retorna_false_sem_importar_otel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
        # Import bloqueado: se o caminho off tentasse importar otel, o teste
        # veria o warning de dependencia ausente em vez de silencio.
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_otel(FastAPI(), object())

        assert resultado is False
        assert logs == []

    @pytest.mark.parametrize("valor", ["false", "False", "0", "", "off"])
    def test_valores_desligados_retornam_false(
        self, monkeypatch: pytest.MonkeyPatch, valor: str
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", valor)
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_otel(FastAPI(), object())

        assert resultado is False
        assert logs == []


class TestFlagLigadaSemDependencias:
    def test_retorna_false_e_loga_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", "true")
        _bloquear_imports_otel(monkeypatch)

        with capture_logs() as logs:
            resultado = configurar_otel(FastAPI(), object())

        assert resultado is False
        warnings = [log for log in logs if log["log_level"] == "warning"]
        assert len(warnings) == 1
        assert "otel" in str(warnings[0]).lower()
        # A mensagem precisa ser acionavel: dizer como instalar o extra.
        assert "--extra otel" in str(warnings[0])


class TestFlagLigadaComDependencias:
    def test_instrumenta_app_e_engine_e_retorna_true(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.setenv("PYTSTOP_GIT_SHA", "abcdef0123456789")
        app = FastAPI()
        engine = object()

        resultado = configurar_otel(app, engine)

        assert resultado is True
        # Resource identifica o servico na UI do Jaeger.
        atributos = otel_stubs["resource_attributes"]
        assert atributos["service.name"] == "pytstop-api"
        assert atributos["service.version"] == "abcdef012345"  # sha truncado [:12]
        # FastAPI instrumentado no app certo, com saude fora do trace.
        assert otel_stubs["fastapi_app"] is app
        kwargs_fastapi = otel_stubs["fastapi_kwargs"]
        assert "saude" in kwargs_fastapi["excluded_urls"]
        assert kwargs_fastapi["tracer_provider"] is otel_stubs["provider"]
        # SQLAlchemy instrumentado no engine certo, mesmo provider.
        kwargs_sqlalchemy = otel_stubs["sqlalchemy_kwargs"]
        assert kwargs_sqlalchemy["engine"] is engine
        assert kwargs_sqlalchemy["tracer_provider"] is otel_stubs["provider"]
        # Pipeline exporter -> batch -> provider montado.
        assert otel_stubs["endpoint"] == "http://jaeger:4317"
        assert isinstance(
            otel_stubs["batch_exporter"], otel_stubs["classes"]["exporter"]
        )
        processors = otel_stubs["provider"].processors
        assert len(processors) == 1
        assert isinstance(processors[0], otel_stubs["classes"]["batch"])

    def test_registra_shutdown_do_provider_no_atexit(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        """Pod kill/SIGTERM: o BatchSpanProcessor so descarrega a fila no
        shutdown() do provider — sem o registro no atexit os ultimos spans
        do processo seriam perdidos."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        registrados: list[object] = []
        monkeypatch.setattr(atexit, "register", registrados.append)

        assert configurar_otel(FastAPI(), object()) is True
        assert registrados == [otel_stubs["provider"].shutdown]

    def test_endpoint_http_usa_canal_insecure(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        assert configurar_otel(FastAPI(), object()) is True
        assert otel_stubs["insecure"] is True

    def test_endpoint_https_customizado_usa_tls(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://collector:4317")

        assert configurar_otel(FastAPI(), object()) is True
        assert otel_stubs["endpoint"] == "https://collector:4317"
        assert otel_stubs["insecure"] is False

    @pytest.mark.parametrize("valor", ["true", "TRUE", "1", " true "])
    def test_valores_ligados_ativam_instrumentacao(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict, valor: str
    ) -> None:
        monkeypatch.setenv("OTEL_ENABLED", valor)

        assert configurar_otel(FastAPI(), object()) is True

    def test_reconstroi_middleware_stack_ja_construido(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        """configurar_otel roda no lifespan, DEPOIS de o Starlette construir o
        middleware_stack (o proprio scope `lifespan` atravessa o stack). O
        instrumentador do FastAPI so embrulha `build_middleware_stack`; sem o
        rebuild explicito o middleware OTel nunca entra no caminho HTTP —
        sintoma real observado: spans de SQLAlchemy presentes, de FastAPI
        ausentes."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        app = FastAPI()
        app.middleware_stack = app.build_middleware_stack()
        stack_pre_instrumentacao = app.middleware_stack

        assert configurar_otel(app, object()) is True
        assert app.middleware_stack is not None
        assert app.middleware_stack is not stack_pre_instrumentacao

    def test_nao_constroi_middleware_stack_antes_da_hora(
        self, monkeypatch: pytest.MonkeyPatch, otel_stubs: dict
    ) -> None:
        """App ainda sem stack construido (uso fora do lifespan, ex.: testes):
        o Starlette constroi lazy no primeiro scope, ja com o patch do
        instrumentador aplicado — construir aqui seria antecipar estado."""
        monkeypatch.setenv("OTEL_ENABLED", "true")
        app = FastAPI()
        assert app.middleware_stack is None

        assert configurar_otel(app, object()) is True
        assert app.middleware_stack is None
