from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect, select, text

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao


def test_tabelas_outbox_existem(engine: Engine) -> None:
    nomes = set(inspect(engine).get_table_names())
    assert "outbox" in nomes
    assert "processed_events" in nomes


def test_outbox_tem_colunas_esperadas(engine: Engine) -> None:
    colunas = {c["name"] for c in inspect(engine).get_columns("outbox")}
    assert colunas == {
        "id",
        "agregado_id",
        "tipo",
        "payload",
        "status",
        "tentativas",
        "proxima_tentativa_em",
        "criado_em",
        "entregue_em",
        "ultimo_erro",
    }


def _seed_cliente_veiculo(session) -> tuple:
    from src.cliente_veiculo.dominio.cliente import Cliente
    from src.cliente_veiculo.dominio.cpf import CPF
    from src.cliente_veiculo.dominio.placa import Placa
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    cliente = Cliente(
        _nome="Cli Outbox",
        _documento=CPF(numero="21249722519"),
        _contato="cli@x.com",
    )
    ClienteSQLAlchemyRepository(session=session).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor="OBX1234"), marca="Fiat", modelo="Uno", ano=2020
    )
    session.flush()
    return cliente.id, cliente.veiculos[0].id


def test_commit_de_transicao_grava_linha_na_outbox(engine) -> None:
    from sqlalchemy.orm import Session as SASession

    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
    from src.ordem_servico.infraestrutura.repository import (
        OrdemDeServicoSQLAlchemyRepository,
    )

    connection = engine.connect()
    transaction = connection.begin()
    session = SASession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        cliente_id, veiculo_id = _seed_cliente_veiculo(session)
        ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
        ordem.limpar_eventos()  # descarta OrdemCriadaEvent (nao e integration)
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        repo.salvar(ordem)
        session.flush()

        ordem.iniciar_diagnostico()  # emite DiagnosticoIniciadoEvent (IntegrationEvent)
        # eventos pendentes ANTES do commit (referencia para o assert pos-commit)
        eventos_antes = ordem.coletar_eventos()
        uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
        with uow:
            uow.commit()

        # Le via `connection` (a `session` foi fechada por `__exit__`, mas a
        # `connection`/transacao da fixture continua viva).
        linhas = connection.execute(
            text("SELECT tipo, status, tentativas FROM outbox WHERE agregado_id = :id"),
            {"id": ordem.id},
        ).all()
        assert len(linhas) == 1
        assert linhas[0].tipo == "DiagnosticoIniciadoEvent"
        assert linhas[0].status == "pendente"
        assert linhas[0].tentativas == 0
        # so o integration event saiu (DiagnosticoIniciadoEvent); como nao ha
        # domain event puro nesta transicao, o agregado fica sem eventos.
        assert all(
            type(ev).__name__ != "DiagnosticoIniciadoEvent"
            for ev in ordem.coletar_eventos()
        )
        assert len(ordem.coletar_eventos()) == len(eventos_antes) - 1
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


def test_autoflush_antes_do_commit_nao_perde_evento(engine) -> None:
    from sqlalchemy.orm import Session as SASession

    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
    from src.ordem_servico.infraestrutura.repository import (
        OrdemDeServicoSQLAlchemyRepository,
    )

    connection = engine.connect()
    transaction = connection.begin()
    session = SASession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
        autoflush=True,  # default; explicito para o cenario
    )
    try:
        cliente_id, veiculo_id = _seed_cliente_veiculo(session)
        ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
        ordem.limpar_eventos()  # descarta OrdemCriadaEvent
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        repo.salvar(ordem)
        ordem.iniciar_diagnostico()  # IntegrationEvent pendente no agregado

        uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
        with uow:
            # Qualquer query dispara autoflush: a `ordem` (nova) e gravada e
            # SAI de `session.new`. Como nao a re-modificamos, ela tambem NAO
            # entra em `session.dirty`. A varredura antiga a perderia aqui.
            session.execute(select(OrdemDeServico).limit(1)).all()
            uow.commit()

        linhas = connection.execute(
            text("SELECT tipo FROM outbox WHERE agregado_id = :id"),
            {"id": ordem.id},
        ).all()
        # Com a coleta via identity_map, o evento foi pra outbox apesar do
        # autoflush. Com `session.new | session.dirty` esta linha seria 0.
        assert len(linhas) == 1
        assert linhas[0].tipo == "DiagnosticoIniciadoEvent"
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
