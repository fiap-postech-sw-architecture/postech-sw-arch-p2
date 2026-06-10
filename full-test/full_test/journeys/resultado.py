"""Resultado tipado de uma journey.

Consumido pelo orchestrator (step 13) e pelo relatorio JSON (step 14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class StatusJourney(StrEnum):
    OK = "ok"
    FALHOU = "falhou"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class PassoExecutado:
    """Um passo dentro da execucao de uma journey.

    Exemplos de ``nome``: ``"POST /clientes"``, ``"iniciar_diagnostico"``.
    """

    nome: str
    inicio: datetime
    fim: datetime
    duracao_ms: int
    sucesso: bool
    correlation_id: str | None
    erro: str | None = None


@dataclass(frozen=True, slots=True)
class ResultadoJourney:
    journey_name: str
    instance_id: str  # ex.: "cliente-happy-03" (persona + indice)
    status: StatusJourney
    inicio: datetime
    fim: datetime
    duracao_ms: int
    falha: str | None  # None se status == OK
    passos: list[PassoExecutado] = field(default_factory=list)

    def para_dict(self) -> dict[str, object]:
        return {
            "journey_name": self.journey_name,
            "instance_id": self.instance_id,
            "status": self.status.value,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "duracao_ms": self.duracao_ms,
            "falha": self.falha,
            "passos": [
                {
                    "nome": p.nome,
                    "inicio": p.inicio.isoformat(),
                    "fim": p.fim.isoformat(),
                    "duracao_ms": p.duracao_ms,
                    "sucesso": p.sucesso,
                    "correlation_id": p.correlation_id,
                    "erro": p.erro,
                }
                for p in self.passos
            ],
        }
