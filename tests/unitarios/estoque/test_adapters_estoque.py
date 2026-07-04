from __future__ import annotations

from unittest.mock import MagicMock

from src.estoque.aplicacao.ports import OrdemDeServicoPort
from src.estoque.infraestrutura.adapters import OrdemDeServicoSQLAlchemyAdapter


class TestAdaptersEstoque:
    def test_existe_os_ativa_com_item_estoque_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_com_item_estoque(MagicMock()) is False

    def test_existe_os_ativa_com_item_estoque_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_com_item_estoque(MagicMock()) is True

    def test_existe_os_ativa_com_item_estoque_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
        assert adapter.existe_os_ativa_com_item_estoque(MagicMock()) is False


class TestOrdemDeServicoPortProtocol:
    def test_protocolo_define_metodo(self) -> None:
        assert hasattr(OrdemDeServicoPort, "existe_os_ativa_com_item_estoque")
