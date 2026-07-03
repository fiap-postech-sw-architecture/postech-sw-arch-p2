from __future__ import annotations

from unittest.mock import MagicMock

from src.autenticacao.infraestrutura.repository import (
    UsuarioSQLAlchemyRepository,
)
from src.autenticacao.infraestrutura.token_revogado_repository import (
    TokenRevogadoSQLAlchemyRepository,
)


class TestRepositoryAuth:
    def test_obter_por_id(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        repo = UsuarioSQLAlchemyRepository(session=session)
        result = repo.obter_por_id(MagicMock())
        assert result is None

    def test_salvar(self) -> None:
        session = MagicMock()
        repo = UsuarioSQLAlchemyRepository(session=session)
        entity = MagicMock()
        repo.salvar(entity)
        session.add.assert_called_once_with(entity)
        session.flush.assert_called_once()

    def test_email_existe_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        repo = UsuarioSQLAlchemyRepository(session=session)
        assert repo.email_existe("test@test.com") is True

    def test_email_existe_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = UsuarioSQLAlchemyRepository(session=session)
        assert repo.email_existe("test@test.com") is False


class TestTokenRevogadoRepository:
    def test_revogar(self) -> None:
        session = MagicMock()
        # O guard de idempotencia (#121) consulta esta_revogado antes de
        # inserir; simula "ainda nao revogado" para exercitar o INSERT.
        session.scalar.return_value = False
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.revogar("some-jti") is True
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_revogar_idempotente_nao_reinsere(self) -> None:
        # Issue #121: jti ja revogado -> revogar nao tenta novo INSERT, evitando
        # o IntegrityError do UNIQUE que virava 500 no logout duplo/retry.
        # O retorno False (#167) sinaliza "ja estava revogado" ao fluxo de
        # refresh (single-use).
        session = MagicMock()
        session.scalar.return_value = True  # ja revogado
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.revogar("some-jti") is False
        session.add.assert_not_called()
        session.flush.assert_not_called()

    def test_esta_revogado_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = False
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.esta_revogado("some-jti") is False

    def test_esta_revogado_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = True
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.esta_revogado("some-jti") is True
