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


def _headers_admin(api_client: TestClient, admin_user: Usuario) -> dict[str, str]:
    resposta_login = api_client.post(
        "/api/v1/autenticacao/login",
        json={"email": admin_user.email, "senha": _SENHA_ADMIN},
    )
    assert resposta_login.status_code == 200
    token = resposta_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _criar_cliente(
    api_client: TestClient,
    headers: dict[str, str],
    *,
    nome: str,
    documento: str,
) -> dict[str, object]:
    resposta = api_client.post(
        "/api/v1/clientes/",
        headers=headers,
        json={
            "nome": nome,
            "documento": documento,
            "tipo_documento": "cpf",
            "contato": "11999990000",
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def _adicionar_veiculo(
    api_client: TestClient,
    headers: dict[str, str],
    *,
    cliente_id: str,
    placa: str,
) -> dict[str, object]:
    resposta = api_client.post(
        f"/api/v1/clientes/{cliente_id}/veiculos",
        headers=headers,
        json={
            "placa": placa,
            "marca": "Fiat",
            "modelo": "Uno",
            "ano": 2020,
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


@pytest.fixture
def session_factory(
    engine: Engine,
) -> Generator[sessionmaker[Session]]:
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
) -> Generator[TestClient]:
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


class TestFluxoOrdemClienteVeiculo:
    """Fluxos cross-context que precisam validar consistencia cliente-veiculo."""

    def test_criar_ordem_rejeita_veiculo_de_outro_cliente(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        headers = _headers_admin(api_client, admin_user)
        cliente_a = _criar_cliente(
            api_client,
            headers,
            nome="Cliente A",
            documento="21249722519",
        )
        cliente_b = _criar_cliente(
            api_client,
            headers,
            nome="Cliente B",
            documento="57648016648",
        )
        veiculo_b = _adicionar_veiculo(
            api_client,
            headers,
            cliente_id=str(cliente_b["id"]),
            placa="DEF5678",
        )

        resposta = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente_a["id"], "veiculo_id": veiculo_b["id"]},
        )

        assert resposta.status_code == 404
        assert (
            resposta.json()["erro"]["mensagem"]
            == "Veiculo nao encontrado para o cliente informado"
        )

    def test_remover_veiculo_com_os_entregue_retorna_409(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        session_factory: sessionmaker[Session],
    ) -> None:
        from sqlalchemy import text

        headers = _headers_admin(api_client, admin_user)
        cliente = _criar_cliente(
            api_client,
            headers,
            nome="Cliente com historico",
            documento="93214407473",
        )
        veiculo = _adicionar_veiculo(
            api_client,
            headers,
            cliente_id=str(cliente["id"]),
            placa="GHI9012",
        )
        resposta_os = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente["id"], "veiculo_id": veiculo["id"]},
        )
        assert resposta_os.status_code == 201
        ordem_id = resposta_os.json()["id"]

        with session_factory() as sess:
            sess.execute(
                text(
                    "UPDATE ordens_de_servico "
                    "SET status = 'entregue' "
                    "WHERE id = :ordem_id"
                ),
                {"ordem_id": ordem_id},
            )
            sess.commit()

        resposta_delete = api_client.delete(
            f"/api/v1/clientes/{cliente['id']}/veiculos/{veiculo['id']}",
            headers=headers,
        )

        assert resposta_delete.status_code == 409
        assert (
            resposta_delete.json()["erro"]["mensagem"]
            == "Veiculo possui ordem de servico vinculada e nao pode ser removido"
        )

    def test_get_ordem_e_listagem_resolvem_cliente_nome_e_veiculo_placa(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        """Detalhe e listagem entregam ``cliente_nome`` e ``veiculo_placa`` resolvidos.

        Reproduz o fluxo da UI (``ui/paginas/ordens_servico.py``): ao
        clicar numa OS, a UI le ``ordem.get('cliente_nome')`` e
        ``ordem.get('veiculo_placa')`` do response. Antes do
        enriquecimento server-side via ``ClientePort`` esses campos
        nao existiam no response e a UI mostrava ``-``.
        """
        headers = _headers_admin(api_client, admin_user)
        cliente = _criar_cliente(
            api_client,
            headers,
            nome="Maria Silva",
            documento="21249722519",
        )
        veiculo = _adicionar_veiculo(
            api_client,
            headers,
            cliente_id=str(cliente["id"]),
            placa="ABC1234",
        )

        resposta_criar = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente["id"], "veiculo_id": veiculo["id"]},
        )
        assert resposta_criar.status_code == 201
        ordem_id = resposta_criar.json()["id"]

        resposta_detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        )
        assert resposta_detalhe.status_code == 200
        detalhe = resposta_detalhe.json()
        assert detalhe["cliente_nome"] == "Maria Silva"
        assert detalhe["veiculo_placa"] == "ABC1234"

        resposta_lista = api_client.get("/api/v1/ordens-de-servico/", headers=headers)
        assert resposta_lista.status_code == 200
        item = next(i for i in resposta_lista.json()["items"] if i["id"] == ordem_id)
        assert item["cliente_nome"] == "Maria Silva"
        assert item["veiculo_placa"] == "ABC1234"
