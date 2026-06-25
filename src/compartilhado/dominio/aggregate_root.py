from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.compartilhado.dominio.entity import Entity

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.compartilhado.dominio.events import DomainEvent


@dataclass(eq=False)
class AggregateRoot(Entity):
    _eventos_pendentes: list[DomainEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    def coletar_eventos(self) -> list[DomainEvent]:
        return list(self._eventos_pendentes)

    def limpar_eventos(self) -> None:
        self._eventos_pendentes.clear()

    def remover_eventos(self, eventos: Sequence[DomainEvent]) -> None:
        """Remove os eventos dados (por identidade), preservando os demais.

        Remocao seletiva sancionada: a UnitOfWork remove do agregado apenas
        os ``IntegrationEvent`` ja enfileirados na outbox no commit, deixando
        os domain events puros para o dispatch sincrono pos-commit (F9).
        Sem isso, a UoW teria de fatiar ``_eventos_pendentes`` diretamente
        (``limpar_eventos`` apagaria tudo). Identidade (``id()``), nao
        igualdade: dois eventos iguais por valor sao linhas distintas.
        """
        if not eventos:
            return
        alvo = {id(ev) for ev in eventos}
        self._eventos_pendentes[:] = [
            ev for ev in self._eventos_pendentes if id(ev) not in alvo
        ]

    def _registrar_evento(self, evento: DomainEvent) -> None:
        self._eventos_pendentes.append(evento)
