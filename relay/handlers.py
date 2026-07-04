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
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import UUID

from relay.processador import PayloadInvalidoError
from src.ordem_servico.aplicacao.notificacoes import (
    _STATUS_POR_EVENTO,
    NotificarMudancaDeStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import Engine

    from src.compartilhado.dominio.events import DomainEvent

NOME_HANDLER_EMAIL = "email"

# Fonte unica: os tipos de evento com handler sao EXATAMENTE as chaves do
# mapa _STATUS_POR_EVENTO de notificacoes.py (dict tipo-de-evento -> status
# novo). Derivar daqui — em vez de manter uma 3a lista paralela que "deve
# espelhar" o mapa — garante que um evento de transicao novo ganhe handler no
# relay automaticamente; senao ele iria direto para a DLQ em producao (sem
# handler) enquanto o teste hardcoded do relay seguiria verde. O tipo estatico
# acompanha a chave do mapa fonte (``type[DomainEvent]``); em runtime todos sao
# IntegrationEvents (entregues pela outbox), mas a fonte e tipada por DomainEvent.
_EVENTOS: tuple[type[DomainEvent], ...] = tuple(_STATUS_POR_EVENTO)
_POR_NOME: dict[str, type[DomainEvent]] = {cls.__name__: cls for cls in _EVENTOS}


def _nome_tipo_base(nome: str) -> str:
    """Reduz anotacoes opcionais ao tipo base: ``"UUID | None"`` -> ``"UUID"``.

    Cobre as duas grafias de opcional (``Optional[UUID]``, inclusive
    qualificada como ``typing.Optional[UUID]``, e a uniao PEP 604
    ``UUID | None`` em qualquer ordem). Uniao com mais de um tipo nao-None
    fica como esta — nao ha desserializacao inequivoca para ela.
    """
    nome = nome.strip()
    posicao = nome.find("Optional[")
    if posicao != -1 and nome.endswith("]"):
        nome = nome[posicao + len("Optional[") : -1].strip()
    if "|" in nome:
        partes = [parte.strip() for parte in nome.split("|") if parte.strip() != "None"]
        if len(partes) == 1:
            nome = partes[0]
    return nome


def _desserializar_valor(tipo_campo: Any, valor: Any) -> Any:  # noqa: ANN401
    """Inverte ``_serializar_valor``: str->UUID, str ISO->datetime, senao cru.

    Com ``from __future__ import annotations`` os ``field.type`` chegam como
    STRING (ex.: ``"UUID"``, ``"datetime"``), nao como o tipo — por isso a
    comparacao e por nome (cobre tanto ``"UUID"`` quanto ``"uuid.UUID"``),
    apos normalizar anotacoes opcionais (``"UUID | None"``/``"Optional[UUID]"``
    -> ``"UUID"``; sem isso um campo opcional novo cairia no ramo cru e o
    evento nasceria com ``str`` onde deveria haver ``UUID``/``datetime``).
    """
    if valor is None:
        return None
    nome_tipo = (
        tipo_campo
        if isinstance(tipo_campo, str)
        else getattr(tipo_campo, "__name__", "")
    )
    nome_tipo = _nome_tipo_base(nome_tipo)
    if nome_tipo.endswith("UUID"):
        return UUID(valor)
    if nome_tipo.endswith("datetime"):
        return datetime.fromisoformat(valor)
    return valor


def _reconstruir_evento(tipo: str, payload: dict[str, Any]) -> DomainEvent:
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
        # Desserializacao ANTES de abrir session/SMTP e FORA do caminho de
        # retry: payload malformado e falha DETERMINISTICA (bug de producer/
        # config) — TypeError/ValueError viram PayloadInvalidoError e o
        # processador manda a linha DIRETO para a DLQ (mesmo caminho do "tipo
        # sem handler"), sem queimar 5 retries de SMTP num dado que nao muda.
        try:
            evento = _reconstruir_evento(tipo, payload)
        except (TypeError, ValueError) as exc:
            msg = f"payload invalido para {tipo}: {type(exc).__name__}: {exc}"
            raise PayloadInvalidoError(msg) from exc
        with SASession(bind=engine, expire_on_commit=False) as session:
            handler = NotificarMudancaDeStatus(
                repo=OrdemDeServicoSQLAlchemyRepository(session=session),
                cliente_port=ClienteSQLAlchemyAdapter(session=session),
                email_port=SmtpEmailAdapter(),
            )
            handler(evento)

    # `partial` congela o `tipo` por valor (equivalente ao fechamento manual
    # `_make_handler`, com menos maquinaria): cada callable recebe so o payload.
    return {tipo: partial(_entregar, tipo) for tipo in _POR_NOME}
