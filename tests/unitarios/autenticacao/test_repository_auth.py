from __future__ import annotations

from unittest.mock import MagicMock

from src.autenticacao.dominio.repository import (
    TokenRevogadoRepository as TokenRevogadoProtocol,
)
from src.autenticacao.dominio.repository import (
    UsuarioRepository as UsuarioProtocol,
)
from src.autenticacao.infraestrutura.repository import (
    UsuarioSQLAlchemyRepository,
)
from src.autenticacao.infraestrutura.token_revogado_repository import (
    TokenRevogadoSQLAlchemyRepository,
)


class TestRepositoryAuth:
    def test_usuario_repo_init(self) -> None:
        session = MagicMock()
        repo = UsuarioSQLAlchemyRepository(session=session)
        assert repo._session is session

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
    def test_init(self) -> None:
        session = MagicMock()
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo._session is session

    def test_revogar(self) -> None:
        session = MagicMock()
        # O guard de idempotencia (#121) consulta esta_revogado antes de
        # inserir; simula "ainda nao revogado" para exercitar o INSERT.
        session.execute.return_value.first.return_value = None
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        repo.revogar("some-jti")
        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_revogar_idempotente_nao_reinsere(self) -> None:
        # Issue #121: jti ja revogado -> revogar nao tenta novo INSERT, evitando
        # o IntegrityError do UNIQUE que virava 500 no logout duplo/retry.
        session = MagicMock()
        session.execute.return_value.first.return_value = MagicMock()  # ja revogado
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        repo.revogar("some-jti")
        session.add.assert_not_called()
        session.flush.assert_not_called()

    def test_esta_revogado_false(self) -> None:
        session = MagicMock()
        execute_result = MagicMock()
        execute_result.first.return_value = None
        session.execute.return_value = execute_result
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.esta_revogado("some-jti") is False

    def test_esta_revogado_true(self) -> None:
        session = MagicMock()
        execute_result = MagicMock()
        execute_result.first.return_value = MagicMock()
        session.execute.return_value = execute_result
        repo = TokenRevogadoSQLAlchemyRepository(session=session)
        assert repo.esta_revogado("some-jti") is True


class TestProtocolDefinitions:
    def test_usuario_protocol_define_metodos(self) -> None:
        assert hasattr(UsuarioProtocol, "obter_por_id")
        assert hasattr(UsuarioProtocol, "obter_por_email")
        assert hasattr(UsuarioProtocol, "salvar")
        assert hasattr(UsuarioProtocol, "email_existe")

    def test_token_revogado_protocol_define_metodos(self) -> None:
        assert hasattr(TokenRevogadoProtocol, "revogar")
        assert hasattr(TokenRevogadoProtocol, "esta_revogado")
