from __future__ import annotations

from unittest.mock import MagicMock

from src.cliente_veiculo.infraestrutura.adapters import (
    OrdemDeServicoSQLAlchemyAdapter,
)


class TestAdaptersClienteVeiculo:
    def test_init(self) -> None:
        session = MagicMock()
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter._session is session

    def test_existe_os_ativa_para_cliente_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_para_cliente(MagicMock()) is False

    def test_existe_os_ativa_para_cliente_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_para_cliente(MagicMock()) is True

    def test_existe_os_para_veiculo_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_para_veiculo(MagicMock()) is False

    def test_existe_os_para_veiculo_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_para_veiculo(MagicMock()) is True
        stmt = session.scalar.call_args.args[0]
        assert "status" not in str(stmt).lower()

    def test_existe_os_ativa_para_cliente_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_para_cliente(MagicMock()) is False

    def test_existe_os_para_veiculo_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_para_veiculo(MagicMock()) is False
