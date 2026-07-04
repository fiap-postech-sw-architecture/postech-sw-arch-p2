from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.compartilhado.dominio.entity import Entity

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass(eq=False)
class ConsentimentoCliente(Entity):
    """Raiz do seu proprio agregado trivial (sem eventos), nao filho de Cliente."""

    _cliente_id: UUID | None = None
    _tipo: str = ""
    _concedido_em: datetime | None = None
    _revogado_em: datetime | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self._cliente_id is None:
            msg = "cliente_id e obrigatorio"
            raise ValueError(msg)
        # Canonicaliza o tipo no agregado (strip + lowercase) para que
        # "Marketing" e "marketing " sejam o MESMO consentimento no par
        # cliente+tipo, independentemente de quem constroi o objeto. O
        # validator do schema HTTP vira apenas UX (feedback antecipado).
        self._tipo = self._tipo.strip().lower()
        if not self._tipo:
            msg = "tipo de consentimento e obrigatorio"
            raise ValueError(msg)
        if self._concedido_em is None:
            msg = "concedido_em e obrigatorio"
            raise ValueError(msg)

    @classmethod
    def criar(
        cls,
        *,
        cliente_id: UUID,
        tipo: str,
        concedido_em: datetime,
        revogado_em: datetime | None = None,
    ) -> ConsentimentoCliente:
        """Factory de consentimento: normaliza o `tipo` via `__post_init__`.

        Prefira esta factory aos kwargs privados (`_cliente_id=...`) nos
        callers de aplicacao — mantem a construcao explicita e garante a
        canonicalizacao do `tipo` em um unico ponto.
        """
        return cls(
            _cliente_id=cliente_id,
            _tipo=tipo,
            _concedido_em=concedido_em,
            _revogado_em=revogado_em,
        )

    @property
    def cliente_id(self) -> UUID:
        if self._cliente_id is None:
            msg = "cliente_id nao pode ser nulo"
            raise ValueError(msg)
        return self._cliente_id

    @property
    def tipo(self) -> str:
        return self._tipo

    @property
    def concedido_em(self) -> datetime:
        if self._concedido_em is None:
            msg = "concedido_em nao pode ser nulo"
            raise ValueError(msg)
        return self._concedido_em

    @property
    def revogado_em(self) -> datetime | None:
        return self._revogado_em

    @property
    def ativo(self) -> bool:
        return self._revogado_em is None

    def revogar(self, revogado_em: datetime) -> None:
        if self._revogado_em is not None:
            msg = "Consentimento ja foi revogado"
            raise ValueError(msg)
        self._revogado_em = revogado_em
