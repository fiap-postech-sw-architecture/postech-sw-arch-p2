from __future__ import annotations

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


class JWTService:
    # As expiracoes chegam pelo construtor (lidas do ambiente na factory
    # `obter_jwt_service`, com os defaults 30/10080). Sem default aqui: quem
    # instancia direto e obrigado a informar, e os defaults tem fonte unica na
    # factory -- leitura de env no import-time congelava o valor antes de
    # qualquer configuracao de ambiente/teste.
    def __init__(
        self,
        chave_secreta: str,
        expiracao_minutos: int,
        refresh_expiracao_minutos: int,
    ) -> None:
        self._chave_secreta = chave_secreta
        self._expiracao_minutos = expiracao_minutos
        self._refresh_expiracao_minutos = refresh_expiracao_minutos

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
            "exp": agora + timedelta(minutes=self._refresh_expiracao_minutos),
        }
        return jwt.encode(payload, self._chave_secreta, algorithm=_ALGORITMO)

    def validar_token(self, token: str) -> dict[str, object]:
        try:
            return jwt.decode(
                token,
                self._chave_secreta,
                algorithms=[_ALGORITMO],
                options={"require": ["sub", "jti", "exp", "type"]},
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiradoException() from None
        except jwt.InvalidAlgorithmError:
            raise TokenInvalidoException(
                mensagem="Algoritmo de token invalido"
            ) from None
        except jwt.InvalidTokenError:
            raise TokenInvalidoException() from None
