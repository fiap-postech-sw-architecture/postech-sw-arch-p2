from __future__ import annotations

from unittest.mock import MagicMock

from src.catalogo_servicos.infraestrutura.repository import (
    ServicoOferecidoSQLAlchemyRepository,
)


class TestRepositoryCatalogo:
    def test_obter_por_id(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        result = repo.obter_por_id(MagicMock())
        assert result is None
        session.get.assert_called_once()

    def test_salvar(self) -> None:
        session = MagicMock()
        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        entity = MagicMock()
        repo.salvar(entity)
        session.add.assert_called_once_with(entity)
        session.flush.assert_called_once()

    def test_contar(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 5
        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        assert repo.contar() == 5

    def test_contar_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

    def test_listar_delega_para_session_scalars(self) -> None:
        session = MagicMock()
        session.scalars.return_value = iter([])
        repo = ServicoOferecidoSQLAlchemyRepository(session=session)
        result = repo.listar(offset=0, limit=10)
        assert result == []
        session.scalars.assert_called_once()
