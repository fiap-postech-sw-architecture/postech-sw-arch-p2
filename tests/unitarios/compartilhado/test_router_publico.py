from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import structlog.testing
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.compartilhado.interfaces import router_publico
from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter


def _criar_app() -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router_publico.router)
    # Stub da session para os testes — nao e usada no mock do use case.
    # codeql[py/unnecessary-lambda] -- FastAPI dependency_overrides exige o lambda
    app.dependency_overrides[obter_session] = lambda: MagicMock()
    return app


class TestRouterPublico:
    def test_saude(self) -> None:
        app = _criar_app()
        client = TestClient(app)
        resp = client.get("/api/v1/saude")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_acompanhamento_encontrado(self) -> None:
        """Happy path: use case retorna DTO -> 200 + AcompanhamentoResponse."""
        app = _criar_app()
        dto_ns = SimpleNamespace(
            status="em_execucao",
            criado_em=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
            atualizado_em=datetime(2026, 4, 1, 15, 30, tzinfo=UTC),
        )
        with patch(
            "src.ordem_servico.interfaces.dependencies.obter_consultar_acompanhamento"
        ) as factory:
            factory.return_value = MagicMock(executar=MagicMock(return_value=dto_ns))
            client = TestClient(app)
            # POST com placa/documento no corpo (issue #180: PII fora da URL).
            resp = client.post(
                "/api/v1/acompanhamento",
                json={"placa": "ABC1D23", "documento": "12345678901"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "em_execucao"
            # RF-021: a consulta publica tambem informa `situacao` no
            # vocabulario do challenge ao lado do `status` tecnico.
            assert body["situacao"] == "Em execução"
            assert "criado_em" in body
            assert "atualizado_em" in body

    def test_acompanhamento_nao_encontrado_retorna_404(self) -> None:
        """Miss case: use case retorna None -> 404 (evita oracle attack)."""
        app = _criar_app()
        with patch(
            "src.ordem_servico.interfaces.dependencies.obter_consultar_acompanhamento"
        ) as factory:
            factory.return_value = MagicMock(executar=MagicMock(return_value=None))
            client = TestClient(app)
            resp = client.post(
                "/api/v1/acompanhamento",
                json={"placa": "XYZ0A00", "documento": "00000000000"},
            )
            assert resp.status_code == 404
            assert resp.json() == {"detail": "Ordem nao encontrada"}

    def test_acompanhamento_placa_documento_nunca_na_url(self) -> None:
        """PII (placa/documento) viaja no corpo, nunca em query param (#180)."""
        app = _criar_app()
        client = TestClient(app)
        # GET com os dados na URL nao existe mais -> 405 Method Not Allowed.
        resp = client.get(
            "/api/v1/acompanhamento",
            params={"placa": "ABC1D23", "documento": "12345678901"},
        )
        assert resp.status_code == 405

    def test_acompanhamento_sem_corpo_retorna_422(self) -> None:
        """Corpo faltando -> 422 (validation error do FastAPI)."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.post("/api/v1/acompanhamento")
        assert resp.status_code == 422

    def test_acompanhamento_placa_muito_curta_retorna_422(self) -> None:
        """Placa < 7 chars rejeitada via ``Field(min_length=7)``."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/acompanhamento",
            json={"placa": "AB1", "documento": "12345678901"},
        )
        assert resp.status_code == 422

    def test_acompanhamento_documento_muito_curto_retorna_422(self) -> None:
        """Documento < 11 chars rejeitado via ``Field(min_length=11)``."""
        app = _criar_app()
        client = TestClient(app)
        resp = client.post(
            "/api/v1/acompanhamento",
            json={"placa": "ABC1D23", "documento": "123"},
        )
        assert resp.status_code == 422


class TestDecisaoOrcamentoExterna:
    """RF-022 (TD-027): endpoint externo de decisao do orcamento.

    Autenticacao por assinatura HMAC por requisicao (``X-Webhook-Signature`` +
    ``X-Webhook-Timestamp``, TD-027 -- evolui o token estatico da ADR-021)
    validada ANTES de tocar o caso de uso -- os cenarios 401/503 afirmam que a
    factory nem chega a ser invocada (non-effect).
    """

    _ROTA = "/api/v1/publico/ordens-de-servico/{oid}/decisao-orcamento"
    _FACTORY = "src.ordem_servico.interfaces.dependencies.obter_decidir_orcamento"

    @pytest.fixture
    def token_configurado(self, monkeypatch: pytest.MonkeyPatch) -> str:
        valor = "demo-webhook-orcamento-unit"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", valor)
        return valor

    def _dto(self, status: str) -> SimpleNamespace:
        return SimpleNamespace(
            status=status,
            criado_em=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
            atualizado_em=datetime(2026, 6, 12, 15, 30, tzinfo=UTC),
        )

    @staticmethod
    def _headers_assinados(
        ordem_id: object,
        segredo: str,
        corpo: bytes,
        *,
        timestamp: str | None = None,
    ) -> dict[str, str]:
        import time

        from src.compartilhado.infraestrutura.webhook_signature import (
            assinar_payload_webhook,
        )

        ts = timestamp if timestamp is not None else str(int(time.time()))
        return {
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": ts,
            "X-Webhook-Signature": assinar_payload_webhook(
                segredo, str(ordem_id), ts, corpo
            ),
        }

    def _post(
        self, app: FastAPI, ordem_id: object, body: dict[str, object], segredo: str
    ) -> object:
        import json

        corpo = json.dumps(body).encode("utf-8")
        return TestClient(app).post(
            self._ROTA.format(oid=ordem_id),
            content=corpo,
            headers=self._headers_assinados(ordem_id, segredo, corpo),
        )

    def test_aprovada_com_assinatura_valida_retorna_situacao_nova(
        self, token_configurado: str
    ) -> None:
        app = _criar_app()
        ordem_id = uuid4()
        uc = MagicMock(executar=MagicMock(return_value=self._dto("em_execucao")))
        with patch(self._FACTORY) as factory:
            factory.return_value = uc
            resp = self._post(app, ordem_id, {"decisao": "aprovada"}, token_configurado)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "em_execucao"
        assert body["situacao"] == "Em execução"
        uc.executar.assert_called_once_with(ordem_id, decisao="aprovada")

    def test_recusada_com_assinatura_valida_retorna_cancelada(
        self, token_configurado: str
    ) -> None:
        app = _criar_app()
        uc = MagicMock(executar=MagicMock(return_value=self._dto("cancelada")))
        with patch(self._FACTORY) as factory:
            factory.return_value = uc
            resp = self._post(app, uuid4(), {"decisao": "recusada"}, token_configurado)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelada"
        assert body["situacao"] == "Cancelada"

    def test_sem_assinatura_retorna_401_sem_tocar_use_case(
        self, token_configurado: str
    ) -> None:
        app = _criar_app()
        with patch(self._FACTORY) as factory:
            resp = TestClient(app).post(
                self._ROTA.format(oid=uuid4()),
                json={"decisao": "aprovada"},
            )
        assert resp.status_code == 401
        factory.assert_not_called()

    def test_assinatura_com_segredo_errado_retorna_401(
        self, token_configurado: str
    ) -> None:
        app = _criar_app()
        with patch(self._FACTORY) as factory:
            # Assina com segredo diferente do configurado no servidor.
            resp = self._post(app, uuid4(), {"decisao": "aprovada"}, "outro-valor")
        assert resp.status_code == 401
        factory.assert_not_called()

    def test_timestamp_fora_da_janela_retorna_401(self, token_configurado: str) -> None:
        import json

        app = _criar_app()
        ordem_id = uuid4()
        corpo = json.dumps({"decisao": "aprovada"}).encode("utf-8")
        with patch(self._FACTORY) as factory:
            resp = TestClient(app).post(
                self._ROTA.format(oid=ordem_id),
                content=corpo,
                headers=self._headers_assinados(
                    ordem_id, token_configurado, corpo, timestamp="1000000000"
                ),
            )
        assert resp.status_code == 401
        factory.assert_not_called()

    def test_assinatura_nao_ascii_retorna_401(self, token_configurado: str) -> None:
        # BUG #171: compare_digest com STR nao-ASCII levanta TypeError -> 500.
        # Comparando em bytes, um header forjado com nao-ASCII e apenas uma
        # assinatura divergente -> 401. O valor vai em BYTES latin-1 (httpx
        # exige ASCII em header str); o Starlette decodifica latin-1 e o
        # handler recebe a str nao-ASCII.
        import json

        app = _criar_app()
        ordem_id = uuid4()
        corpo = json.dumps({"decisao": "aprovada"}).encode("utf-8")
        headers = self._headers_assinados(ordem_id, token_configurado, corpo)
        headers_forjados: dict[str, str | bytes] = {
            **headers,
            "X-Webhook-Signature": "assinatura-inválida-ñ".encode("latin-1"),
        }
        with patch(self._FACTORY) as factory:
            resp = TestClient(app).post(
                self._ROTA.format(oid=ordem_id),
                content=corpo,
                headers=headers_forjados,  # type: ignore[arg-type]
            )
        assert resp.status_code == 401
        factory.assert_not_called()

    def test_timestamp_nao_numerico_retorna_401(self, token_configurado: str) -> None:
        import json

        app = _criar_app()
        ordem_id = uuid4()
        corpo = json.dumps({"decisao": "aprovada"}).encode("utf-8")
        with patch(self._FACTORY) as factory:
            resp = TestClient(app).post(
                self._ROTA.format(oid=ordem_id),
                content=corpo,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Timestamp": "nao-numerico",
                    "X-Webhook-Signature": "deadbeef",
                },
            )
        assert resp.status_code == 401
        factory.assert_not_called()

    def test_segredo_nao_configurado_no_servidor_retorna_503(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Ausencia de configuracao = canal externo desabilitado (503), nunca
        # canal aberto sem credencial.
        monkeypatch.delenv("ORCAMENTO_WEBHOOK_TOKEN", raising=False)
        app = _criar_app()
        with patch(self._FACTORY) as factory:
            resp = self._post(app, uuid4(), {"decisao": "aprovada"}, "qualquer")
        assert resp.status_code == 503
        factory.assert_not_called()

    def test_decisao_invalida_retorna_422(self, token_configurado: str) -> None:
        app = _criar_app()
        resp = self._post(app, uuid4(), {"decisao": "talvez"}, token_configurado)
        assert resp.status_code == 422

    def test_payload_com_campo_extra_retorna_422(self, token_configurado: str) -> None:
        app = _criar_app()
        resp = self._post(
            app, uuid4(), {"decisao": "aprovada", "motivo": "x"}, token_configurado
        )
        assert resp.status_code == 422

    def test_rejeicao_loga_motivo_sem_vazar_assinatura(
        self, token_configurado: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Assinar com o segredo errado -> assinatura divergente -> 401. A
        # rejeicao emite `webhook_auth_falhou` com `motivo` generico + `ordem_id`,
        # e a assinatura recebida NUNCA aparece nos logs.
        #
        # `_log` fresco por teste: com cache_logger_on_first_use=True (setado por
        # configurar_logging em outro teste da sessao), capture_logs nao intercepta
        # o `_log` module-level ja cacheado. Um proxy novo torna o capture
        # deterministico em qualquer ordem da suite.
        monkeypatch.setattr(
            router_publico, "_log", structlog.get_logger("test_webhook_auth")
        )
        app = _criar_app()
        ordem_id = uuid4()
        with structlog.testing.capture_logs() as logs, patch(self._FACTORY):
            resp = self._post(app, ordem_id, {"decisao": "aprovada"}, "outro-valor")
        assert resp.status_code == 401
        eventos = [log for log in logs if log.get("event") == "webhook_auth_falhou"]
        assert len(eventos) == 1, logs
        evento = eventos[0]
        assert evento["motivo"] == "assinatura_divergente"
        assert evento["ordem_id"] == ordem_id
        # A assinatura recebida (HMAC do segredo errado) nao vaza para o log.
        assinatura_recebida = self._headers_assinados(
            ordem_id, "outro-valor", b'{"decisao": "aprovada"}'
        )["X-Webhook-Signature"]
        assert assinatura_recebida not in str(logs)

    def test_ordem_id_nao_uuid_retorna_422(self, token_configurado: str) -> None:
        app = _criar_app()
        resp = self._post(app, "nao-e-uuid", {"decisao": "aprovada"}, token_configurado)
        assert resp.status_code == 422
