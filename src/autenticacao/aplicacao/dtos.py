from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from src.autenticacao.dominio.papel import Papel


@dataclass(frozen=True, slots=True)
class RegistrarDTO:
    email: str
    # senha em claro: `repr=False` mantem o valor fora de qualquer repr/traceback.
    # O scrubber de log mascara PII por nome-de-chave em dict, nao a substring
    # `senha='...'` que apareceria no repr do dataclass num stack trace.
    senha: str = field(repr=False)
    papel: Papel


@dataclass(frozen=True, slots=True)
class LoginDTO:
    email: str
    senha: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class TokenDTO:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class UsuarioDTO:
    id: UUID
    email: str = field(repr=False)
    papel: str
