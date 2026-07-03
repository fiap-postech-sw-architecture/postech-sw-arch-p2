"""Eventos de dominio emitidos pela ``OrdemDeServico`` em cada transicao.

Todos os eventos sao ``@dataclass(frozen=True)`` e herdam ``agregado_id``
de ``DomainEvent``. Eventos sem payload adicional carregam apenas o
``agregado_id`` (handlers re-buscam o agregado se precisarem de mais).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.compartilhado.dominio.events import DomainEvent
from src.compartilhado.dominio.integration_event import IntegrationEvent

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class OrdemCriadaEvent(DomainEvent):
    """Evento emitido quando uma nova ``OrdemDeServico`` e criada.

    ``agregado_id`` (herdado) identifica a ordem; ``cliente_id`` e
    ``veiculo_id`` viajam no payload para que consumidores futuros nao
    precisem re-buscar o agregado. Hoje nenhum handler consome este
    evento: criacao nao e atualizacao de status (RF-024).
    """

    cliente_id: UUID = field(kw_only=True, repr=False)
    veiculo_id: UUID = field(kw_only=True, repr=False)


@dataclass(frozen=True)
class DiagnosticoIniciadoEvent(IntegrationEvent):
    """Emitido na transicao ``RECEBIDA -> EM_DIAGNOSTICO``."""


@dataclass(frozen=True)
class OrcamentoGeradoEvent(IntegrationEvent):
    """Emitido na transicao ``EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO``."""


@dataclass(frozen=True)
class OrcamentoAprovadoEvent(IntegrationEvent):
    """Emitido na transicao ``AGUARDANDO_APROVACAO -> EM_EXECUCAO``."""


@dataclass(frozen=True)
class ServicoFinalizadoEvent(IntegrationEvent):
    """Emitido na transicao ``EM_EXECUCAO -> FINALIZADA``."""


@dataclass(frozen=True)
class EntregaRegistradaEvent(IntegrationEvent):
    """Emitido na transicao ``FINALIZADA -> ENTREGUE``."""


@dataclass(frozen=True)
class OrdemCanceladaEvent(IntegrationEvent):
    """Emitido em qualquer transicao para ``CANCELADA``.

    Carrega o ``motivo`` informado pelo caller; o agregado garante que
    o motivo nunca e vazio antes de emitir o evento.
    """

    motivo: str = field(kw_only=True)


@dataclass(frozen=True)
class OrcamentoComplementarGeradoEvent(IntegrationEvent):
    """Emitido na transicao ``EM_EXECUCAO -> AGUARDANDO_APROVACAO_COMPLEMENTAR``."""


@dataclass(frozen=True)
class OrcamentoComplementarAprovadoEvent(IntegrationEvent):
    """Emitido quando o orcamento complementar e aprovado (volta para EM_EXECUCAO)."""


@dataclass(frozen=True)
class OrcamentoComplementarRejeitadoEvent(IntegrationEvent):
    """Emitido quando o orcamento complementar e rejeitado (volta para EM_EXECUCAO)."""
