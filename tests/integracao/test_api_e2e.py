"""Testes de integracao E2E do fluxo auth + catalogo de servicos.

Exerce o caminho completo da API (login -> POST /servicos -> GET /servicos)
usando FastAPI TestClient contra PostgreSQL real via testcontainers. Protege
contra regressoes de wiring do session factory no lifespan e outros bugs que
mocks com SimpleNamespace nao capturam.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from uuid import uuid4

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


def _criar_servico(
    api_client: TestClient,
    headers: dict[str, str],
    *,
    nome: str,
    preco: str,
) -> dict[str, object]:
    resposta = api_client.post(
        "/api/v1/servicos/",
        headers=headers,
        json={"nome": nome, "descricao": f"{nome} (e2e)", "preco": preco},
    )
    assert resposta.status_code == 201
    return resposta.json()


def _criar_item_estoque(
    api_client: TestClient,
    headers: dict[str, str],
    *,
    nome: str,
    quantidade: int,
    preco_unitario: str,
) -> dict[str, object]:
    resposta = api_client.post(
        "/api/v1/estoque/",
        headers=headers,
        json={
            "nome": nome,
            "descricao": f"{nome} (e2e)",
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
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

    def test_consulta_de_status_retorna_situacao_do_challenge(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        """RF-021: detalhe e listagem informam ``situacao`` no vocabulario
        do challenge; ``status`` tecnico snake_case permanece intacto.

        Exercita uma transicao real (diagnostico) para garantir que o
        rotulo acentuado atravessa a serializacao JSON do response.
        """
        headers = _headers_admin(api_client, admin_user)
        cliente = _criar_cliente(
            api_client,
            headers,
            nome="Cliente Consulta Status",
            documento="57648016648",
        )
        veiculo = _adicionar_veiculo(
            api_client,
            headers,
            cliente_id=str(cliente["id"]),
            placa="JKL3456",
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
        assert detalhe["status"] == "recebida"
        assert detalhe["situacao"] == "Recebida"

        resposta_diagnostico = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico", headers=headers
        )
        assert resposta_diagnostico.status_code == 200
        assert resposta_diagnostico.json()["situacao"] == "Em diagnóstico"

        resposta_detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        )
        assert resposta_detalhe.status_code == 200
        detalhe = resposta_detalhe.json()
        assert detalhe["status"] == "em_diagnostico"
        assert detalhe["situacao"] == "Em diagnóstico"

        resposta_lista = api_client.get("/api/v1/ordens-de-servico/", headers=headers)
        assert resposta_lista.status_code == 200
        item = next(i for i in resposta_lista.json()["items"] if i["id"] == ordem_id)
        assert item["situacao"] == "Em diagnóstico"


class TestCriacaoOsComItens:
    """RF-020: abertura de OS recebendo servicos e pecas num unico POST.

    Exercita o caminho completo contra PostgreSQL real: criacao atomica
    (itens na mesma transacao), erro de dominio sem efeito colateral
    (OS nao persiste) e a interacao dos itens criados na abertura com a
    reserva de estoque da aprovacao (ADR-008, all-or-nothing).
    """

    def _setup_cliente_veiculo(
        self, api_client: TestClient, headers: dict[str, str], documento: str
    ) -> tuple[str, str]:
        cliente = _criar_cliente(
            api_client, headers, nome="Cliente RF020", documento=documento
        )
        veiculo = _adicionar_veiculo(
            api_client, headers, cliente_id=str(cliente["id"]), placa="RFA0020"
        )
        return str(cliente["id"]), str(veiculo["id"])

    def test_post_com_servicos_e_pecas_cria_os_completa(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        headers = _headers_admin(api_client, admin_user)
        cliente_id, veiculo_id = self._setup_cliente_veiculo(
            api_client, headers, documento="21249722519"
        )
        troca = _criar_servico(
            api_client, headers, nome="Troca de oleo", preco="100.00"
        )
        alinhamento = _criar_servico(
            api_client, headers, nome="Alinhamento", preco="80.00"
        )
        filtro = _criar_item_estoque(
            api_client,
            headers,
            nome="Filtro de oleo",
            quantidade=10,
            preco_unitario="35.00",
        )

        resposta = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "servicos": [
                    {"servico_catalogo_id": troca["id"]},
                    {"servico_catalogo_id": alinhamento["id"], "quantidade": 2},
                ],
                "pecas": [
                    {
                        "servico_catalogo_id": troca["id"],
                        "item_estoque_id": filtro["id"],
                        "quantidade": 2,
                    }
                ],
            },
        )

        assert resposta.status_code == 201
        criada = resposta.json()
        assert criada["status"] == "recebida"
        assert criada["situacao"] == "Recebida"
        assert len(criada["itens"]) == 3

        # Detalhe persistido reflete os itens com preco da fonte certa.
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{criada['id']}", headers=headers
        ).json()
        assert len(detalhe["itens"]) == 3
        linha_peca = next(
            i for i in detalhe["itens"] if i["item_estoque_id"] == filtro["id"]
        )
        assert linha_peca["preco_unitario_centavos"] == 3500  # preco do ESTOQUE
        assert linha_peca["subtotal_centavos"] == 7000
        assert linha_peca["descricao"] == "Filtro de oleo"
        assert linha_peca["item_estoque_nome"] == "Filtro de oleo"
        linha_alinhamento = next(
            i for i in detalhe["itens"] if i["descricao"] == "Alinhamento"
        )
        assert linha_alinhamento["item_estoque_id"] is None
        assert linha_alinhamento["subtotal_centavos"] == 16000
        assert linha_alinhamento["servico_nome"] == "Alinhamento"

    def test_post_com_peca_inexistente_nao_cria_os(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        headers = _headers_admin(api_client, admin_user)
        cliente_id, veiculo_id = self._setup_cliente_veiculo(
            api_client, headers, documento="57648016648"
        )
        troca = _criar_servico(
            api_client, headers, nome="Troca de oleo", preco="100.00"
        )

        resposta = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "servicos": [{"servico_catalogo_id": troca["id"]}],
                "pecas": [
                    {
                        "servico_catalogo_id": troca["id"],
                        "item_estoque_id": str(uuid4()),
                        "quantidade": 1,
                    }
                ],
            },
        )

        assert resposta.status_code == 409
        assert resposta.json()["erro"]["mensagem"] == "Item de estoque nao encontrado"
        # Rollback total: nenhuma OS persistida (nem com o servico valido).
        listagem = api_client.get(
            "/api/v1/ordens-de-servico/?incluir_encerradas=true", headers=headers
        ).json()
        assert listagem["total"] == 0

    def test_post_sem_itens_mantem_comportamento_fase_1(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        headers = _headers_admin(api_client, admin_user)
        cliente_id, veiculo_id = self._setup_cliente_veiculo(
            api_client, headers, documento="93214407473"
        )

        resposta = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente_id, "veiculo_id": veiculo_id},
        )

        assert resposta.status_code == 201
        criada = resposta.json()
        assert criada["status"] == "recebida"
        assert criada["itens"] == []
        assert criada["orcamento"] is None

    def test_aprovacao_de_os_criada_com_pecas_respeita_saldo_com_rollback(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        """Peca com quantidade > saldo: a criacao nao reserva estoque
        (reserva acontece na aprovacao, ADR-008), entao o POST cria a OS;
        a aprovacao falha com o erro atual de estoque insuficiente e faz
        rollback all-or-nothing — a peca com saldo suficiente NAO fica
        reservada e a OS permanece aguardando aprovacao.
        """
        headers = _headers_admin(api_client, admin_user)
        cliente_id, veiculo_id = self._setup_cliente_veiculo(
            api_client, headers, documento="21249722519"
        )
        troca = _criar_servico(
            api_client, headers, nome="Troca de oleo", preco="100.00"
        )
        filtro = _criar_item_estoque(
            api_client,
            headers,
            nome="Filtro de oleo",
            quantidade=10,
            preco_unitario="35.00",
        )
        vela = _criar_item_estoque(
            api_client,
            headers,
            nome="Vela de ignicao",
            quantidade=1,
            preco_unitario="20.00",
        )

        resposta = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "pecas": [
                    {
                        "servico_catalogo_id": troca["id"],
                        "item_estoque_id": filtro["id"],
                        "quantidade": 2,
                    },
                    {
                        "servico_catalogo_id": troca["id"],
                        "item_estoque_id": vela["id"],
                        "quantidade": 5,  # > saldo (1)
                    },
                ],
            },
        )
        assert resposta.status_code == 201
        ordem_id = resposta.json()["id"]

        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico", headers=headers
            ).status_code
            == 200
        )
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/orcamento", headers=headers
            ).status_code
            == 200
        )

        resposta_aprovacao = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao", headers=headers
        )

        assert resposta_aprovacao.status_code == 409
        assert "insuficiente" in resposta_aprovacao.json()["erro"]["mensagem"]
        # Rollback total da aprovacao: o filtro (saldo suficiente) nao
        # ficou reservado e a ordem nao avancou de status.
        saldo_filtro = api_client.get(
            f"/api/v1/estoque/{filtro['id']}", headers=headers
        ).json()["quantidade"]
        assert saldo_filtro == 10
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "aguardando_aprovacao"

    def test_orcamento_complementar_cobra_item_extra_em_execucao(
        self, api_client: TestClient, admin_user: Usuario
    ) -> None:
        """#80 e2e: em EM_EXECUCAO adicionar peca extra reserva estoque e o
        orcamento complementar cobra o trabalho extra (total > original)."""
        headers = _headers_admin(api_client, admin_user)
        cliente_id, veiculo_id = self._setup_cliente_veiculo(
            api_client, headers, documento="93214407473"
        )
        troca = _criar_servico(api_client, headers, nome="Troca", preco="100.00")
        filtro = _criar_item_estoque(
            api_client, headers, nome="Filtro", quantidade=10, preco_unitario="35.00"
        )
        vela = _criar_item_estoque(
            api_client, headers, nome="Vela", quantidade=5, preco_unitario="20.00"
        )
        ordem_id = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={
                "cliente_id": cliente_id,
                "veiculo_id": veiculo_id,
                "pecas": [
                    {
                        "servico_catalogo_id": troca["id"],
                        "item_estoque_id": filtro["id"],
                        "quantidade": 2,
                    }
                ],
            },
        ).json()["id"]
        api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico", headers=headers
        )
        api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/orcamento", headers=headers
        )
        total_original = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()["orcamento"]["total_centavos"]
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao", headers=headers
            ).status_code
            == 200
        )
        # EM_EXECUCAO: adicionar a vela extra retorna 201 (antes era 409) e
        # reserva 1 unidade na hora (saldo 5 -> 4).
        r_add = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/itens",
            headers=headers,
            json={
                "servico_catalogo_id": troca["id"],
                "item_estoque_id": vela["id"],
                "descricao": "Vela extra",
                "quantidade": 1,
            },
        )
        assert r_add.status_code == 201
        saldo_vela = api_client.get(
            f"/api/v1/estoque/{vela['id']}", headers=headers
        ).json()["quantidade"]
        assert saldo_vela == 4
        # O orcamento complementar cobra o item extra: total cresce.
        r_comp = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/orcamento-complementar",
            headers=headers,
        )
        assert r_comp.status_code == 200
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "aguardando_aprovacao_complementar"
        assert detalhe["orcamento"]["total_centavos"] > total_original


class TestDecisaoExternaOrcamento:
    """RF-022 (ADR-021): decisao externa de orcamento contra Postgres real.

    Cobre as quatro transicoes do canal externo (aprovada/recusada x
    inicial/complementar), a autenticacao por ``X-Webhook-Token`` e os
    erros padrao (401, 404, 409, 422, 503). O token e lido do ambiente a
    cada request, entao ``monkeypatch.setenv`` depois do app criado vale.
    """

    def _rota(self, ordem_id: object) -> str:
        return f"/api/v1/publico/ordens-de-servico/{ordem_id}/decisao-orcamento"

    def _criar_os_aguardando_aprovacao(
        self,
        api_client: TestClient,
        headers: dict[str, str],
        *,
        documento: str,
        placa: str,
        item_estoque_id: str | None = None,
        quantidade_peca: int = 2,
    ) -> str:
        """Cria OS com 1 servico (e opcionalmente 1 peca) e leva ate
        AGUARDANDO_APROVACAO pelos endpoints internos."""
        cliente = _criar_cliente(
            api_client, headers, nome="Cliente RF022", documento=documento
        )
        veiculo = _adicionar_veiculo(
            api_client, headers, cliente_id=str(cliente["id"]), placa=placa
        )
        servico = _criar_servico(
            api_client, headers, nome="Revisao geral", preco="200.00"
        )
        payload: dict[str, object] = {
            "cliente_id": cliente["id"],
            "veiculo_id": veiculo["id"],
            "servicos": [{"servico_catalogo_id": servico["id"]}],
        }
        if item_estoque_id is not None:
            payload["pecas"] = [
                {
                    "servico_catalogo_id": servico["id"],
                    "item_estoque_id": item_estoque_id,
                    "quantidade": quantidade_peca,
                }
            ]
        resposta = api_client.post(
            "/api/v1/ordens-de-servico/", headers=headers, json=payload
        )
        assert resposta.status_code == 201
        ordem_id = str(resposta.json()["id"])
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico", headers=headers
            ).status_code
            == 200
        )
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/orcamento", headers=headers
            ).status_code
            == 200
        )
        return ordem_id

    def test_aprovada_transita_para_em_execucao(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        credencial = "e2e-webhook-aprovacao"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        headers = _headers_admin(api_client, admin_user)
        ordem_id = self._criar_os_aguardando_aprovacao(
            api_client, headers, documento="21249722519", placa="RFB0022"
        )

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "aprovada"},
            headers={"X-Webhook-Token": credencial},
        )

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "em_execucao"
        assert corpo["situacao"] == "Em execução"
        # Resposta publica nao vaza dados internos da OS (LGPD).
        assert "cliente_id" not in corpo
        assert "itens" not in corpo
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "em_execucao"

    def test_recusada_cancela_a_ordem(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        credencial = "e2e-webhook-recusa"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        headers = _headers_admin(api_client, admin_user)
        ordem_id = self._criar_os_aguardando_aprovacao(
            api_client, headers, documento="57648016648", placa="RFC0022"
        )

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "recusada"},
            headers={"X-Webhook-Token": credencial},
        )

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "cancelada"
        assert corpo["situacao"] == "Cancelada"
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "cancelada"

    def test_aprovada_com_complementar_pendente_volta_a_execucao(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        credencial = "e2e-webhook-complementar"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        headers = _headers_admin(api_client, admin_user)
        ordem_id = self._criar_os_aguardando_aprovacao(
            api_client, headers, documento="93214407473", placa="RFD0022"
        )
        # Aprovacao interna -> EM_EXECUCAO -> orcamento complementar.
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao", headers=headers
            ).status_code
            == 200
        )
        resposta_compl = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/orcamento-complementar",
            headers=headers,
        )
        assert resposta_compl.status_code == 200
        assert resposta_compl.json()["status"] == "aguardando_aprovacao_complementar"

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "aprovada"},
            headers={"X-Webhook-Token": credencial},
        )

        assert resposta.status_code == 200
        assert resposta.json()["status"] == "em_execucao"

    def test_recusada_com_complementar_pendente_cancela_e_libera_estoque(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ADR-021: recusa externa do complementar = desistencia total.

        A OS inteira vai a CANCELADA e a reserva de estoque feita na
        aprovacao do orcamento inicial e devolvida (CancelarOrdem).
        """
        credencial = "e2e-webhook-compl-recusa"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        headers = _headers_admin(api_client, admin_user)
        filtro = _criar_item_estoque(
            api_client,
            headers,
            nome="Filtro RF022",
            quantidade=10,
            preco_unitario="35.00",
        )
        ordem_id = self._criar_os_aguardando_aprovacao(
            api_client,
            headers,
            documento="21249722519",
            placa="RFE0022",
            item_estoque_id=str(filtro["id"]),
            quantidade_peca=2,
        )
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/aprovacao", headers=headers
            ).status_code
            == 200
        )
        saldo_reservado = api_client.get(
            f"/api/v1/estoque/{filtro['id']}", headers=headers
        ).json()["quantidade"]
        assert saldo_reservado == 8
        assert (
            api_client.post(
                f"/api/v1/ordens-de-servico/{ordem_id}/orcamento-complementar",
                headers=headers,
            ).status_code
            == 200
        )

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "recusada"},
            headers={"X-Webhook-Token": credencial},
        )

        assert resposta.status_code == 200
        assert resposta.json()["status"] == "cancelada"
        saldo_final = api_client.get(
            f"/api/v1/estoque/{filtro['id']}", headers=headers
        ).json()["quantidade"]
        assert saldo_final == 10

    def test_token_errado_retorna_401_e_nao_transita(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", "valor-correto-e2e")
        headers = _headers_admin(api_client, admin_user)
        ordem_id = self._criar_os_aguardando_aprovacao(
            api_client, headers, documento="57648016648", placa="RFF0022"
        )

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "aprovada"},
            headers={"X-Webhook-Token": "valor-errado"},
        )

        assert resposta.status_code == 401
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "aguardando_aprovacao"

    def test_token_nao_configurado_retorna_503(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ORCAMENTO_WEBHOOK_TOKEN", raising=False)
        resposta = api_client.post(
            self._rota(uuid4()),
            json={"decisao": "aprovada"},
            headers={"X-Webhook-Token": "qualquer"},
        )
        assert resposta.status_code == 503

    def test_ordem_inexistente_retorna_404_no_envelope_padrao(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        credencial = "e2e-webhook-404"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        resposta = api_client.post(
            self._rota(uuid4()),
            json={"decisao": "aprovada"},
            headers={"X-Webhook-Token": credencial},
        )
        assert resposta.status_code == 404
        assert "erro" in resposta.json()

    def test_decisao_invalida_retorna_422(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        credencial = "e2e-webhook-422"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        resposta = api_client.post(
            self._rota(uuid4()),
            json={"decisao": "talvez"},
            headers={"X-Webhook-Token": credencial},
        )
        assert resposta.status_code == 422

    def test_status_fora_de_espera_retorna_409(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """OS RECEBIDA: o guard do caso de uso impede a recusa externa de
        virar cancelamento generico (409 no envelope padrao)."""
        credencial = "e2e-webhook-409"
        monkeypatch.setenv("ORCAMENTO_WEBHOOK_TOKEN", credencial)
        headers = _headers_admin(api_client, admin_user)
        cliente = _criar_cliente(
            api_client, headers, nome="Cliente 409", documento="93214407473"
        )
        veiculo = _adicionar_veiculo(
            api_client, headers, cliente_id=str(cliente["id"]), placa="RFG0022"
        )
        resposta_criar = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente["id"], "veiculo_id": veiculo["id"]},
        )
        assert resposta_criar.status_code == 201
        ordem_id = resposta_criar.json()["id"]

        resposta = api_client.post(
            self._rota(ordem_id),
            json={"decisao": "recusada"},
            headers={"X-Webhook-Token": credencial},
        )

        assert resposta.status_code == 409
        assert "erro" in resposta.json()
        detalhe = api_client.get(
            f"/api/v1/ordens-de-servico/{ordem_id}", headers=headers
        ).json()
        assert detalhe["status"] == "recebida"


class TestNotificacaoEmailViaApi:
    """RF-024 (e2e leve): transicao via API enfileira notificacao duravel na outbox.

    Valida que a chamada POST /diagnostico persiste exatamente um registro
    na outbox com tipo 'DiagnosticoIniciadoEvent' e status 'pendente' para
    o agregado. A entrega efetiva ao destinatario de email (campo ``contato``
    do cliente) e verificada ao nivel do relay/handler em
    tests/integracao/relay/, nao aqui.
    """

    def test_transicao_via_api_enfileira_notificacao_na_outbox(
        self,
        api_client: TestClient,
        admin_user: Usuario,
        engine: Engine,
    ) -> None:
        from uuid import UUID

        from sqlalchemy import select

        from src.compartilhado.infraestrutura.outbox_mapping import outbox_table

        headers = _headers_admin(api_client, admin_user)
        resposta_cliente = api_client.post(
            "/api/v1/clientes/",
            headers=headers,
            json={
                "nome": "Maria Notificada",
                "documento": "21249722519",
                "tipo_documento": "cpf",
                "contato": "Maria - maria@cliente.com / (11) 99999-0000",
            },
        )
        assert resposta_cliente.status_code == 201
        cliente = resposta_cliente.json()
        veiculo = _adicionar_veiculo(
            api_client, headers, cliente_id=str(cliente["id"]), placa="EML5678"
        )
        resposta_criar = api_client.post(
            "/api/v1/ordens-de-servico/",
            headers=headers,
            json={"cliente_id": cliente["id"], "veiculo_id": veiculo["id"]},
        )
        assert resposta_criar.status_code == 201
        ordem_id = resposta_criar.json()["id"]

        resposta_diagnostico = api_client.post(
            f"/api/v1/ordens-de-servico/{ordem_id}/diagnostico", headers=headers
        )

        assert resposta_diagnostico.status_code == 200

        # A API faz commit real — a outbox deve ter exatamente um registro
        # pendente para este agregado (prova de enfileiramento durable RF-024).
        # A verificacao do destinatario de email correto (campo contato do
        # cliente) e responsabilidade do relay/handler (tests/integracao/relay/).
        with engine.connect() as conn:
            linhas = conn.execute(
                select(outbox_table).where(outbox_table.c.agregado_id == UUID(ordem_id))
            ).all()
        assert len(linhas) == 1
        assert linhas[0].tipo == "DiagnosticoIniciadoEvent"
        assert linhas[0].status == "pendente"
