from __future__ import annotations

from unittest.mock import MagicMock

from src.catalogo_servicos.interfaces.dependencies import (
    obter_atualizar_servico,
    obter_criar_servico,
    obter_desativar_servico,
    obter_listar_servicos,
    obter_obter_servico,
)


class TestDependenciesCatalogo:
    def test_obter_criar_servico(self) -> None:
        session = MagicMock()
        uc = obter_criar_servico(session)
        assert uc is not None

    def test_obter_listar_servicos(self) -> None:
        session = MagicMock()
        uc = obter_listar_servicos(session)
        assert uc is not None

    def test_obter_obter_servico(self) -> None:
        session = MagicMock()
        uc = obter_obter_servico(session)
        assert uc is not None

    def test_obter_atualizar_servico(self) -> None:
        session = MagicMock()
        uc = obter_atualizar_servico(session)
        assert uc is not None

    def test_obter_desativar_servico(self) -> None:
        session = MagicMock()
        uc = obter_desativar_servico(session)
        assert uc is not None
