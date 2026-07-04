from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEvent:
    agregado_id: UUID
    # kw_only: o default de ``ocorrido_em`` nao bloqueia subclasses de
    # declararem campos posicionais obrigatorios (sem hacks de default).
    ocorrido_em: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        kw_only=True,
    )
