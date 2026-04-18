"""Testes de integracao E2E do fluxo auth + catalogo de servicos.

Exerce o caminho completo da API (login -> POST /servicos -> GET /servicos)
usando FastAPI TestClient contra PostgreSQL real via testcontainers. Protege
contra regressoes de wiring do session factory no lifespan e outros bugs que
mocks com SimpleNamespace nao capturam.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.password_hasher import hash_senha
from src.autenticacao.infraestrutura.repository import (
    UsuarioSQLAlchemyRepository,
)
from src.main import criar_app

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integracao

_SENHA_ADMIN = "senhaforte1234"
_EMAIL_ADMIN = "admin-e2e@test.com"
# Tabelas truncadas no teardown para evitar poluicao entre testes. A ordem
# respeita FKs (dependentes antes de referenciados). Inclui todos os contextos
# ativos no app.
_TABELAS_TRUNCATE = (
    "itens_da_ordem",
    "ordens_de_servico",
    "servicos_oferecidos",
    "itens_estoque",
    "consentimentos",
    "veiculos",
    "clientes",
    "tokens_revogados",
    "usuarios",
)


@pytest.fixture
def session_factory(
    engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    from sqlalchemy import text

    from src.compartilhado.infraestrutura.database import criar_session_factory

    factory = criar_session_factory(engine)
    yield factory

    # Testes E2E fazem commit real atraves do TestClient. O fixture `session`
    # (SAVEPOINT rollback) nao alcanca essas transacoes, entao limpamos
    # explicitamente para nao vazar dados entre testes.
    with factory() as sess:
        for tabela in _TABELAS_TRUNCATE:
            sess.execute(text(f"TRUNCATE TABLE {tabela} CASCADE"))
        sess.commit()


@pytest.fixture
def admin_user(
    session_factory: sessionmaker[Session],
) -> Usuario:
    """Semeia um usuario admin para autenticacao."""
    with session_factory() as sess:
        repo = UsuarioSQLAlchemyRepository(session=sess)
        usuario = Usuario.criar(
            email=_EMAIL_ADMIN,
            senha_hash=hash_senha(_SENHA_ADMIN),
            papel=Papel.ADMIN,
        )
        repo.salvar(usuario)
        sess.commit()
    return usuario


@pytest.fixture
def api_client(
    engine: Engine,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """Cria um TestClient apontando para o banco de teste.

    Configura `DATABASE_URL` e `JWT_SECRET` antes de instanciar o app. O
    lifespan real se encarrega de criar o engine e registrar a session
    factory, garantindo que o teste E2E exerca exatamente o mesmo wiring
    que ``docker compose up`` -- se o bug do session factory voltar, esses
    testes quebram.
    """
    monkeypatch.setenv(
        "JWT_SECRET",
        "test-secret-at-least-32-bytes-long-for-hs256-signing",
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    app: FastAPI = criar_app()

    with TestClient(app) as client:
        yield client


class TestFluxoAuthCriacaoListagem:
    """Fluxo completo: login -> cria servico -> lista -> obtem por id."""

    def test_login_com_credenciais_validas_retorna_tokens(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        resposta = api_client.post(
            "/api/v1/autenticacao/login",
            json={"email": admin_user.email, "senha": _SENHA_ADMIN},
        )

        assert resposta.status_code == 200
        dados = resposta.json()
        assert "access_token" in dados
        assert "refresh_token" in dados
        assert dados["token_type"] == "bearer"

    def test_login_com_senha_invalida_retorna_401(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        resposta = api_client.post(
            "/api/v1/autenticacao/login",
            json={"email": admin_user.email, "senha": "senhaerrada1234"},
        )

        assert resposta.status_code == 401

    def test_criar_servico_sem_token_retorna_401(self, api_client: TestClient) -> None:
        resposta = api_client.post(
            "/api/v1/servicos/",
            json={
                "nome": "Troca de oleo",
                "descricao": "Troca completa",
                "preco": "150.00",
            },
        )

        assert resposta.status_code == 401

    def test_fluxo_completo_login_criar_listar_obter(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        # 1. Login -> token de acesso.
        resposta_login = api_client.post(
            "/api/v1/autenticacao/login",
            json={"email": admin_user.email, "senha": _SENHA_ADMIN},
        )
        assert resposta_login.status_code == 200
        token = resposta_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Criar servico -> 201 + body completo.
        resposta_criacao = api_client.post(
            "/api/v1/servicos/",
            headers=headers,
            json={
                "nome": "Alinhamento",
                "descricao": "Alinhamento completo das rodas",
                "preco": "89.90",
            },
        )
        assert resposta_criacao.status_code == 201
        servico_criado = resposta_criacao.json()
        assert servico_criado["nome"] == "Alinhamento"
        assert servico_criado["descricao"] == "Alinhamento completo das rodas"
        assert servico_criado["preco"] == "89.90"
        assert servico_criado["moeda"] == "BRL"
        assert servico_criado["ativo"] is True
        assert "id" in servico_criado

        # 3. Listar servicos -> paginacao com o item recem criado.
        resposta_listagem = api_client.get("/api/v1/servicos/", headers=headers)
        assert resposta_listagem.status_code == 200
        lista = resposta_listagem.json()
        assert lista["total"] >= 1
        ids = {item["id"] for item in lista["items"]}
        assert servico_criado["id"] in ids

        # 4. Obter servico especifico -> 200 + mesmo id.
        resposta_obter = api_client.get(
            f"/api/v1/servicos/{servico_criado['id']}", headers=headers
        )
        assert resposta_obter.status_code == 200
        assert resposta_obter.json()["id"] == servico_criado["id"]

    def test_token_invalido_retorna_401(self, api_client: TestClient) -> None:
        resposta = api_client.get(
            "/api/v1/servicos/",
            headers={"Authorization": "Bearer token-invalido-123"},
        )
        assert resposta.status_code == 401
