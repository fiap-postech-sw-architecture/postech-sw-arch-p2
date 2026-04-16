from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.autenticacao.infraestrutura.jwt_service import JWTService
from src.autenticacao.interfaces.middleware import (
    exigir_papel,
    obter_usuario_atual,
)

_CHAVE = "test-secret"
_MOCK_SESSION = MagicMock()


class _FakeCredentials:
    def __init__(self, token: str) -> None:
        self.credentials = token


@pytest.fixture(autouse=True)
def _jwt_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _CHAVE)


class TestObterUsuarioAtual:
    def test_sem_credenciais_retorna_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=None, session=_MOCK_SESSION)
        assert exc.value.status_code == 401

    def test_token_invalido_retorna_401(self) -> None:
        creds = _FakeCredentials(token="invalido")
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert exc.value.status_code == 401

    def test_token_expirado_retorna_401(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE, expiracao_minutos=-1)
        token = svc.gerar_access_token(
            usuario_id=uuid4(), email="t@t.com", papel="admin"
        )
        creds = _FakeCredentials(token=token)
        with pytest.raises(HTTPException) as exc:
            obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert exc.value.status_code == 401

    def test_token_valido_retorna_payload(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "t@t.com", "admin")
        creds = _FakeCredentials(token=token)
        fake_repo = MagicMock()
        fake_repo.esta_revogado = MagicMock(return_value=False)
        with patch(
            "src.autenticacao.infraestrutura.token_revogado_repository.TokenRevogadoSQLAlchemyRepository",
            return_value=fake_repo,
        ):
            payload = obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
        assert payload["sub"] == str(uid)

    def test_token_revogado_retorna_401(self) -> None:
        svc = JWTService(chave_secreta=_CHAVE)
        uid = uuid4()
        token = svc.gerar_access_token(uid, "t@t.com", "admin")
        payload = svc.validar_token(token)
        jti = str(payload["jti"])
        fake_repo = MagicMock()
        fake_repo.esta_revogado = lambda j: j == jti
        with patch(
            "src.autenticacao.infraestrutura.token_revogado_repository.TokenRevogadoSQLAlchemyRepository",
            return_value=fake_repo,
        ):
            creds = _FakeCredentials(token=token)
            with pytest.raises(HTTPException) as exc:
                obter_usuario_atual(credentials=creds, session=_MOCK_SESSION)  # type: ignore[arg-type]
            assert exc.value.status_code == 401
            assert "revogado" in str(exc.value.detail).lower()


class TestExigirPapel:
    def test_papel_permitido(self) -> None:
        verificar = exigir_papel("admin")
        result = verificar({"papel": "admin", "sub": "123"})  # type: ignore[operator]
        assert result["papel"] == "admin"

    def test_papel_nao_permitido(self) -> None:
        verificar = exigir_papel("admin")
        with pytest.raises(HTTPException) as exc:
            verificar({"papel": "usuario", "sub": "123"})  # type: ignore[operator]
        assert exc.value.status_code == 403

    def test_multiplos_papeis_permitidos(self) -> None:
        verificar = exigir_papel("admin", "mecanico")
        result = verificar({"papel": "mecanico", "sub": "123"})  # type: ignore[operator]
        assert result["papel"] == "mecanico"


class TestEnvLimpeza:
    def test_jwt_secret_nao_vaza_entre_testes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET nao configurado"):
            obter_usuario_atual(
                credentials=_FakeCredentials(token="qualquer"),
                session=_MOCK_SESSION,
            )
