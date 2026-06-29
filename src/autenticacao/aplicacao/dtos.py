from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.papel import Papel


@dataclass(frozen=True, slots=True)
class RegistrarDTO:
    email: str
    senha: str
    papel: Papel


@dataclass(frozen=True, slots=True)
class LoginDTO:
    email: str
    senha: str


@dataclass(frozen=True, slots=True)
class TokenDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class UsuarioDTO:
    id: UUID
    email: str
    papel: str
