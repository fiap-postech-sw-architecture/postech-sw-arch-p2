from __future__ import annotations

from dataclasses import dataclass

from src.autenticacao.dominio.papel import Papel
from src.compartilhado.dominio.aggregate_root import AggregateRoot


@dataclass(eq=False)
class Usuario(AggregateRoot):
    _email: str = ""
    _senha_hash: str = ""
    _papel: Papel = Papel.ADMIN

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self._email or "@" not in self._email:
            msg = "Email invalido"
            raise ValueError(msg)
        local, domain = self._email.rsplit("@", 1)
        if not local or not domain or "." not in domain:
            msg = "Email invalido"
            raise ValueError(msg)

    @property
    def email(self) -> str:
        return self._email

    @property
    def senha_hash(self) -> str:
        return self._senha_hash

    @property
    def papel(self) -> Papel:
        return self._papel

    @classmethod
    def criar(cls, email: str, senha_hash: str, papel: Papel = Papel.ADMIN) -> Usuario:
        return cls(_email=email, _senha_hash=senha_hash, _papel=papel)
