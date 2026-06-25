"""Registro de handlers do relay: tipo de IntegrationEvent -> callable.

Para cada tipo de evento de transicao da OS, o relay reconstrucao o
evento a partir do ``payload`` JSON da outbox e invoca o handler de e-mail
``NotificarMudancaDeStatus`` (reusado da aplicacao, sem duplicar a regra
de notificacao). Cada invocacao abre uma session propria (escopo curto):
o relay roda fora do ciclo de request, entao nao ha session
request-scoped; a session vive apenas o tempo de resolver cliente +
enviar e-mail.

``NOME_HANDLER_EMAIL`` e a chave gravada em ``processed_events`` — DEVE
permanecer estavel entre deploys, senao a idempotencia reprocessaria
eventos ja entregues.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.ordem_servico.aplicacao.notificacoes import NotificarMudancaDeStatus
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    EntregaRegistradaEvent,
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarRejeitadoEvent,
    OrcamentoGeradoEvent,
    OrdemCanceladaEvent,
    ServicoFinalizadoEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Engine

    from src.compartilhado.dominio.integration_event import IntegrationEvent

NOME_HANDLER_EMAIL = "email"

# Mesmos 9 tipos do mapa _STATUS_POR_EVENTO de notificacoes.py.
_EVENTOS: tuple[type[IntegrationEvent], ...] = (
    DiagnosticoIniciadoEvent,
    OrcamentoGeradoEvent,
    OrcamentoAprovadoEvent,
    ServicoFinalizadoEvent,
    EntregaRegistradaEvent,
    OrdemCanceladaEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarRejeitadoEvent,
)
_POR_NOME: dict[str, type[IntegrationEvent]] = {
    cls.__name__: cls for cls in _EVENTOS
}


def _desserializar_valor(tipo_campo: Any, valor: Any) -> Any:  # noqa: ANN401
    """Inverte ``_serializar_valor``: str->UUID, str ISO->datetime, senao cru.

    Com ``from __future__ import annotations`` os ``field.type`` chegam como
    STRING (ex.: ``"UUID"``, ``"datetime"``), nao como o tipo — por isso a
    comparacao e por nome (cobre tanto ``"UUID"`` quanto ``"uuid.UUID"``).
    """
    if valor is None:
        return None
    nome_tipo = tipo_campo if isinstance(tipo_campo, str) else getattr(
        tipo_campo, "__name__", ""
    )
    if nome_tipo.endswith("UUID"):
        return UUID(valor)
    if nome_tipo.endswith("datetime"):
        return datetime.fromisoformat(valor)
    return valor


def _reconstruir_evento(tipo: str, payload: dict[str, Any]) -> IntegrationEvent:
    """Reconstroi o IntegrationEvent a partir do tipo + payload da outbox.

    Itera ``dataclasses.fields(cls)`` em vez de hard-listar campos (ex.:
    ``motivo``): um campo novo de evento futuro e reconstruido
    automaticamente (F10), sem perder dado silenciosamente. O tipo declarado
    do campo guia a desserializacao de UUID/datetime.
    """
    cls = _POR_NOME[tipo]
    kwargs: dict[str, Any] = {
        campo.name: _desserializar_valor(campo.type, payload[campo.name])
        for campo in fields(cls)
        if campo.name in payload
    }
    return cls(**kwargs)


def construir_mapa_handlers(
    engine: Engine,
) -> dict[str, Callable[[dict[str, Any]], None]]:
    """Mapa ``tipo -> callable(payload)`` que entrega via e-mail.

    Cada callable abre uma session do ``engine``, monta o handler de e-mail
    com os adapters reais e o invoca com o evento reconstruido.
    """
    from sqlalchemy.orm import Session as SASession

    from src.ordem_servico.infraestrutura.adapters import ClienteSQLAlchemyAdapter
    from src.ordem_servico.infraestrutura.email_adapter import SmtpEmailAdapter
    from src.ordem_servico.infraestrutura.repository import (
        OrdemDeServicoSQLAlchemyRepository,
    )

    def _entregar(tipo: str, payload: dict[str, Any]) -> None:
        evento = _reconstruir_evento(tipo, payload)
        with SASession(bind=engine, expire_on_commit=False) as session:
            handler = NotificarMudancaDeStatus(
                repo=OrdemDeServicoSQLAlchemyRepository(session=session),
                cliente_port=ClienteSQLAlchemyAdapter(session=session),
                email_port=SmtpEmailAdapter(),
            )
            handler(evento)

    def _make_handler(t: str) -> Callable[[dict[str, Any]], None]:
        def _h(p: dict[str, Any]) -> None:
            _entregar(t, p)

        return _h

    return {tipo: _make_handler(tipo) for tipo in _POR_NOME}
