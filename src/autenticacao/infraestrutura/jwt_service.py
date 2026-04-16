from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

from src.autenticacao.dominio.exceptions import (
    TokenExpiradoException,
    TokenInvalidoException,
)

if TYPE_CHECKING:
    from uuid import UUID

_ALGORITMO = "HS256"
_REFRESH_EXPIRACAO_MINUTOS = int(
    os.environ.get("JWT_REFRESH_EXPIRATION_MINUTES", "10080")
)


class JWTService:
    def __init__(self, chave_secreta: str, expiracao_minutos: int = 30) -> None:
        self._chave_secreta = chave_secreta
        self._expiracao_minutos = expiracao_minutos

    def gerar_access_token(self, usuario_id: UUID, email: str, papel: str) -> str:
        agora = datetime.now(UTC)
        payload = {
            "sub": str(usuario_id),
            "email": email,
            "papel": papel,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": agora,
            "exp": agora + timedelta(minutes=self._expiracao_minutos),
        }
        return jwt.encode(payload, self._chave_secreta, algorithm=_ALGORITMO)

    def gerar_refresh_token(self, usuario_id: UUID) -> str:
        agora = datetime.now(UTC)
        payload = {
            "sub": str(usuario_id),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": agora,
            "exp": agora + timedelta(minutes=_REFRESH_EXPIRACAO_MINUTOS),
        }
        return jwt.encode(payload, self._chave_secreta, algorithm=_ALGORITMO)

    def gerar_token(self, usuario_id: UUID, email: str, papel: str) -> str:
        return self.gerar_access_token(usuario_id=usuario_id, email=email, papel=papel)

    def validar_token(self, token: str) -> dict[str, object]:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != _ALGORITMO:
                raise TokenInvalidoException(mensagem="Algoritmo de token invalido")
            return jwt.decode(
                token,
                self._chave_secreta,
                algorithms=[_ALGORITMO],
                options={"require": ["sub", "jti", "exp", "type"]},
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiradoException() from None
        except jwt.InvalidTokenError:
            raise TokenInvalidoException() from None
