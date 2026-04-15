from __future__ import annotations

from unittest.mock import MagicMock

from src.estoque.infraestrutura.repository import (
    ItemEstoqueSQLAlchemyRepository,
)


class TestRepositoryEstoque:
    def test_init(self) -> None:
        session = MagicMock()
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        assert repo._session is session

    def test_obter_por_id(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        result = repo.obter_por_id(MagicMock())
        assert result is None

    def test_salvar(self) -> None:
        session = MagicMock()
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        entity = MagicMock()
        repo.salvar(entity)
        session.add.assert_called_once_with(entity)
        session.flush.assert_called_once()

    def test_contar(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 3
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        assert repo.contar() == 3

    def test_contar_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

    def test_listar_delega_para_session_scalars(self) -> None:
        session = MagicMock()
        session.scalars.return_value = iter([])
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        result = repo.listar(offset=0, limit=10)
        assert result == []
        session.scalars.assert_called_once()

    def test_obter_por_ids_delega_para_session_scalars(self) -> None:
        session = MagicMock()
        session.scalars.return_value = iter([])
        repo = ItemEstoqueSQLAlchemyRepository(session=session)
        result = repo.obter_por_ids(ids=[])
        assert result == []
        session.scalars.assert_called_once()
