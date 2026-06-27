from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import (
    Limiter,
    _rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.compartilhado.interfaces.middleware import (
    SecurityHeadersMiddleware,
    _resolver_storage_uri,
    configurar_cors,
    configurar_rate_limiting,
)


def _montar_app_com_limiter(limiter: Limiter) -> FastAPI:
    """Anexa ``limiter`` a um app FastAPI minimo exatamente como
    ``configurar_rate_limiting`` (state.limiter + SlowAPIMiddleware +
    handler do ``RateLimitExceeded``), com uma rota ``GET /x`` -> 200."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )

    @app.get("/x")
    def x() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _criar_app_com_saude() -> FastAPI:
    app = FastAPI()

    @app.get("/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestSecurityHeadersMiddleware:
    def test_headers_de_seguranca_aplicados(self) -> None:
        app = _criar_app_com_saude()
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp = client.get("/saude")

        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )
        assert resp.headers["Cache-Control"] == "no-store"
        assert resp.headers["Content-Security-Policy"] == "default-src 'none'"
        assert "X-Request-ID" in resp.headers

    def test_request_id_gerado_por_request(self) -> None:
        app = _criar_app_com_saude()
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp1 = client.get("/saude")
        resp2 = client.get("/saude")

        assert resp1.headers["X-Request-ID"] != resp2.headers["X-Request-ID"]

    def test_csp_nao_aplicado_em_rotas_de_docs(self) -> None:
        app = FastAPI()

        @app.get("/docs")
        def docs_stub() -> dict[str, str]:
            return {"page": "swagger"}

        @app.get("/openapi.json")
        def openapi_stub() -> dict[str, str]:
            return {"openapi": "3.1"}

        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        resp_docs = client.get("/docs")
        assert "Content-Security-Policy" not in resp_docs.headers
        # Security headers still land even when CSP is skipped.
        assert resp_docs.headers["X-Content-Type-Options"] == "nosniff"

        resp_openapi = client.get("/openapi.json")
        assert "Content-Security-Policy" not in resp_openapi.headers


class TestConfigurarCors:
    def test_cors_sem_origens_configuradas(self, monkeypatch: object) -> None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)  # type: ignore[attr-defined]
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}

    def test_cors_com_origem_permitida(self, monkeypatch: object) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "https://allowed.example.com")  # type: ignore[attr-defined]
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://allowed.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://allowed.example.com"
        )

    def test_cors_com_multiplas_origens(self, monkeypatch: object) -> None:
        monkeypatch.setenv(  # type: ignore[attr-defined]
            "CORS_ORIGINS",
            "https://a.example.com, https://b.example.com",
        )
        app = _criar_app_com_saude()
        configurar_cors(app)

        client = TestClient(app)
        resp = client.options(
            "/saude",
            headers={
                "Origin": "https://b.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin") == "https://b.example.com"
        )

    def test_cors_rejeita_wildcard_com_credenciais(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "*")
        app = _criar_app_com_saude()
        with pytest.raises(ValueError, match="CORS_ORIGINS='\\*'"):
            configurar_cors(app)


class TestResolverStorageUri:
    def test_retorna_valor_do_env_quando_definido(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379")
        assert _resolver_storage_uri() == "redis://localhost:6379"

    def test_retorna_none_quando_ausente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RATE_LIMIT_STORAGE_URI", raising=False)
        assert _resolver_storage_uri() is None

    def test_retorna_none_quando_string_vazia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "")
        assert _resolver_storage_uri() is None

    def test_retorna_none_quando_somente_espacos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Um valor só com espaços passaria pelo ``or None`` e faria
        # ``limits.storage_from_string`` disparar ``ConfigurationError`` no
        # import do modulo. O ``strip()`` trata branco como ausente.
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "   ")
        assert _resolver_storage_uri() is None


class TestConfigurarRateLimiting:
    def test_limiter_instalado_no_app(self) -> None:
        app = _criar_app_com_saude()
        configurar_rate_limiting(app)

        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None

    def test_limiter_permite_request_normal(self) -> None:
        app = _criar_app_com_saude()
        configurar_rate_limiting(app)

        client = TestClient(app)
        resp = client.get("/saude")
        assert resp.status_code == 200


class TestGracefulDegradationRedisIndisponivel:
    """Prova do C1 (TD-016): com Redis morto, as requests NAO viram 500.

    O ``Limiter`` aponta para ``redis://127.0.0.1:6390`` — porta sem nada
    escutando, entao a conexao falha imediatamente com ECONNREFUSED (rapido,
    sem Docker). Com ``in_memory_fallback_enabled=True`` o SlowAPI degrada
    para um limiter in-memory por-processo em vez de re-raisar o
    ``ConnectionError`` como 500, e o limite SEGUE sendo enforcado.
    """

    def test_redis_morto_nao_vira_500_e_ainda_rate_limita(self) -> None:
        limiter = Limiter(
            key_func=lambda: "k",
            default_limits=["2/minute"],
            storage_uri="redis://127.0.0.1:6390",
            in_memory_fallback_enabled=True,
        )
        app = _montar_app_com_limiter(limiter)
        client = TestClient(app)

        # 1a e 2a requisicoes: backend Redis morto, mas o fallback in-memory
        # responde 200. A asserciao-chave do C1: NENHUM 500 (sem outage).
        resp1 = client.get("/x")
        resp2 = client.get("/x")
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # 3a requisicao dentro da janela: o fallback in-memory reaproveita os
        # ``default_limits`` ("2/minute") e enforca -> 429 (nao 500).
        resp3 = client.get("/x")
        assert resp3.status_code == 429


class TestMemoryStorageEnforce:
    """Prova (pedido do reviewer de CI) de que o caminho ``memory://`` — o
    backend usado quando ``RATE_LIMIT_STORAGE_URI`` NAO esta definido —
    realmente enforca o limite por-processo."""

    def test_memory_storage_default_trip_no_terceiro_request(self) -> None:
        # Sem ``storage_uri`` o SlowAPI usa ``memory://`` (mesmo backend do
        # ambiente sem RATE_LIMIT_STORAGE_URI).
        limiter = Limiter(
            key_func=lambda: "k",
            default_limits=["2/minute"],
        )
        app = _montar_app_com_limiter(limiter)
        client = TestClient(app)

        assert client.get("/x").status_code == 200
        assert client.get("/x").status_code == 200
        # 3a requisicao excede "2/minute".
        assert client.get("/x").status_code == 429
