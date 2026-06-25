from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from src.compartilhado.dominio.aggregate_root import AggregateRoot
from src.compartilhado.dominio.events import DomainEvent
from src.compartilhado.dominio.integration_event import IntegrationEvent
from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork


class _AgregadoFake(AggregateRoot):
    pass


def _agregado_com(*eventos: DomainEvent) -> _AgregadoFake:
    agg = _AgregadoFake.__new__(_AgregadoFake)
    object.__setattr__(agg, "id", uuid4())  # Entity.__hash__ usa id (set membership)
    object.__setattr__(agg, "_eventos_pendentes", list(eventos))
    object.__setattr__(agg, "_id_atribuido", True)
    return agg


def _session_mock(*, novos: set, identity: list) -> MagicMock:
    """MagicMock de session com `new` e `identity_map` controlados.

    `identity_map` e iteravel via `.values()` (como o IdentityMap real do
    SQLAlchemy); a UoW varre `session.new | session.identity_map.values()`.
    """
    session = MagicMock()
    session.new = novos
    session.identity_map.values.return_value = identity
    session.get_bind.return_value.dialect.name = "postgresql"
    return session


def test_commit_insere_integration_events_e_notifica() -> None:
    integ = IntegrationEvent(agregado_id=uuid4())
    agg = _agregado_com(integ)

    session = _session_mock(novos={agg}, identity=[])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    # 1 INSERT na outbox + 1 pg_notify + commit, nessa ordem antes do commit
    assert session.execute.call_count == 2
    session.commit.assert_called_once()
    # integration event enfileirado e removido do agregado pos-commit
    assert agg.coletar_eventos() == []


def test_commit_coleta_agregado_flushado_via_identity_map() -> None:
    # Agregado ja flushado (autoflush) NAO esta em session.new; cai no
    # identity_map. Sem varrer o identity_map o evento se perderia (F1).
    integ = IntegrationEvent(agregado_id=uuid4())
    agg = _agregado_com(integ)

    session = _session_mock(novos=set(), identity=[agg])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    assert session.execute.call_count == 2  # INSERT + NOTIFY
    session.commit.assert_called_once()
    assert agg.coletar_eventos() == []


def test_commit_preserva_domain_event_puro_no_agregado() -> None:
    puro = DomainEvent(agregado_id=uuid4())
    agg = _agregado_com(puro)

    session = _session_mock(novos={agg}, identity=[])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    # nenhum INSERT/NOTIFY (so domain event puro) — execute nao chamado
    session.execute.assert_not_called()
    session.commit.assert_called_once()
    # domain event puro PERMANECE para o _despachar_pos_commit sincrono (F9)
    assert agg.coletar_eventos() == [puro]


def test_commit_remove_so_o_integration_event_em_agregado_misto() -> None:
    integ = IntegrationEvent(agregado_id=uuid4())
    puro = DomainEvent(agregado_id=uuid4())
    agg = _agregado_com(puro, integ)

    session = _session_mock(novos={agg}, identity=[])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    assert session.execute.call_count == 2  # so o integ vai pra outbox
    # o integration event sai; o domain event puro fica
    assert agg.coletar_eventos() == [puro]


def test_commit_sem_eventos_nao_executa_nada() -> None:
    agg = _agregado_com()
    session = _session_mock(novos={agg}, identity=[])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    session.execute.assert_not_called()
    session.commit.assert_called_once()


def test_commit_deduplica_agregado_em_new_e_identity_map() -> None:
    # Um agregado pode aparecer em new E no identity_map; nao pode gerar
    # INSERT duplicado nem coletar o evento 2x.
    integ = IntegrationEvent(agregado_id=uuid4())
    agg = _agregado_com(integ)

    session = _session_mock(novos={agg}, identity=[agg])

    uow = SQLAlchemyUnitOfWork(session_factory=lambda: session)
    with uow:
        uow.commit()

    assert session.execute.call_count == 2  # 1 INSERT (1 registro) + 1 NOTIFY
    session.commit.assert_called_once()
