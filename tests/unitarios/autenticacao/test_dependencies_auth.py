from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.autenticacao.interfaces.dependencies import (
    obter_jwt_service,
    obter_login,
    obter_logout,
    obter_refresh_token,
    obter_registrar,
)


class TestDependenciesAuth:
    def test_obter_jwt_service_sem_chave_levanta_erro(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("JWT_SECRET", None)
            with pytest.raises(RuntimeError, match="JWT_SECRET"):
                obter_jwt_service()

    def test_obter_jwt_service_com_chave(self) -> None:
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
            svc = obter_jwt_service()
            assert svc is not None

    def test_obter_registrar(self) -> None:
        session = MagicMock()
        uc = obter_registrar(session)
        assert uc is not None

    def test_obter_login(self) -> None:
        session = MagicMock()
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
            uc = obter_login(session)
            assert uc is not None

    def test_obter_logout(self) -> None:
        session = MagicMock()
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
            uc = obter_logout(session)
            assert uc is not None

    def test_obter_refresh_token(self) -> None:
        session = MagicMock()
        with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
            uc = obter_refresh_token(session)
            assert uc is not None
