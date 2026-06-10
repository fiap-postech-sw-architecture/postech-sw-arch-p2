"""Eventos de dominio emitidos pela ``OrdemDeServico`` em cada transicao.

Todos os eventos sao ``@dataclass(frozen=True)`` e herdam ``agregado_id``
de ``DomainEvent``. Eventos sem payload adicional carregam apenas o
``agregado_id`` (handlers re-buscam o agregado se precisarem de mais).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.compartilhado.dominio.events import DomainEvent

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class OrdemCriadaEvent(DomainEvent):
    """Evento emitido quando uma nova ``OrdemDeServico`` e criada.

    ``agregado_id`` (herdado) identifica a ordem; ``cliente_id`` e
    ``veiculo_id`` permitem a handlers downstream evitar uma busca extra.
    """

    cliente_id: UUID = field(default=None, repr=False)  # type: ignore[assignment]
    veiculo_id: UUID = field(default=None, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.cliente_id is None:
            msg = "cliente_id e obrigatorio em OrdemCriadaEvent (recebido: None)"
            raise ValueError(msg)
        if self.veiculo_id is None:
            msg = "veiculo_id e obrigatorio em OrdemCriadaEvent (recebido: None)"
            raise ValueError(msg)


@dataclass(frozen=True)
class DiagnosticoIniciadoEvent(DomainEvent):
    """Emitido na transicao ``RECEBIDA -> EM_DIAGNOSTICO``."""


@dataclass(frozen=True)
class OrcamentoGeradoEvent(DomainEvent):
    """Emitido na transicao ``EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO``."""


@dataclass(frozen=True)
class OrcamentoAprovadoEvent(DomainEvent):
    """Emitido na transicao ``AGUARDANDO_APROVACAO -> EM_EXECUCAO``."""


@dataclass(frozen=True)
class ServicoFinalizadoEvent(DomainEvent):
    """Emitido na transicao ``EM_EXECUCAO -> FINALIZADA``."""


@dataclass(frozen=True)
class EntregaRegistradaEvent(DomainEvent):
    """Emitido na transicao ``FINALIZADA -> ENTREGUE``."""


@dataclass(frozen=True)
class OrdemCanceladaEvent(DomainEvent):
    """Emitido em qualquer transicao para ``CANCELADA``.

    Carrega o ``motivo`` informado pelo caller; o agregado garante que
    o motivo nunca e vazio antes de emitir o evento.
    """

    motivo: str = ""


@dataclass(frozen=True)
class OrcamentoComplementarGeradoEvent(DomainEvent):
    """Emitido na transicao ``EM_EXECUCAO -> AGUARDANDO_APROVACAO_COMPLEMENTAR``."""


@dataclass(frozen=True)
class OrcamentoComplementarAprovadoEvent(DomainEvent):
    """Emitido quando o orcamento complementar e aprovado (volta para EM_EXECUCAO)."""


@dataclass(frozen=True)
class OrcamentoComplementarRejeitadoEvent(DomainEvent):
    """Emitido quando o orcamento complementar e rejeitado (volta para EM_EXECUCAO)."""
