"""Integracao do dispatch pos-commit de eventos de transicao (RF-024).

Exercita ``IniciarDiagnostico`` real (repositorio SQLAlchemy + UnitOfWork
real) com handlers fake registrados no ``EventDispatcher``:

- o handler recebe o evento DEPOIS do commit — provado lendo o status da
  OS direto da tabela no momento da chamada do handler;
- falha do handler nao afeta a transicao ja persistida (aceite RF-024);
- ``ClienteSQLAlchemyAdapter.obter_contato`` resolve nome + contato do
  cliente real (cross-context via port, sem tocar o dominio vizinho).

Usa uma session propria com ``expire_on_commit=False`` (espelho de
``criar_session_factory``) porque os casos de uso leem atributos do
agregado apos ``uow.commit()`` + fechamento da session — com o default
``expire_on_commit=True`` da fixture compartilhada o acesso pos-commit
levantaria ``DetachedInstanceError``, um falso negativo de wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
from src.ordem_servico.aplicacao.use_cases import IniciarDiagnostico
from src.ordem_servico.dominio.events import DiagnosticoIniciadoEvent
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.infraestrutura.adapters import ClienteSQLAlchemyAdapter
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from uuid import UUID

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integracao


@pytest.fixture
def sessao(engine: Engine) -> Generator[Session]:
    from sqlalchemy.orm import Session as SASession

    connection = engine.connect()
    transaction = connection.begin()
    sess = SASession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    yield sess

    sess.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


def _seed_cliente_com_veiculo(
    sessao: Session, *, contato: str = "maria@cliente.com"
) -> tuple[UUID, UUID]:
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    cliente = Cliente(
        _nome="Maria Notificada",
        _documento=CPF(numero="21249722519"),
        _contato=contato,
    )
    ClienteSQLAlchemyRepository(session=sessao).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor="EML1234"), marca="Fiat", modelo="Uno", ano=2020
    )
    sessao.flush()
    return cliente.id, cliente.veiculos[0].id


def _seed_ordem_recebida(sessao: Session) -> OrdemDeServico:
    cliente_id, veiculo_id = _seed_cliente_com_veiculo(sessao)
    ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
    ordem.limpar_eventos()
    OrdemDeServicoSQLAlchemyRepository(session=sessao).salvar(ordem)
    sessao.flush()
    return ordem


def _status_no_banco(sessao: Session, ordem_id: UUID) -> str | None:
    linha = sessao.execute(
        text("SELECT status FROM ordens_de_servico WHERE id = :id"),
        {"id": ordem_id},
    ).first()
    return None if linha is None else str(linha.status)


class TestDispatchPosCommitComBancoReal:
    def test_handler_recebe_evento_apos_commit_e_ve_ordem_persistida(
        self, sessao: Session
    ) -> None:
        ordem = _seed_ordem_recebida(sessao)
        visto: list[tuple[type, str | None]] = []

        def handler(evento: object) -> None:
            # Prova de ordem: no momento da notificacao, a linha da OS ja
            # esta com o status novo persistido (commit aconteceu antes).
            visto.append((type(evento), _status_no_banco(sessao, ordem.id)))

        uc = IniciarDiagnostico(
            repo=OrdemDeServicoSQLAlchemyRepository(session=sessao),
            uow=SQLAlchemyUnitOfWork(session_factory=lambda: sessao),
            dispatcher=EventDispatcher(handlers=(handler,)),
        )
        uc.executar(ordem.id)

        assert visto == [(DiagnosticoIniciadoEvent, "em_diagnostico")]

    def test_falha_do_handler_nao_desfaz_a_transicao_persistida(
        self, sessao: Session
    ) -> None:
        ordem = _seed_ordem_recebida(sessao)

        def handler_quebrado(_evento: object) -> None:
            raise RuntimeError("notificacao indisponivel")

        uc = IniciarDiagnostico(
            repo=OrdemDeServicoSQLAlchemyRepository(session=sessao),
            uow=SQLAlchemyUnitOfWork(session_factory=lambda: sessao),
            dispatcher=EventDispatcher(handlers=(handler_quebrado,)),
        )
        result = uc.executar(ordem.id)

        assert result.status == "em_diagnostico"
        assert _status_no_banco(sessao, ordem.id) == "em_diagnostico"


class TestObterContatoComBancoReal:
    def test_resolve_nome_e_contato_do_cliente(self, sessao: Session) -> None:
        cliente_id, _ = _seed_cliente_com_veiculo(
            sessao, contato="Maria - maria@cliente.com"
        )

        dto = ClienteSQLAlchemyAdapter(session=sessao).obter_contato(cliente_id)

        assert dto is not None
        assert dto.id == cliente_id
        assert dto.nome == "Maria Notificada"
        assert dto.contato == "Maria - maria@cliente.com"

    def test_cliente_inexistente_retorna_none(self, sessao: Session) -> None:
        assert ClienteSQLAlchemyAdapter(session=sessao).obter_contato(uuid4()) is None
