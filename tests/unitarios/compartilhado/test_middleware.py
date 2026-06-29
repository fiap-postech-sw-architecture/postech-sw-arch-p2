from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import (
    Limiter,
    _rate_limit_exceeded_handler,
)
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.compartilhado.interfaces.middleware import (
    SecurityHeadersMiddleware,
    _resolver_storage_uri,
    _resolver_trusted_proxies,
    configurar_cors,
    configurar_proxy_headers,
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


class TestResolverTrustedProxies:
    """Parsing de ``TRUSTED_PROXIES`` (helper que alimenta o middleware)."""

    def test_vazio_quando_ausente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        assert _resolver_trusted_proxies() == []

    def test_vazio_quando_string_vazia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRUSTED_PROXIES", "")
        assert _resolver_trusted_proxies() == []

    def test_vazio_quando_so_virgulas_e_espacos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Tokens em branco sao descartados — uma lista de strings vazias
        # confiaria em literais "" no uvicorn, sem sentido.
        monkeypatch.setenv("TRUSTED_PROXIES", " , ,  ")
        assert _resolver_trusted_proxies() == []

    def test_lista_com_multiplos_hosts_trimada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.5, 10.0.0.0/8 , *")
        assert _resolver_trusted_proxies() == ["10.0.0.5", "10.0.0.0/8", "*"]


# IP do peer imediato (conexao TCP) usado nos testes de proxy. O TestClient
# permite fixar o client do scope ASGI via kwarg ``client=`` — assim o teste
# controla deterministicamente quem e o peer, sem depender do literal
# "testclient" default.
_PEER_PROXY = "10.0.0.5"
_PEER_NAO_CONFIAVEL = "203.0.113.9"


def _montar_app_proxy(*, limite: str = "2/minute") -> FastAPI:
    """App minimo que espelha a ORDEM de ``criar_app`` para o caminho do proxy.

    Constroi um ``Limiter`` PROPRIO (keyed por ``get_remote_address``, sem
    tocar o singleton do modulo) + ``SlowAPIMiddleware`` e, por fora,
    ``configurar_proxy_headers`` (que le ``TRUSTED_PROXIES`` do ambiente — o
    teste ja o configura via ``monkeypatch`` ANTES de chamar este helper). A
    rota ``GET /ip`` devolve o ``request.client.host`` resolvido — exatamente
    a chave que o limiter usa — e e limitada a ``limite`` para o teste
    comportamental de buckets.
    """
    limiter = Limiter(key_func=get_remote_address, default_limits=[limite])
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
    # Mesma ordem de criar_app: proxy-headers DEPOIS do SlowAPI -> fica por
    # fora dele -> reescreve o client antes do limiter ler request.client.host.
    configurar_proxy_headers(app)

    @app.get("/ip")
    def ip(request: Request) -> dict[str, str | None]:
        return {"client": request.client.host if request.client else None}

    return app


class TestProxyHeadersChaveDeRateLimit:
    """TD-023: a chave do rate limiter vira o IP REAL do cliente atras de um
    proxy confiavel; sem ``TRUSTED_PROXIES`` o XFF e ignorado (sem spoof)."""

    def test_confiavel_com_xff_chaveia_pelo_cliente_real(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Peer = proxy confiavel; XFF carrega o IP do cliente real -> o
        # middleware reescreve request.client para esse IP.
        monkeypatch.setenv("TRUSTED_PROXIES", _PEER_PROXY)
        app = _montar_app_proxy()
        client = TestClient(app, client=(_PEER_PROXY, 51000))

        resp = client.get("/ip", headers={"X-Forwarded-For": "198.51.100.7"})

        assert resp.status_code == 200
        # A chave do rate limiter (request.client.host) e o cliente do XFF,
        # NAO o IP do proxy.
        assert resp.json()["client"] == "198.51.100.7"

    def test_confiavel_xffs_distintos_nao_compartilham_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Atras do MESMO proxy confiavel, dois clientes (XFF distintos) tem
        # buckets SEPARADOS: cada um vai ate o limite de forma independente.
        monkeypatch.setenv("TRUSTED_PROXIES", _PEER_PROXY)
        app = _montar_app_proxy(limite="2/minute")
        client = TestClient(app, client=(_PEER_PROXY, 51000))

        cliente_a = {"X-Forwarded-For": "198.51.100.7"}
        cliente_b = {"X-Forwarded-For": "198.51.100.8"}

        # Cliente A gasta o limite (2/minute) e e barrado no 3o.
        assert client.get("/ip", headers=cliente_a).status_code == 200
        assert client.get("/ip", headers=cliente_a).status_code == 200
        assert client.get("/ip", headers=cliente_a).status_code == 429

        # Cliente B, no MESMO proxy, segue com o bucket cheio -> 200. Se o XFF
        # fosse ignorado (bucket unico do proxy), ja viria 429 aqui.
        assert client.get("/ip", headers=cliente_b).status_code == 200
        assert client.get("/ip", headers=cliente_b).status_code == 200

    def test_default_vazio_ignora_xff_e_chaveia_pelo_peer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TRUSTED_PROXIES ausente (default): o middleware NAO e instalado, o
        # XFF e ignorado e a chave e o IP do peer. Garantia de no-spoof.
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        app = _montar_app_proxy()
        client = TestClient(app, client=(_PEER_NAO_CONFIAVEL, 51000))

        resp = client.get("/ip", headers={"X-Forwarded-For": "198.51.100.7"})

        assert resp.status_code == 200
        # Chave = peer imediato, nao o XFF spoofavel.
        assert resp.json()["client"] == _PEER_NAO_CONFIAVEL

    def test_default_vazio_xffs_distintos_compartilham_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sem proxy confiavel, variar o XFF NAO cria buckets novos: o bucket e
        # do peer (classico bucket unico). Spoofar XFF nao tem efeito.
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        app = _montar_app_proxy(limite="2/minute")
        client = TestClient(app, client=(_PEER_NAO_CONFIAVEL, 51000))

        # 2 requisicoes (XFF distintos) gastam o limite do peer; a 3a (outro
        # XFF ainda) e barrada -> o XFF nao abriu bucket novo.
        assert (
            client.get("/ip", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        )
        assert (
            client.get("/ip", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
        )
        assert (
            client.get("/ip", headers={"X-Forwarded-For": "3.3.3.3"}).status_code == 429
        )

    def test_peer_nao_confiavel_ignora_xff_mesmo_com_middleware(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TRUSTED_PROXIES setado (middleware instalado), mas o peer NAO esta na
        # lista -> uvicorn nao reescreve o client. Spoof de XFF por um peer
        # arbitrario nao engana a chave.
        monkeypatch.setenv("TRUSTED_PROXIES", _PEER_PROXY)
        app = _montar_app_proxy()
        client = TestClient(app, client=(_PEER_NAO_CONFIAVEL, 51000))

        resp = client.get("/ip", headers={"X-Forwarded-For": "198.51.100.7"})

        assert resp.status_code == 200
        assert resp.json()["client"] == _PEER_NAO_CONFIAVEL

    def test_proxy_que_repassa_xff_do_cliente_e_burlavel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # CAVEAT CAPTURADO (NAO e propriedade desejada): documenta executavelmente
        # POR QUE o proxy confiavel DEVE adicionar (append)/sobrescrever o
        # X-Forwarded-For com o IP real do cliente. Aqui simulamos um proxy
        # MAL CONFIGURADO que REPASSA, sem append, um XFF de UM unico hop enviado
        # pelo cliente: o peer e confiavel, mas a unica entrada do XFF e
        # controlada pelo atacante. Como uvicorn devolve a entrada mais a direita
        # NAO-confiavel, request.client vira o IP forjado -> rotacionar o XFF
        # forjado abre buckets SEPARADOS -> o limite E burlavel nesse misconfig.
        # A defesa (append/overwrite no proxy) esta documentada no configmap.yaml
        # e na ADR-023; este teste existe para travar o entendimento do caveat.
        monkeypatch.setenv("TRUSTED_PROXIES", _PEER_PROXY)
        app = _montar_app_proxy(limite="2/minute")
        client = TestClient(app, client=(_PEER_PROXY, 51000))

        # Single hop forjado: a chave do limiter passa a ser o IP que o atacante
        # escolheu, nao o peer confiavel.
        forjado_1 = {"X-Forwarded-For": "198.51.100.250"}
        resp = client.get("/ip", headers=forjado_1)
        assert resp.status_code == 200
        assert resp.json()["client"] == "198.51.100.250"

        # Gasta o limite (2/minute) do IP forjado_1 -> 3a barrada (429).
        assert client.get("/ip", headers=forjado_1).status_code == 200
        assert client.get("/ip", headers=forjado_1).status_code == 429

        # Rotacionar o XFF forjado abre um bucket NOVO (limite contornado) ->
        # 200 de novo. Com o proxy fazendo append/overwrite isto seria impossivel.
        forjado_2 = {"X-Forwarded-For": "198.51.100.251"}
        assert client.get("/ip", headers=forjado_2).status_code == 200
        assert client.get("/ip", headers=forjado_2).status_code == 200

    def test_cidr_confiavel_chaveia_pelo_cliente_real(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Forma de PRODUCAO: TRUSTED_PROXIES como CIDR (faixa do ingress). O peer
        # 10.1.2.3 esta dentro de 10.0.0.0/8 -> confiavel -> o XFF e honrado e a
        # chave vira o IP real do cliente. Prova o match por CIDR ponta a ponta
        # (uvicorn resolve via ipaddress.ip_network).
        monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")
        app = _montar_app_proxy()
        client = TestClient(app, client=("10.1.2.3", 51000))

        resp = client.get("/ip", headers={"X-Forwarded-For": "203.0.113.7"})

        assert resp.status_code == 200
        assert resp.json()["client"] == "203.0.113.7"

    def test_ipv6_cidr_confiavel_chaveia_pelo_cliente_real(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # IPv6: TRUSTED_PROXIES como CIDR v6 (2001:db8::/32), peer v6 dentro da
        # faixa e cliente v6 no XFF -> a chave vira o cliente v6. Prova que o
        # caminho v6 funciona ponta a ponta no harness (TestClient aceita a
        # string v6 no client=; uvicorn casa via ipaddress.ip_network v6).
        monkeypatch.setenv("TRUSTED_PROXIES", "2001:db8::/32")
        app = _montar_app_proxy()
        client = TestClient(app, client=("2001:db8::1", 51000))

        resp = client.get("/ip", headers={"X-Forwarded-For": "2001:db8:abcd::42"})

        assert resp.status_code == 200
        assert resp.json()["client"] == "2001:db8:abcd::42"


class TestCriarAppRealOrdemProxyHeadersSlowAPI:
    """TD-023 (regressao de ORDEM): exercita o ``criar_app`` REAL, nao um app
    minimo que espelha a ordem manualmente.

    A propriedade critica de seguranca e que, na pilha real, o
    ``ProxyHeadersMiddleware`` roda ANTES do ``SlowAPIMiddleware`` no request:
    so assim o ``request.client`` ja foi reescrito pelo XFF confiavel quando o
    rate limiter le ``request.client.host`` como chave. As demais provas de
    proxy neste arquivo usam ``_montar_app_proxy`` (app minimo que IMITA a
    ordem de ``criar_app``); se alguem reordenar os ``configurar_*`` em
    ``src/main.py:criar_app``, aqueles testes seguem verdes e a regressao passa
    silenciosa. Este teste fecha essa lacuna driblando o ``criar_app`` de
    verdade.
    """

    def test_criar_app_real_proxyheaders_antes_do_slowapi(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TRUSTED_PROXIES setado ANTES de criar_app: assim
        # configurar_proxy_headers instala o ProxyHeadersMiddleware na pilha
        # real (default vazio -> nao instalaria).
        monkeypatch.setenv("TRUSTED_PROXIES", _PEER_PROXY)

        # O singleton ``limiter`` do modulo congela seu limite default em tempo
        # de import (60/minute), inviavel para um teste deterministico. Troca-se
        # por um Limiter de limite BAIXO (2/minute) ANTES de criar_app: o
        # composition root le ``mw.limiter`` em ``configurar_rate_limiting`` e o
        # mesmo objeto vira ``app.state.limiter`` lido pelo SlowAPIMiddleware,
        # entao a troca propaga de ponta a ponta.
        #
        # ROTA usada: ``/x-proxy`` — adicionada DEPOIS de criar_app no app real
        # (rotas registradas apos a montagem do middleware ainda atravessam toda
        # a pilha, SlowAPI incluso). Sem ``@limiter.limit`` proprio e sem
        # ``@limiter.exempt`` e sem tocar dependencia alguma, logo governada SO
        # pelos ``default_limits`` — o caminho do limiter de middleware keyed por
        # ``get_remote_address``, isolado de DB/JWT. ``/api/v1/saude`` NAO serve
        # mais aqui: ela e isenta do rate limit (issue #81), entao nunca daria o
        # 429 que esta regressao de ORDEM precisa observar.
        import src.compartilhado.interfaces.middleware as mw

        limiter_baixo = Limiter(
            key_func=get_remote_address, default_limits=["2/minute"]
        )
        # ``saude`` segue isenta com o limiter de teste (reusa o registro do
        # singleton real, preenchido pelo decorator ``@limiter.exempt`` no
        # import de ``router_publico``).
        limiter_baixo._exempt_routes = mw.limiter._exempt_routes
        monkeypatch.setattr(mw, "limiter", limiter_baixo)

        # Importa criar_app DEPOIS dos patches (env + singleton) para que a
        # fabrica monte a pilha real com o proxy-headers ativo e o limite baixo.
        from src.main import criar_app

        app = criar_app()
        # Sanidade: a fabrica realmente instalou o limiter de teste (mesma
        # instancia que os decorators e o middleware compartilham).
        assert app.state.limiter is limiter_baixo

        rota = "/x-proxy"

        @app.get(rota)
        def _x_proxy() -> dict[str, str]:
            return {"status": "ok"}

        # Peer = proxy confiavel; o XFF carrega o IP do cliente real.
        client = TestClient(app, client=(_PEER_PROXY, 12345))
        cliente_a = {"X-Forwarded-For": "198.51.100.7"}
        cliente_b = {"X-Forwarded-For": "198.51.100.8"}

        # Cliente A gasta o limite (2/minute) e e barrado no 3o.
        assert client.get(rota, headers=cliente_a).status_code == 200
        assert client.get(rota, headers=cliente_a).status_code == 200
        assert client.get(rota, headers=cliente_a).status_code == 429

        # Cliente B, atras do MESMO proxy confiavel, cai em bucket SEPARADO ->
        # 200, 200. Isso so e possivel se o ProxyHeadersMiddleware ja reescreveu
        # request.client a partir do XFF ANTES do SlowAPIMiddleware ler a chave,
        # na PILHA REAL. Se alguem mover ``configurar_proxy_headers`` para ANTES
        # de ``configurar_rate_limiting`` em criar_app (proxy-headers passa a
        # rodar DEPOIS do SlowAPI), a chave volta a ser o IP do peer, A e B
        # compartilham o bucket do peer e o cliente B ja viria 429 aqui ->
        # ESTE TESTE FALHA, capturando a regressao.
        assert client.get(rota, headers=cliente_b).status_code == 200
        assert client.get(rota, headers=cliente_b).status_code == 200

    def test_criar_app_real_sem_trusted_proxies_nao_instala_proxyheaders(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Espelho do default SEGURO na pilha REAL: sem TRUSTED_PROXIES o
        # ProxyHeadersMiddleware NAO e instalado (XFF ignorado, sem spoof).
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)

        from src.main import criar_app

        app = criar_app()
        nomes = [getattr(m.cls, "__name__", "") for m in app.user_middleware]
        assert "ProxyHeadersMiddleware" not in nomes
        # SlowAPI segue presente: o rate limiting nao depende do proxy-headers.
        assert "SlowAPIMiddleware" in nomes


class TestSaudeIsentaDeRateLimit:
    """Issue #81: ``/api/v1/saude`` (probe de liveness E readiness do kubelet)
    DEVE estar isenta do rate limit global.

    Todas as probes do kubelet saem de um unico IP (o no), que e a chave do
    limiter (``key_func=get_remote_address``). Sob HPA, com varios pods, o
    agregado de probes do mesmo IP estouraria o limite global (``60/minute``)
    -> o kubelet receberia 429 no health check -> o pod seria morto e
    reiniciado (restart storm auto-reforcante, confirmado ao vivo com 5 pods).

    A prova exercita o ``criar_app`` REAL com um limite default BAIXO e bate em
    ``/api/v1/saude`` MUITAS vezes (bem alem do limite) do MESMO cliente: tudo
    200, nunca 429. O contraste (rota governada pelos mesmos ``default_limits``
    AINDA toma 429) garante que o limiter segue ATIVO — a isencao e cirurgica,
    so para a saude.
    """

    _ROTA_CONTROLE = "/x-rate-limited"

    def _criar_app_limite_baixo(
        self, monkeypatch: pytest.MonkeyPatch, *, limite: str = "3/minute"
    ) -> FastAPI:
        """``criar_app`` REAL com ``default_limits`` baixo + uma rota de
        CONTROLE (``/x-rate-limited``) governada por esses defaults.

        O singleton ``limiter`` do modulo congela seu default em tempo de import
        (60/minute), inviavel para um teste deterministico. Troca-se por um
        Limiter de limite BAIXO ANTES de criar_app: o composition root le
        ``mw.limiter`` em ``configurar_rate_limiting`` e o mesmo objeto vira
        ``app.state.limiter`` lido pelo SlowAPIMiddleware. O ``@limiter.exempt``
        em ``saude()`` registra a rota no ``_exempt_routes`` do singleton REAL
        (o decorator roda no import de ``router_publico``, ja importado); o
        ``_exempt_routes`` e reaproveitado no limiter de teste para a isencao
        seguir valendo.

        A rota de controle e adicionada DEPOIS de ``criar_app`` (no app real):
        rotas registradas apos a montagem do middleware ainda atravessam toda a
        pilha (SlowAPIMiddleware incluso). Ela nao tem ``@limiter.limit`` proprio
        nem ``@limiter.exempt`` e nao toca dependencia alguma (sem DB/JWT), logo
        e governada SO pelos ``default_limits`` — o caminho exato do limiter de
        middleware keyed por ``get_remote_address``, isolado de side effects.
        """
        monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
        import src.compartilhado.interfaces.middleware as mw

        limiter_baixo = Limiter(key_func=get_remote_address, default_limits=[limite])
        limiter_baixo._exempt_routes = mw.limiter._exempt_routes
        monkeypatch.setattr(mw, "limiter", limiter_baixo)

        from src.main import criar_app

        app = criar_app()
        assert app.state.limiter is limiter_baixo

        @app.get(self._ROTA_CONTROLE)
        def _x_rate_limited() -> dict[str, str]:
            return {"status": "ok"}

        return app

    def test_saude_isenta_nunca_retorna_429_do_mesmo_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        limite = 3
        app = self._criar_app_limite_baixo(monkeypatch, limite=f"{limite}/minute")
        # Cliente unico (mesmo IP, como o kubelet de um no): todas as probes
        # compartilham a chave do limiter.
        client = TestClient(app, client=("10.244.0.1", 51000))

        # Bate bem alem do limite (limite + 5). Sem a isencao, a partir da
        # (limite+1)-esima request viria 429 (o que matava o pod).
        for _ in range(limite + 5):
            resp = client.get("/api/v1/saude")
            assert resp.status_code == 200, (
                f"esperado 200 em /api/v1/saude (isenta), obtido {resp.status_code}"
            )
            assert resp.json() == {"status": "ok"}

    def test_rota_nao_isenta_ainda_rate_limita_provando_limiter_ativo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # CONTRASTE: uma rota governada pelos MESMOS ``default_limits`` (sem
        # ``@limiter.limit`` proprio e sem ``@limiter.exempt``) AINDA toma 429
        # passado o limite. Isso prova que o limiter esta ATIVO na pilha real e
        # que a isencao de ``/saude`` e cirurgica, nao um desligamento global.
        limite = 3
        app = self._criar_app_limite_baixo(monkeypatch, limite=f"{limite}/minute")
        client = TestClient(app, client=("10.244.0.1", 51000))

        # As primeiras ``limite`` requests passam (200);
        for _ in range(limite):
            assert client.get(self._ROTA_CONTROLE).status_code == 200
        # a (limite+1)-esima estoura o default -> 429 (limiter ativo).
        assert client.get(self._ROTA_CONTROLE).status_code == 429
