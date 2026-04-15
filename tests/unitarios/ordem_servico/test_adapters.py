from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.compartilhado.dominio.exceptions import EntidadeNaoEncontradaException
from src.ordem_servico.infraestrutura.adapters import (
    CatalogoSQLAlchemyAdapter,
    ClienteSQLAlchemyAdapter,
    EstoqueSQLAlchemyAdapter,
)


class TestAdapters:
    def test_estoque_adapter_aceita_session(self) -> None:
        session = MagicMock()
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        assert adapter._session is session

    def test_catalogo_adapter_aceita_session(self) -> None:
        session = MagicMock()
        adapter = CatalogoSQLAlchemyAdapter(session=session)
        assert adapter._session is session

    def test_cliente_adapter_aceita_session(self) -> None:
        session = MagicMock()
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter._session is session

    def test_estoque_metodos_existem(self) -> None:
        assert hasattr(EstoqueSQLAlchemyAdapter, "reservar")
        assert hasattr(EstoqueSQLAlchemyAdapter, "liberar")

    def test_catalogo_metodos_existem(self) -> None:
        assert hasattr(CatalogoSQLAlchemyAdapter, "obter_servico")

    def test_cliente_metodos_existem(self) -> None:
        assert hasattr(ClienteSQLAlchemyAdapter, "cliente_existe")
        assert hasattr(ClienteSQLAlchemyAdapter, "veiculo_existe")


class TestEstoqueSQLAlchemyAdapter:
    def test_reservar_item_encontrado_chama_reservar(self) -> None:
        session = MagicMock()
        mock_item = MagicMock()
        session.get.return_value = mock_item
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        item_id = uuid4()
        adapter.reservar(item_id, 3)
        mock_item.reservar.assert_called_once_with(3)

    def test_reservar_item_nao_encontrado_levanta_excecao(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        with pytest.raises(
            EntidadeNaoEncontradaException,
            match="Item de estoque nao encontrado",
        ):
            adapter.reservar(uuid4(), 1)

    def test_liberar_item_encontrado_chama_liberar(self) -> None:
        session = MagicMock()
        mock_item = MagicMock()
        session.get.return_value = mock_item
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        item_id = uuid4()
        adapter.liberar(item_id, 5)
        mock_item.liberar.assert_called_once_with(5)

    def test_liberar_item_nao_encontrado_levanta_excecao(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        with pytest.raises(
            EntidadeNaoEncontradaException,
            match="Item de estoque nao encontrado",
        ):
            adapter.liberar(uuid4(), 1)


class TestCatalogoSQLAlchemyAdapter:
    def test_obter_servico_encontrado_retorna_dto(self) -> None:
        session = MagicMock()
        mock_servico = MagicMock()
        mock_servico.id = uuid4()
        mock_servico.nome = "Troca de oleo"
        mock_servico.preco = MagicMock()
        mock_servico.ativo = True
        session.get.return_value = mock_servico
        adapter = CatalogoSQLAlchemyAdapter(session=session)
        result = adapter.obter_servico(mock_servico.id)
        assert result is not None
        assert result.id == mock_servico.id
        assert result.nome == "Troca de oleo"
        assert result.ativo is True

    def test_obter_servico_nao_encontrado_retorna_none(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        adapter = CatalogoSQLAlchemyAdapter(session=session)
        result = adapter.obter_servico(uuid4())
        assert result is None


class TestClienteSQLAlchemyAdapter:
    def test_cliente_existe_retorna_true(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock()
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.cliente_existe(uuid4()) is True

    def test_cliente_existe_retorna_false(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.cliente_existe(uuid4()) is False

    def test_veiculo_existe_retorna_true(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock()
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.veiculo_existe(uuid4()) is True

    def test_veiculo_existe_retorna_false(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.veiculo_existe(uuid4()) is False
