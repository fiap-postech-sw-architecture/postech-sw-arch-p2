"""Testes unitarios para scripts/seed_admin.py.

Cobre os tres branches criticos de idempotencia/seguranca:
- Falha rapida quando ADMIN_EMAIL/ADMIN_PASSWORD estao ausentes ou invalidos.
- Normalizacao de email (case + whitespace).
- Criacao idempotente: email ja existente = no-op; race (IntegrityError) = no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.seed_admin import (  # noqa: E402
    _PLACEHOLDERS_PROIBIDOS,
    _SENHA_MIN_LEN,
    _ConfigError,
    criar_admin_se_ausente,
    ler_config,
    main,
)

if TYPE_CHECKING:
    pass


class TestLerConfig:
    def test_rejeita_admin_password_ausente(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        with pytest.raises(_ConfigError, match="ADMIN_PASSWORD"):
            ler_config(env)

    def test_rejeita_admin_email_ausente(self) -> None:
        env = {
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        with pytest.raises(_ConfigError, match="ADMIN_EMAIL"):
            ler_config(env)

    def test_rejeita_senha_curta(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "a" * (_SENHA_MIN_LEN - 1),
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        with pytest.raises(_ConfigError, match="pelo menos"):
            ler_config(env)

    @pytest.mark.parametrize("placeholder", sorted(_PLACEHOLDERS_PROIBIDOS))
    def test_rejeita_placeholders_publicos(self, placeholder: str) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": placeholder,
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        with pytest.raises(_ConfigError, match="placeholder"):
            ler_config(env)

    def test_rejeita_senha_whitespace(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "   \t  ",
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        with pytest.raises(_ConfigError, match="ADMIN_PASSWORD"):
            ler_config(env)

    def test_normaliza_email_para_lowercase_e_strip(self) -> None:
        env = {
            "ADMIN_EMAIL": "  Admin@PytStop.LOCAL  ",
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "DATABASE_URL": "postgresql://u:p@h/d",
        }
        _, email, _ = ler_config(env)
        assert email == "admin@pytstop.local"

    def test_database_url_obrigatoria_em_producao(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "ENVIRONMENT": "production",
        }
        with pytest.raises(_ConfigError, match="DATABASE_URL"):
            ler_config(env)

    def test_database_url_usa_default_em_dev(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "ENVIRONMENT": "development",
        }
        db_url, _, _ = ler_config(env)
        assert "localhost:5432" in db_url

    def test_database_url_usa_default_em_test(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "ENVIRONMENT": "test",
        }
        db_url, _, _ = ler_config(env)
        assert "localhost:5432" in db_url

    def test_retorna_valores_validos_no_happy_path(self) -> None:
        env = {
            "ADMIN_EMAIL": "admin@pytstop.local",
            "ADMIN_PASSWORD": "S3nh4-Bem-Forte",
            "DATABASE_URL": "postgresql://u:p@h:5432/d",
        }
        db_url, email, senha = ler_config(env)
        assert db_url == "postgresql://u:p@h:5432/d"
        assert email == "admin@pytstop.local"
        assert senha == "S3nh4-Bem-Forte"


class TestCriarAdminSeAusente:
    def _session_factory_com_repo(self, repo_mock: MagicMock) -> MagicMock:
        session = MagicMock(name="session")
        session_ctx = MagicMock(name="session_ctx")
        session_ctx.__enter__.return_value = session
        session_ctx.__exit__.return_value = False
        factory = MagicMock(return_value=session_ctx)
        self._last_repo = repo_mock
        self._last_session = session
        return factory

    def test_retorna_false_se_email_ja_existe(self) -> None:
        repo = MagicMock()
        repo.email_existe.return_value = True
        factory = self._session_factory_com_repo(repo)

        with patch(
            "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository",
            return_value=repo,
        ):
            criado = criar_admin_se_ausente(factory, "admin@pytstop.local", "hash-fake")

        assert criado is False
        repo.salvar.assert_not_called()
        self._last_session.commit.assert_not_called()

    def test_cria_quando_email_nao_existe(self) -> None:
        repo = MagicMock()
        repo.email_existe.return_value = False
        factory = self._session_factory_com_repo(repo)

        with patch(
            "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository",
            return_value=repo,
        ):
            criado = criar_admin_se_ausente(factory, "admin@pytstop.local", "hash-fake")

        assert criado is True
        repo.salvar.assert_called_once()
        self._last_session.commit.assert_called_once()

    def test_trata_integrity_error_como_ja_existia(self) -> None:
        from sqlalchemy.exc import IntegrityError

        repo = MagicMock()
        repo.email_existe.return_value = False
        repo.salvar.side_effect = IntegrityError("INSERT", {}, Exception("dup"))
        factory = self._session_factory_com_repo(repo)

        with patch(
            "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository",
            return_value=repo,
        ):
            criado = criar_admin_se_ausente(factory, "admin@pytstop.local", "hash-fake")

        assert criado is False
        self._last_session.rollback.assert_called_once()
        self._last_session.commit.assert_not_called()


class TestMain:
    def test_sai_com_codigo_1_quando_password_ausente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.setenv("ADMIN_EMAIL", "admin@pytstop.local")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
