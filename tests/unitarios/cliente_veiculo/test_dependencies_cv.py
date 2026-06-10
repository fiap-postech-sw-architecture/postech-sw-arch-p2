from __future__ import annotations

from unittest.mock import MagicMock

from src.cliente_veiculo.interfaces.dependencies import (
    obter_adicionar_veiculo,
    obter_atualizar_cliente,
    obter_criar_cliente,
    obter_desativar_cliente,
    obter_listar_clientes,
    obter_listar_veiculos,
    obter_obter_cliente,
    obter_remover_veiculo,
)


class TestDependenciesClienteVeiculo:
    def test_obter_criar_cliente(self) -> None:
        session = MagicMock()
        uc = obter_criar_cliente(session)
        assert uc is not None

    def test_obter_listar_clientes(self) -> None:
        session = MagicMock()
        uc = obter_listar_clientes(session)
        assert uc is not None

    def test_obter_obter_cliente(self) -> None:
        session = MagicMock()
        uc = obter_obter_cliente(session)
        assert uc is not None

    def test_obter_atualizar_cliente(self) -> None:
        session = MagicMock()
        uc = obter_atualizar_cliente(session)
        assert uc is not None

    def test_obter_desativar_cliente(self) -> None:
        session = MagicMock()
        uc = obter_desativar_cliente(session)
        assert uc is not None

    def test_obter_adicionar_veiculo(self) -> None:
        session = MagicMock()
        uc = obter_adicionar_veiculo(session)
        assert uc is not None

    def test_obter_listar_veiculos(self) -> None:
        session = MagicMock()
        uc = obter_listar_veiculos(session)
        assert uc is not None

    def test_obter_remover_veiculo(self) -> None:
        session = MagicMock()
        uc = obter_remover_veiculo(session)
        assert uc is not None
