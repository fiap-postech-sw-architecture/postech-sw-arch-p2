from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.compartilhado.aplicacao.unit_of_work import UnitOfWork
from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork


class TestSQLAlchemyUnitOfWork:
    def _criar_uow(self) -> tuple[SQLAlchemyUnitOfWork, MagicMock]:
        session_mock = MagicMock()
        session_mock.new = set()
        session_mock.identity_map.values.return_value = []
        factory_mock = MagicMock(return_value=session_mock)
        uow = SQLAlchemyUnitOfWork(session_factory=factory_mock)
        return uow, session_mock

    def test_session_antes_de_enter_levanta_erro(self) -> None:
        uow, _ = self._criar_uow()
        with pytest.raises(RuntimeError, match="nao foi iniciado"):
            _ = uow.session

    def test_enter_cria_sessao(self) -> None:
        uow, session_mock = self._criar_uow()
        with uow:
            assert uow.session is session_mock

    def test_exit_fecha_sessao(self) -> None:
        uow, session_mock = self._criar_uow()
        with uow:
            pass
        session_mock.close.assert_called_once()

    def test_commit(self) -> None:
        uow, session_mock = self._criar_uow()
        with uow:
            uow.commit()
        session_mock.commit.assert_called_once()

    def test_rollback(self) -> None:
        uow, session_mock = self._criar_uow()
        with uow:
            uow.rollback()
        session_mock.rollback.assert_called_once()

    def test_rollback_em_excecao(self) -> None:
        uow, session_mock = self._criar_uow()
        with pytest.raises(ValueError, match="erro"), uow:
            raise ValueError("erro")
        # codeql[py/unreachable-statement] -- executa dentro de pytest.raises
        session_mock.rollback.assert_called_once()
        session_mock.close.assert_called_once()

    def test_session_none_apos_exit(self) -> None:
        uow, _ = self._criar_uow()
        with uow:
            pass
        with pytest.raises(RuntimeError, match="nao foi iniciado"):
            _ = uow.session


class TestUnitOfWorkProtocol:
    def test_protocolo_e_uma_classe(self) -> None:
        assert isinstance(UnitOfWork, type)

    def test_implementacao_sqlalchemy_satisfaz_protocolo(self) -> None:
        # Protocol sem @runtime_checkable (a conformidade e do mypy):
        # verificacao estrutural minima dos membros exigidos.
        uow = SQLAlchemyUnitOfWork(session_factory=MagicMock())
        for membro in ("__enter__", "__exit__", "commit", "rollback"):
            assert callable(getattr(uow, membro)), membro
