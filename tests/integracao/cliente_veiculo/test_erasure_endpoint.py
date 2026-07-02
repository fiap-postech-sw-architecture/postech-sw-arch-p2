"""Erasure LGPD ponta-a-ponta pelo ENDPOINT (RBAC + anonimização em DB real).

Fecha a lacuna que deixou o #76 (erasure -> admin-only) quebrar o harness E2E
sem o gate rápido pegar: os testes de endpoint (unit, mockados) validavam o
403/204 e os de repositório validavam a anonimização, mas nada exercia o
caminho COMPLETO `DELETE HTTP -> use case -> repositório -> DB` numa suíte que
roda no gate local. Aqui os dois se juntam contra Postgres real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.autenticacao.interfaces.middleware import obter_usuario_atual
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.documento_anonimizado import DocumentoAnonimizado
from src.cliente_veiculo.dominio.placa import Placa
from src.cliente_veiculo.dominio.placa_anonimizada import PlacaAnonimizada
from src.cliente_veiculo.infraestrutura.repository import ClienteSQLAlchemyRepository
from src.cliente_veiculo.interfaces.router import router
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _app_com_papel(session: Session, papel: str) -> FastAPI:
    """App com a sessão REAL e o papel do usuário injetados por override."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[obter_session] = lambda: session
    app.dependency_overrides[obter_usuario_atual] = lambda: {
        "sub": str(uuid4()),
        "papel": papel,
    }
    return app


def _criar_cliente_com_veiculo(session: Session) -> tuple[UUID, UUID]:
    """Cria + persiste cliente com 1 veículo; retorna (cliente_id, veiculo_id).

    Os ids são capturados em memória ANTES do ``salvar`` (que faz commit e
    expira o agregado) — assim o teste trabalha com UUIDs puros e recarrega o
    estado do banco por consulta fresca, sem tocar instância detachada.
    """
    repo = ClienteSQLAlchemyRepository(session=session)
    cliente = Cliente(
        _nome="Joao Silva",
        _documento=CPF(numero="21249722519"),
        _contato=Contato(valor="11999990000"),
    )
    cliente.adicionar_veiculo(
        placa=Placa(valor="ABC1234"), marca="Fiat", modelo="Uno", ano=2020
    )
    cliente_id, veiculo_id = cliente.id, cliente.veiculos[0].id
    repo.salvar(cliente)
    return cliente_id, veiculo_id


class TestErasureEndpointAnonimiza:
    def test_admin_apaga_e_anonimiza_cliente_e_veiculo(self, session: Session) -> None:
        """Admin -> 204 e a anonimização (documento + cascata de placa) acontece
        de fato no banco, com as linhas/FK preservadas (#72 + #76)."""
        cliente_id, veiculo_id = _criar_cliente_com_veiculo(session)

        resp = TestClient(_app_com_papel(session, "admin")).delete(
            f"/api/v1/clientes/{cliente_id}/dados-pessoais"
        )

        assert resp.status_code == 204
        session.expire_all()
        resultado = ClienteSQLAlchemyRepository(session=session).obter_por_id(
            cliente_id
        )
        assert resultado is not None
        # Documento (PII) anonimizado; a linha do cliente é preservada (ativo=False).
        assert isinstance(resultado.documento, DocumentoAnonimizado)
        assert resultado.ativo is False
        # Cascata: a placa do veículo é neutralizada, com veiculo_id intacto
        # (FK ordens_de_servico.veiculo_id continua válida).
        veiculo = resultado.veiculos[0]
        assert isinstance(veiculo.placa, PlacaAnonimizada)
        assert veiculo.id == veiculo_id

    def test_atendente_recebe_403_e_nao_anonimiza(self, session: Session) -> None:
        """Atendente -> 403 e NADA é anonimizado (o erasure admin-only não roda);
        guarda de regressão para o caso que o harness pegou tarde."""
        cliente_id, _ = _criar_cliente_com_veiculo(session)

        resp = TestClient(_app_com_papel(session, "atendente")).delete(
            f"/api/v1/clientes/{cliente_id}/dados-pessoais"
        )

        assert resp.status_code == 403
        session.expire_all()
        resultado = ClienteSQLAlchemyRepository(session=session).obter_por_id(
            cliente_id
        )
        assert resultado is not None
        # Dados originais intactos: nada foi anonimizado.
        assert not isinstance(resultado.documento, DocumentoAnonimizado)
        assert resultado.ativo is True
        assert not isinstance(resultado.veiculos[0].placa, PlacaAnonimizada)
