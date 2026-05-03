from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest

from src.autenticacao.dominio.exceptions import (
    TokenExpiradoException,
    TokenInvalidoException,
)
from src.autenticacao.infraestrutura.jwt_service import JWTService

_CHAVE = "chave-secreta-de-teste"


class TestJWTService:
    def test_gerar_access_token_contem_claims(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "a@b.com", "admin")
        payload = svc.validar_token(token)
        assert payload["sub"] == str(uid)
        assert payload["email"] == "a@b.com"
        assert payload["papel"] == "admin"
        assert payload["type"] == "access"
        assert "jti" in payload

    def test_gerar_refresh_token_contem_claims(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_refresh_token(uid)
        payload = svc.validar_token(token)
        assert payload["sub"] == str(uid)
        assert payload["type"] == "refresh"
        assert "jti" in payload
        assert "email" not in payload
        assert "papel" not in payload

    def test_gerar_token_backward_compat(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_token(uid, "a@b.com", "admin")
        payload = svc.validar_token(token)
        assert payload["type"] == "access"

    def test_token_expirado(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE, expiracao_minutos=-1)
        token = svc.gerar_access_token(uuid4(), "a@b.com", "admin")
        with pytest.raises(TokenExpiradoException):
            svc.validar_token(token)

    def test_token_invalido(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        with pytest.raises(TokenInvalidoException):
            svc.validar_token("lixo.token.invalido")

    def test_chave_errada(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        token = svc.gerar_access_token(uuid4(), "a@b.com", "admin")
        outro_svc = JWTService(chave_secreta="outra-chave")
        with pytest.raises(TokenInvalidoException):
            outro_svc.validar_token(token)

    def test_validar_token_nao_inspeciona_header_sem_verificar_assinatura(
        self,
    ) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "a@b.com", "admin")

        with patch(
            "src.autenticacao.infraestrutura.jwt_service.jwt.get_unverified_header",
            side_effect=AssertionError("nao deve ler header nao verificado"),
        ):
            payload = svc.validar_token(token)

        assert payload["sub"] == str(uid)

    def test_algoritmo_invalido_rejeitado(self) -> None:
        payload = {"sub": "x", "jti": "y", "exp": 9999999999, "type": "access"}
        token = jwt.encode(payload, "key", algorithm="HS384")
        svc = JWTService(chave_secreta="key")
        with pytest.raises(TokenInvalidoException, match="Algoritmo"):
            svc.validar_token(token)

    def test_jti_unico_por_token(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        t1 = svc.gerar_access_token(uid, "a@b.com", "admin")
        t2 = svc.gerar_access_token(uid, "a@b.com", "admin")
        p1 = svc.validar_token(t1)
        p2 = svc.validar_token(t2)
        assert p1["jti"] != p2["jti"]
