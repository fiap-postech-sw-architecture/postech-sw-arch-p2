from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.compartilhado.dominio.entity import Entity


@dataclass(eq=False)
class TokenRevogado(Entity):
    _jti: str = ""
    # Sentinel: __post_init__ guarantees non-None before first use.
    _revogado_em: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self._jti:
            msg = "JTI nao pode ser vazio"
            raise ValueError(msg)
        if self._revogado_em is None:
            object.__setattr__(self, "_revogado_em", datetime.now(UTC))

    @property
    def jti(self) -> str:
        return self._jti

    @property
    def revogado_em(self) -> datetime:
        return self._revogado_em

    @classmethod
    def criar(cls, jti: str) -> TokenRevogado:
        return cls(_jti=jti, _revogado_em=datetime.now(UTC))
