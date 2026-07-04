"""Contrato produtor->consumidor da outbox: o payload REAL de
``serializar_integration_event`` (compartilhado/aplicacao/outbox.py) atravessa
o caminho REAL de reconstrucao do relay (``relay.handlers._reconstruir_evento``,
usado por ``construir_mapa_handlers``) sem perder nem deturpar campos.

Os demais testes de relay usam payloads escritos a mao; nenhum exercitava o
serializador de producao contra o desserializador de producao. Uma divergencia
entre os dois (ex.: um formato de UUID/datetime, um campo novo de evento) so
apareceria em producao — este teste fecha essa lacuna para TODOS os
IntegrationEvents de transicao (as chaves de ``_STATUS_POR_EVENTO``).

Importa ``relay.handlers`` para registrar as classes de evento como
subclasses de ``IntegrationEvent`` (o mapa ``_POR_NOME`` do modulo e o alvo do
``_reconstruir_evento``).
"""

from __future__ import annotations

from dataclasses import MISSING, fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

import relay.handlers as handlers_mod
from src.compartilhado.aplicacao.outbox import serializar_integration_event
from src.ordem_servico.aplicacao.notificacoes import _STATUS_POR_EVENTO

if TYPE_CHECKING:
    from src.compartilhado.dominio.integration_event import IntegrationEvent

# Valores deterministicos para os campos extras dos eventos de transicao.
# ``motivo`` (so em OrdemCanceladaEvent) e obrigatorio. ``status_novo`` (base
# TransicaoStatusEvent) tem default None, mas o setamos EXPLICITAMENTE com o
# status real do evento (mapa _STATUS_POR_EVENTO) para que o round-trip
# exercite o caminho do Enum (StatusOrdem -> ``.value`` na serializacao ->
# StatusOrdem de volta na reconstrucao), nao so o ramo None. Se um evento futuro
# adicionar OUTRO campo obrigatorio, o guard de _instanciar_evento aponta o
# campo faltante.
_VALORES_EXTRAS: dict[str, Any] = {
    "motivo": "cliente desistiu do reparo",
}


def _instanciar_evento(cls: type[IntegrationEvent]) -> IntegrationEvent:
    """Instancia o evento REAL com valores deterministicos e verificaveis."""
    nomes_campos = {campo.name for campo in fields(cls)}
    kwargs: dict[str, Any] = {
        "agregado_id": uuid4(),
        "ocorrido_em": datetime(2026, 6, 24, 12, 0, tzinfo=UTC),
    }
    # Preenche status_novo com o status real do evento quando o campo existe,
    # para cobrir a (de)serializacao do Enum em vez do ramo legado None.
    if "status_novo" in nomes_campos:
        kwargs["status_novo"] = _STATUS_POR_EVENTO[cls]
    for campo in fields(cls):
        if campo.name in kwargs:
            continue
        tem_default = (
            campo.default is not MISSING or campo.default_factory is not MISSING
        )
        if tem_default:
            continue
        if campo.name not in _VALORES_EXTRAS:
            msg = (
                f"{cls.__name__} tem o campo obrigatorio {campo.name!r} sem "
                f"valor de teste; adicione-o a _VALORES_EXTRAS."
            )
            raise AssertionError(msg)
        kwargs[campo.name] = _VALORES_EXTRAS[campo.name]
    return cls(**kwargs)


@pytest.mark.parametrize(
    "evento_cls",
    list(_STATUS_POR_EVENTO),
    ids=lambda cls: cls.__name__,
)
def test_round_trip_serializa_e_reconstroi_pelo_caminho_do_relay(
    evento_cls: type[IntegrationEvent],
) -> None:
    original = _instanciar_evento(evento_cls)

    # Produtor real: serializa como a UnitOfWork faria no commit.
    registro = serializar_integration_event(original)
    assert registro.tipo == evento_cls.__name__
    assert registro.agregado_id == original.agregado_id

    # Consumidor real: o mesmo caminho do relay (tipo + payload da outbox ->
    # evento reconstruido) que ``construir_mapa_handlers`` invoca por linha.
    reconstruido = handlers_mod._reconstruir_evento(registro.tipo, registro.payload)

    # A reconstrucao bate com o original campo a campo. Como os eventos sao
    # frozen dataclasses, a igualdade estrutural cobre TODOS os campos
    # (agregado_id, ocorrido_em e quaisquer extras), com os tipos certos
    # (UUID/datetime, nao str).
    assert reconstruido == original
    assert type(reconstruido) is evento_cls
    assert isinstance(reconstruido.agregado_id, type(original.agregado_id))
    assert reconstruido.ocorrido_em == original.ocorrido_em


def test_round_trip_entrega_ao_handler_real_com_notificador_fake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O payload serializado, ao passar pelo callable REAL do mapa do relay,
    chega ao handler como o evento original reconstruido (notificador fake).

    Cobre o caminho completo ``construir_mapa_handlers`` -> callable(payload)
    -> ``_reconstruir_evento`` -> handler, sem session/SMTP reais.
    """
    from unittest.mock import MagicMock

    capturado: list[IntegrationEvent] = []

    class FakeNotificar:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, evento: IntegrationEvent) -> None:
            capturado.append(evento)

    monkeypatch.setattr(handlers_mod, "NotificarMudancaDeStatus", FakeNotificar)

    mapa = handlers_mod.construir_mapa_handlers(MagicMock())

    original = _instanciar_evento(handlers_mod._POR_NOME["OrdemCanceladaEvent"])
    registro = serializar_integration_event(original)

    mapa[registro.tipo](registro.payload)

    assert len(capturado) == 1
    assert capturado[0] == original
    assert capturado[0].motivo == original.motivo  # type: ignore[attr-defined]
