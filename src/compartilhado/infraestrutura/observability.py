"""Instrumentacao OpenTelemetry minima (ADR-020, diferencial opcional).

Auto-instrumentation de FastAPI + SQLAlchemy exportando traces OTLP/gRPC
direto para o Jaeger all-in-one do cluster de demo. Telemetria e detalhe de
borda (ADR-015): nenhuma camada interna importa OTel — este modulo e o unico
ponto de contato, chamado pelo lifespan em ``src/main.py``.

Default OFF: sem ``OTEL_ENABLED=true`` a funcao retorna antes de qualquer
import de OpenTelemetry — custo zero para compose, CI e testes. Os imports
sao lazy (dentro da funcao) porque o extra ``otel`` fica fora do extra
``test`` de proposito: o CI nao instala SDK + grpcio, e o mypy do CI so
enxerga estes modulos via override ``ignore_missing_imports`` no
``pyproject.toml``. Flag ligada sem o extra instalado degrada para warning +
no-op — nunca quebra o boot.
"""

from __future__ import annotations

import atexit
import os
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy import Engine

_log = structlog.get_logger(__name__)

# Porta 4317 = OTLP/gRPC do Jaeger all-in-one (k8s/jaeger.yaml e servico
# `jaeger` do docker-compose.yml usam o mesmo nome DNS).
_ENDPOINT_PADRAO = "http://jaeger:4317"
_VALORES_VERDADEIROS = frozenset({"true", "1"})

# Marcador que substitui a query string nos spans (TD-017).
_QUERY_REDIGIDA = "REDACTED"


def _redigir_pii_da_span(span: object, scope: object) -> None:
    """``server_request_hook`` do FastAPIInstrumentor: remove PII da query.

    A consulta publica de acompanhamento recebe ``placa``/``documento`` como
    query params; a instrumentacao HTTP grava ``url.query``/``http.target`` nos
    spans, levando PII (CPF/CNPJ/placa) ao Jaeger (TD-017). Este hook roda na
    criacao do span server — DEPOIS de a instrumentacao setar os atributos
    padrao — e sobrescreve os que carregam a query: ``url.query`` vira
    ``REDACTED`` e ``http.target`` fica so com o path.

    Funcao pura (sem import de OpenTelemetry) para ser testavel com o extra
    ``otel`` ausente: opera apenas sobre o protocolo do ``span`` (set_attribute
    / is_recording) e o ``scope`` ASGI.
    """
    is_recording = getattr(span, "is_recording", None)
    if not callable(is_recording) or not is_recording():
        return
    set_attribute = getattr(span, "set_attribute", None)
    if not callable(set_attribute):
        return
    set_attribute("url.query", _QUERY_REDIGIDA)
    path = scope.get("path", "") if isinstance(scope, dict) else ""
    if isinstance(path, str) and path:
        # http.target (conv. antiga) carregava path + "?" + query; url.path
        # (conv. nova) e so o path — ambos ficam sem a query.
        set_attribute("http.target", path)
        set_attribute("url.path", path)


def configurar_otel(app: FastAPI, engine: Engine) -> bool:
    """Liga a auto-instrumentacao FastAPI + SQLAlchemy com export OTLP.

    Le ``OTEL_ENABLED`` (default ``"false"``); quando ligada, monta
    TracerProvider (service.name=pytstop-api, service.version=PYTSTOP_GIT_SHA
    curto) com BatchSpanProcessor -> OTLPSpanExporter gRPC no endpoint
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default ``http://jaeger:4317``; o scheme
    ``http://`` seleciona canal gRPC sem TLS). ``/api/v1/saude`` fica fora do
    trace — probes do kubelet e healthchecks gerariam ruido continuo.

    Returns:
        True quando a instrumentacao foi ativada; False quando a flag esta
        desligada ou o extra ``otel`` nao esta instalado (warning logado).
    """
    habilitado = (
        os.environ.get("OTEL_ENABLED", "false").strip().lower() in _VALORES_VERDADEIROS
    )
    if not habilitado:
        return False

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        _log.warning(
            "otel ignorado: OTEL_ENABLED=true mas o extra 'otel' nao esta "
            "instalado; instale com `uv sync --extra otel`",
        )
        return False

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", _ENDPOINT_PADRAO)
    resource = Resource.create(
        {
            "service.name": "pytstop-api",
            # Mesmo SHA curto do banner de boot e dos logs (logging.py).
            "service.version": os.environ.get("PYTSTOP_GIT_SHA", "unknown")[:12],
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint,
                insecure=endpoint.startswith("http://"),
            )
        )
    )
    # Pod kill/SIGTERM nao perde os ultimos spans: o shutdown() descarrega o batch.
    atexit.register(provider.shutdown)

    # tracer_provider explicito nos dois instrumentadores em vez de
    # trace.set_tracer_provider global: o provider global so aceita um set
    # por processo (warm restart/testes logariam "Overriding ... not
    # allowed") e nada mais no app le o provider global.
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/api/v1/saude",
        # Redige placa/documento da query string antes de exportar (TD-017).
        server_request_hook=_redigir_pii_da_span,
    )
    # O instrumentador (0.63b) nao adiciona middleware: ele embrulha
    # `build_middleware_stack`. Como esta funcao roda no lifespan e o proprio
    # scope `lifespan` ja fez o Starlette construir o stack, o embrulho nunca
    # seria invocado — spans de SQLAlchemy apareceriam e os de FastAPI nao
    # (sintoma validado contra Jaeger real). Reconstruir aqui e seguro: o
    # uvicorn so aceita conexoes depois de o startup completar, entao nenhuma
    # request usa o stack antigo; o scope lifespan em andamento segue na
    # cadeia antiga, que delega ao mesmo router.
    if app.middleware_stack is not None:
        app.middleware_stack = app.build_middleware_stack()
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    _log.info("otel configurado: traces OTLP ativos", endpoint=endpoint)
    return True
