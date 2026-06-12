from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(eq=False)
class Entity:
    id: UUID = field(default_factory=uuid4)
    _id_atribuido: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._id_atribuido = True

    def __setattr__(self, name: str, value: object) -> None:
        if name == "id" and getattr(self, "_id_atribuido", False):
            msg = "Identidade da entidade nao pode ser alterada apos criacao"
            raise AttributeError(msg)
        super().__setattr__(name, value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
