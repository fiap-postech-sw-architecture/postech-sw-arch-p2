"""Integracao da persistencia duravel de eventos de transicao via outbox (RF-024).

Exercita ``IniciarDiagnostico`` real (repositorio SQLAlchemy + UnitOfWork
real) e prova que:

- a transicao de status e o registro na outbox sao commitados juntos na
  MESMA transacao (garantia de ordering: estado + evento atomicos);
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
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.infraestrutura.outbox_mapping import outbox_table
from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
from src.ordem_servico.aplicacao.use_cases import IniciarDiagnostico
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
        _contato=Contato(valor=contato),
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
    def test_transicao_enfileira_evento_na_outbox_no_mesmo_commit(
        self, sessao: Session
    ) -> None:
        """Prova que status 'em_diagnostico' e o registro na outbox sao atomicos.

        O status da OS e o registro na outbox compartilham o mesmo COMMIT
        (garantia de ordering do fluxo outbox). A consulta e feita na MESMA
        session/connection que o UoW usou — fora dela os dados nao seriam
        visiveis, pois a fixture sessao usa savepoint+rollback.
        """
        ordem = _seed_ordem_recebida(sessao)

        uc = IniciarDiagnostico(
            repo=OrdemDeServicoSQLAlchemyRepository(session=sessao),
            uow=SQLAlchemyUnitOfWork(session_factory=lambda: sessao),
            dispatcher=EventDispatcher(handlers=()),
        )
        uc.executar(ordem.id)

        # 1. O status da OS ja esta persistido (estado commitado).
        assert _status_no_banco(sessao, ordem.id) == "em_diagnostico"

        # 2. O mesmo commit gravou exatamente um registro na outbox para
        #    esse agregado, com tipo e status corretos (durabilidade RF-024).
        linhas = sessao.execute(
            outbox_table.select().where(outbox_table.c.agregado_id == ordem.id)
        ).all()
        assert len(linhas) == 1
        assert linhas[0].tipo == "DiagnosticoIniciadoEvent"
        assert linhas[0].status == "pendente"

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
