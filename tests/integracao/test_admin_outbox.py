"""Integracao dos endpoints admin da DLQ da outbox (RF-018 / router_admin).

Cobre a superficie HTTP auth-gated do ``router_admin`` ponta a ponta via
``TestClient`` contra Postgres real (testcontainers): autorizacao por papel
(admin vs nao-admin vs anonimo), o shape do GET ``/dead`` (inclui
``tem_sucessores_pendentes``, F4) e o contrato do POST ``reenfileirar``
(``dead`` -> ``pendente``/tentativas 0; 404 fora desse estado).

O ``router_admin`` constroi seu proprio Engine a partir de ``DATABASE_URL``
(cache de modulo). O fixture ``api_client`` aponta ``DATABASE_URL`` para o
banco de teste, entao o endpoint le/escreve a MESMA outbox que semeamos pelo
``engine`` da sessao. As linhas ``dead`` sao inseridas via Core (isola o
teste da UoW) e limpas no teardown.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import structlog
import structlog.testing
from fastapi.testclient import TestClient
from sqlalchemy import text

import src.compartilhado.interfaces.router_admin as router_admin_modulo
from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.password_hasher import hash_senha
from src.autenticacao.infraestrutura.repository import UsuarioSQLAlchemyRepository
from src.main import criar_app

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integracao


@pytest.fixture(autouse=True)
def _logger_fresco(monkeypatch: pytest.MonkeyPatch) -> None:
    # capture_logs nao intercepta o `_log` module-level ja cacheado quando
    # outro teste bootou o app antes (configurar_logging usa
    # cache_logger_on_first_use=True). Um proxy novo por teste torna o capture
    # do audit de reenfileiramento deterministico em qualquer ordem da suite.
    monkeypatch.setattr(
        router_admin_modulo, "_log", structlog.get_logger("test_admin_outbox")
    )


_SENHA = "senhaforte1234"
_EMAIL_ADMIN = "admin-dlq@test.com"
_EMAIL_ATENDENTE = "atendente-dlq@test.com"


@pytest.fixture
def session_factory(engine: Engine) -> Generator[sessionmaker[Session]]:
    from src.compartilhado.infraestrutura.database import criar_session_factory

    factory = criar_session_factory(engine)
    yield factory
    # Limpa usuarios e a outbox (commits reais via TestClient/Core nao sao
    # alcancados pelo rollback de SAVEPOINT do fixture `session`).
    with factory() as sess:
        sess.execute(text("DELETE FROM processed_events"))
        sess.execute(text("DELETE FROM outbox"))
        sess.execute(text("TRUNCATE TABLE tokens_revogados CASCADE"))
        sess.execute(text("TRUNCATE TABLE usuarios CASCADE"))
        sess.commit()


def _criar_usuario(
    session_factory: sessionmaker[Session], *, email: str, papel: Papel
) -> Usuario:
    with session_factory() as sess:
        repo = UsuarioSQLAlchemyRepository(session=sess)
        usuario = Usuario.criar(email=email, senha_hash=hash_senha(_SENHA), papel=papel)
        repo.salvar(usuario)
        sess.commit()
    return usuario


@pytest.fixture
def admin_user(session_factory: sessionmaker[Session]) -> Usuario:
    return _criar_usuario(session_factory, email=_EMAIL_ADMIN, papel=Papel.ADMIN)


@pytest.fixture
def atendente_user(session_factory: sessionmaker[Session]) -> Usuario:
    """Usuario autenticado SEM papel admin (atendente) — deve receber 403."""
    return _criar_usuario(
        session_factory, email=_EMAIL_ATENDENTE, papel=Papel.ATENDENTE
    )


@pytest.fixture
def api_client(
    engine: Engine,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient]:
    monkeypatch.setenv(
        "JWT_SECRET", "test-secret-at-least-32-bytes-long-for-hs256-signing"
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    app: FastAPI = criar_app()
    with TestClient(app) as client:
        yield client


def _headers(api_client: TestClient, usuario: Usuario) -> dict[str, str]:
    resposta = api_client.post(
        "/api/v1/autenticacao/login",
        json={"email": usuario.email, "senha": _SENHA},
    )
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def _inserir_dead(
    engine: Engine,
    *,
    agregado_id: UUID | None = None,
    tipo: str = "DiagnosticoIniciadoEvent",
    tentativas: int = 5,
) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em, ultimo_erro) "
                "VALUES (:aid, :tipo, CAST(:p AS JSONB), 'dead', :t, :agora, "
                ":agora, 'boom') RETURNING id"
            ),
            {
                "aid": agregado_id or uuid4(),
                "tipo": tipo,
                "p": '{"agregado_id": "x"}',
                "t": tentativas,
                "agora": datetime.now(UTC),
            },
        ).first()
    return int(row.id)


def _inserir_pendente(engine: Engine, *, agregado_id: UUID) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em) "
                "VALUES (:aid, 'OrcamentoGeradoEvent', CAST(:p AS JSONB), "
                "'pendente', 0, :agora, :agora) RETURNING id"
            ),
            {
                "aid": agregado_id,
                "p": '{"agregado_id": "x"}',
                "agora": datetime.now(UTC),
            },
        ).first()
    return int(row.id)


def _status(engine: Engine, outbox_id: int) -> tuple[str, int]:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT status, tentativas FROM outbox WHERE id = :id"),
            {"id": outbox_id},
        ).first()
    return row.status, row.tentativas


class TestAutorizacaoListarDlq:
    """GET /api/v1/admin/outbox/dead exige papel admin."""

    def test_sem_token_retorna_401(self, api_client: TestClient) -> None:
        assert api_client.get("/api/v1/admin/outbox/dead").status_code == 401

    def test_nao_admin_retorna_403(
        self, api_client: TestClient, atendente_user: Usuario
    ) -> None:
        headers = _headers(api_client, atendente_user)
        resposta = api_client.get("/api/v1/admin/outbox/dead", headers=headers)
        assert resposta.status_code == 403

    def test_admin_retorna_200_com_shape_esperado(
        self, api_client: TestClient, admin_user: Usuario, engine: Engine
    ) -> None:
        # Um dead "limpo" (sem sucessor) e um dead com sucessor pendente do
        # mesmo agregado (F4: tem_sucessores_pendentes=True).
        id_limpo = _inserir_dead(engine)
        agregado_com_gap = uuid4()
        id_com_gap = _inserir_dead(engine, agregado_id=agregado_com_gap)
        _inserir_pendente(engine, agregado_id=agregado_com_gap)

        headers = _headers(api_client, admin_user)
        resposta = api_client.get("/api/v1/admin/outbox/dead", headers=headers)

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert isinstance(corpo, list)
        por_id = {linha["id"]: linha for linha in corpo}
        assert {id_limpo, id_com_gap} <= set(por_id)

        alvo = por_id[id_limpo]
        # Shape do listar_dead (router delega a outbox_dlq.listar_dead).
        assert set(alvo) == {
            "id",
            "agregado_id",
            "tipo",
            "tentativas",
            "ultimo_erro",
            "criado_em",
            "status",
            "tem_sucessores_pendentes",
        }
        assert alvo["status"] == "dead"
        assert alvo["tipo"] == "DiagnosticoIniciadoEvent"
        assert alvo["tem_sucessores_pendentes"] is False
        assert por_id[id_com_gap]["tem_sucessores_pendentes"] is True


class TestAutorizacaoReenfileirar:
    """POST /api/v1/admin/outbox/dead/{id}/reenfileirar exige papel admin."""

    def test_sem_token_retorna_401(
        self, api_client: TestClient, engine: Engine
    ) -> None:
        outbox_id = _inserir_dead(engine)
        resposta = api_client.post(
            f"/api/v1/admin/outbox/dead/{outbox_id}/reenfileirar"
        )
        assert resposta.status_code == 401
        # Nenhuma mutacao sem autorizacao: a linha continua dead.
        assert _status(engine, outbox_id)[0] == "dead"

    def test_nao_admin_retorna_403(
        self, api_client: TestClient, atendente_user: Usuario, engine: Engine
    ) -> None:
        outbox_id = _inserir_dead(engine)
        headers = _headers(api_client, atendente_user)
        resposta = api_client.post(
            f"/api/v1/admin/outbox/dead/{outbox_id}/reenfileirar", headers=headers
        )
        assert resposta.status_code == 403
        assert _status(engine, outbox_id)[0] == "dead"


class TestReenfileirarContrato:
    """Contrato funcional do reenfileiramento (admin autenticado)."""

    def test_reenfileira_dead_volta_para_pendente_zera_tentativas(
        self, api_client: TestClient, admin_user: Usuario, engine: Engine
    ) -> None:
        outbox_id = _inserir_dead(engine, tentativas=5)
        headers = _headers(api_client, admin_user)

        resposta = api_client.post(
            f"/api/v1/admin/outbox/dead/{outbox_id}/reenfileirar", headers=headers
        )

        assert resposta.status_code == 200
        assert resposta.json() == {"reenfileirado": True, "id": outbox_id}
        assert _status(engine, outbox_id) == ("pendente", 0)

    def test_reenfileira_emite_audit_com_ator_e_outbox_id(
        self, api_client: TestClient, admin_user: Usuario, engine: Engine
    ) -> None:
        # Acao que muta estado (ressuscita um dead) deve deixar trilha de
        # auditoria: QUEM (o admin autenticado, via `sub`=id do JWT) e QUAL
        # `outbox_id`. Captura o log estruturado em volta do POST.
        outbox_id = _inserir_dead(engine, tentativas=5)
        headers = _headers(api_client, admin_user)

        with structlog.testing.capture_logs() as logs:
            resposta = api_client.post(
                f"/api/v1/admin/outbox/dead/{outbox_id}/reenfileirar", headers=headers
            )

        assert resposta.status_code == 200
        auditorias = [
            log for log in logs if log.get("event") == "outbox_reenfileirado_via_admin"
        ]
        assert len(auditorias) == 1, logs
        evento = auditorias[0]
        assert evento["outbox_id"] == outbox_id
        # O ator e o `sub` do JWT = id do usuario admin que se autenticou.
        assert evento["ator"] == str(admin_user.id)

    def test_reenfileira_id_inexistente_nao_emite_audit(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        # 404 (linha nao-dead/inexistente): nada mutou, nenhum audit emitido.
        headers = _headers(api_client, admin_user)
        with structlog.testing.capture_logs() as logs:
            resposta = api_client.post(
                "/api/v1/admin/outbox/dead/99999999/reenfileirar", headers=headers
            )
        assert resposta.status_code == 404
        assert not any(
            log.get("event") == "outbox_reenfileirado_via_admin" for log in logs
        )

    def test_reenfileira_id_inexistente_retorna_404(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        headers = _headers(api_client, admin_user)
        resposta = api_client.post(
            "/api/v1/admin/outbox/dead/99999999/reenfileirar", headers=headers
        )
        assert resposta.status_code == 404

    def test_reenfileira_linha_nao_dead_retorna_404(
        self, api_client: TestClient, admin_user: Usuario, engine: Engine
    ) -> None:
        # Linha existe mas NAO esta em 'dead' (pendente): o UPDATE com
        # `AND status='dead'` nao afeta linha -> contrato 404.
        outbox_id = _inserir_pendente(engine, agregado_id=uuid4())
        headers = _headers(api_client, admin_user)
        resposta = api_client.post(
            f"/api/v1/admin/outbox/dead/{outbox_id}/reenfileirar", headers=headers
        )
        assert resposta.status_code == 404
        # Continua pendente, intocada.
        assert _status(engine, outbox_id) == ("pendente", 0)
