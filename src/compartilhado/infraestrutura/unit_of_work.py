from __future__ import annotations

from typing import TYPE_CHECKING, Self

from src.compartilhado.aplicacao.outbox import serializar_integration_event
from src.compartilhado.dominio.aggregate_root import AggregateRoot
from src.compartilhado.dominio.integration_event import IntegrationEvent
from src.compartilhado.infraestrutura.outbox_mapping import (
    inserir_na_outbox,
    pg_notify_outbox,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from sqlalchemy.orm import Session


class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            msg = "UnitOfWork nao foi iniciado. Use 'with' para iniciar."
            raise RuntimeError(msg)
        return self._session

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rollback()
        self._fechar_sessao()

    def commit(self) -> None:
        """Comita o estado e, na MESMA transacao, enfileira a outbox (RF-018).

        Antes do commit: varre os agregados pendentes na session
        (``new | identity_map``), coleta seus ``IntegrationEvent`` e os
        insere na ``outbox``; emite ``pg_notify('outbox_novo')``
        (transacional -- so chega ao relay no COMMIT). Apos o commit: remove
        do agregado APENAS os ``IntegrationEvent`` enfileirados -- os domain
        events puros permanecem em ``_eventos_pendentes`` para o
        ``_despachar_pos_commit`` sincrono dos use cases (F9).
        """
        agregados = self._agregados_pendentes()
        por_agregado = {
            agregado: [
                ev
                for ev in agregado.coletar_eventos()
                if isinstance(ev, IntegrationEvent)
            ]
            for agregado in agregados
        }
        integration_events = [ev for eventos in por_agregado.values() for ev in eventos]
        if integration_events:
            registros = [serializar_integration_event(ev) for ev in integration_events]
            inserir_na_outbox(self.session, registros)
            pg_notify_outbox(self.session)
        self.session.commit()
        for agregado, enfileirados in por_agregado.items():
            agregado.remover_eventos(enfileirados)

    def rollback(self) -> None:
        self.session.rollback()

    def _agregados_pendentes(self) -> list[AggregateRoot]:
        """Agregados raiz tocados na transacao (novos ou ja flushados).

        Varre ``session.new`` (agregados ainda pendentes) UNIDO ao
        ``session.identity_map`` (agregados ja persistidos/flushados nesta
        transacao). Um agregado novo seguido de autoflush sai de
        ``session.new`` e, se nao for re-modificado, NAO aparece em
        ``session.dirty`` -- varrer ``identity_map`` garante que seu evento
        nao se perca (F1). Deduplica por identidade de objeto (um agregado
        pode estar em ambos).
        """
        vistos: dict[int, AggregateRoot] = {}
        for obj in (*self.session.new, *self.session.identity_map.values()):
            if isinstance(obj, AggregateRoot):
                vistos.setdefault(id(obj), obj)
        return list(vistos.values())

    def _fechar_sessao(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
