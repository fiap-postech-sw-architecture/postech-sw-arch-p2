from __future__ import annotations

from unittest.mock import MagicMock

from src.estoque.interfaces.dependencies import (
    obter_ajustar_quantidade,
    obter_atualizar_item,
    obter_criar_item,
    obter_desativar_item,
    obter_listar_itens,
    obter_obter_item,
)


class TestDependenciesEstoque:
    def test_obter_criar_item(self) -> None:
        session = MagicMock()
        uc = obter_criar_item(session)
        assert uc is not None

    def test_obter_listar_itens(self) -> None:
        session = MagicMock()
        uc = obter_listar_itens(session)
        assert uc is not None

    def test_obter_obter_item(self) -> None:
        session = MagicMock()
        uc = obter_obter_item(session)
        assert uc is not None

    def test_obter_atualizar_item(self) -> None:
        session = MagicMock()
        uc = obter_atualizar_item(session)
        assert uc is not None

    def test_obter_ajustar_quantidade(self) -> None:
        session = MagicMock()
        uc = obter_ajustar_quantidade(session)
        assert uc is not None

    def test_obter_desativar_item(self) -> None:
        session = MagicMock()
        uc = obter_desativar_item(session)
        assert uc is not None
