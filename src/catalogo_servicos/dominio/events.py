from __future__ import annotations

from dataclasses import dataclass

from src.compartilhado.dominio.events import DomainEvent


@dataclass(frozen=True, slots=True)
class ServicoCadastradoEvent(DomainEvent):
    """Evento emitido quando um servico e cadastrado no catalogo.

    Payload contem apenas `agregado_id`/`ocorrido_em` (herdados); consumidores
    que precisarem dos dados buscam o servico pelo id. Emitido apenas pela
    factory `ServicoOferecido.criar`, nunca na reconstituicao via repository.
    """
