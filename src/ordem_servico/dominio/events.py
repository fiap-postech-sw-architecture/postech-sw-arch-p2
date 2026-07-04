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

    from src.ordem_servico.dominio.status import StatusOrdem


@dataclass(frozen=True, slots=True)
class OrdemCriadaEvent(DomainEvent):
    """Evento emitido quando uma nova ``OrdemDeServico`` e criada.

    ``agregado_id`` (herdado) identifica a ordem; ``cliente_id`` e
    ``veiculo_id`` viajam no payload para que consumidores futuros nao
    precisem re-buscar o agregado. Hoje nenhum handler consome este
    evento: criacao nao e atualizacao de status (RF-024) — por isso NAO
    carrega ``status_novo``.
    """

    cliente_id: UUID = field(kw_only=True, repr=False)
    veiculo_id: UUID = field(kw_only=True, repr=False)


@dataclass(frozen=True, slots=True)
class TransicaoStatusEvent(IntegrationEvent):
    """Base dos eventos de transicao: carrega o ``status_novo`` da ordem.

    O agregado preenche ``status_novo`` na emissao para que o handler de
    notificacao (RF-024) resolva a situacao direto do payload, sem depender
    do mapa ``_STATUS_POR_EVENTO`` (mantido como fallback para linhas antigas
    da outbox, gravadas antes deste campo). O serializer da outbox converte o
    ``Enum`` em ``.value``; ``None`` (linha legada) serializa como ``null``.
    ``slots=True`` porque subclasses frozen de base com slots reganham
    ``__dict__`` sem isso.
    """

    status_novo: StatusOrdem | None = field(kw_only=True, default=None)


@dataclass(frozen=True, slots=True)
class DiagnosticoIniciadoEvent(TransicaoStatusEvent):
    """Emitido na transicao ``RECEBIDA -> EM_DIAGNOSTICO``."""


@dataclass(frozen=True, slots=True)
class OrcamentoGeradoEvent(TransicaoStatusEvent):
    """Emitido na transicao ``EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO``."""


@dataclass(frozen=True, slots=True)
class OrcamentoAprovadoEvent(TransicaoStatusEvent):
    """Emitido na transicao ``AGUARDANDO_APROVACAO -> EM_EXECUCAO``."""


@dataclass(frozen=True, slots=True)
class ServicoFinalizadoEvent(TransicaoStatusEvent):
    """Emitido na transicao ``EM_EXECUCAO -> FINALIZADA``."""


@dataclass(frozen=True, slots=True)
class EntregaRegistradaEvent(TransicaoStatusEvent):
    """Emitido na transicao ``FINALIZADA -> ENTREGUE``."""


@dataclass(frozen=True, slots=True)
class OrdemCanceladaEvent(TransicaoStatusEvent):
    """Emitido em qualquer transicao para ``CANCELADA``.

    Carrega o ``motivo`` informado pelo caller; o agregado garante que
    o motivo nunca e vazio antes de emitir o evento.

    PII (LGPD): ``motivo`` e texto livre e pode conter PII. A redacao NAO
    ocorre aqui nem no agregado porque ``dominio``/``aplicacao`` NAO podem
    importar ``compartilhado.infraestrutura.logging.redigir_pii_erro``
    (contrato ``forbidden`` do import-linter — dominio nunca conhece infra).
    A redacao e responsabilidade da FRONTEIRA de escrita duravel: o serializer
    da outbox (``compartilhado.aplicacao.outbox``) e o unico ponto que ve o
    valor a caminho da coluna ``outbox.payload`` / DLQ e deve mascara-lo la.
    """

    motivo: str = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class OrcamentoComplementarGeradoEvent(TransicaoStatusEvent):
    """Emitido na transicao ``EM_EXECUCAO -> AGUARDANDO_APROVACAO_COMPLEMENTAR``."""


@dataclass(frozen=True, slots=True)
class OrcamentoComplementarAprovadoEvent(TransicaoStatusEvent):
    """Emitido quando o orcamento complementar e aprovado (volta para EM_EXECUCAO)."""


@dataclass(frozen=True, slots=True)
class OrcamentoComplementarRejeitadoEvent(TransicaoStatusEvent):
    """Emitido quando o orcamento complementar e rejeitado (volta para EM_EXECUCAO)."""
