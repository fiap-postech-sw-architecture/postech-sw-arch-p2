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


@pytest.fixture(autouse=True)
def _mapeamento_estoque_registrado() -> None:
    """Registra o mapeamento imperativo de ``ItemEstoque`` (idempotente).

    ``reservar``/``liberar`` agora carregam o item via
    ``ItemEstoqueSQLAlchemyRepository.obter_por_id(com_lock=True)`` (issue
    #83), cujo ramo de lock monta ``select(ItemEstoque).with_for_update()`` —
    isso exige a classe MAPEADA. Sem registrar aqui, o teste so passaria por
    efeito colateral da ordem de coleta da suite (fragil). ``iniciar_
    mapeamentos`` e init-once, entao chamar sempre e seguro.
    """
    from src.estoque.infraestrutura.mapping import iniciar_mapeamentos

    iniciar_mapeamentos()


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
        assert hasattr(EstoqueSQLAlchemyAdapter, "obter_itens_em_lote")

    def test_catalogo_metodos_existem(self) -> None:
        assert hasattr(CatalogoSQLAlchemyAdapter, "obter_servico")
        assert hasattr(CatalogoSQLAlchemyAdapter, "obter_servicos_em_lote")

    def test_cliente_metodos_existem(self) -> None:
        assert hasattr(ClienteSQLAlchemyAdapter, "cliente_existe")
        assert hasattr(ClienteSQLAlchemyAdapter, "veiculo_pertence_ao_cliente")


def _mock_session_com_lock(item: object | None) -> MagicMock:
    """Session fake que devolve ``item`` pelo caminho ``com_lock=True``.

    ``reservar``/``liberar`` agora carregam o item via
    ``ItemEstoqueSQLAlchemyRepository.obter_por_id(com_lock=True)`` (issue
    #83), que executa ``session.scalars(select(...).with_for_update())
    .one_or_none()`` em vez do antigo ``session.get``. O fake espelha esse
    caminho. O teste de integracao prova o FOR UPDATE real.
    """
    session = MagicMock()
    session.scalars.return_value.one_or_none.return_value = item
    return session


class TestEstoqueSQLAlchemyAdapter:
    def test_reservar_item_encontrado_chama_reservar(self) -> None:
        mock_item = MagicMock()
        session = _mock_session_com_lock(mock_item)
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        item_id = uuid4()
        adapter.reservar(item_id, 3)
        mock_item.reservar.assert_called_once_with(3)
        # Carrega com FOR UPDATE (caminho com_lock), nao via session.get cru.
        session.scalars.assert_called_once()
        session.get.assert_not_called()

    def test_reservar_item_nao_encontrado_levanta_excecao(self) -> None:
        session = _mock_session_com_lock(None)
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        with pytest.raises(
            EntidadeNaoEncontradaException,
            match="Item de estoque nao encontrado",
        ):
            adapter.reservar(uuid4(), 1)

    def test_liberar_item_encontrado_chama_liberar(self) -> None:
        mock_item = MagicMock()
        session = _mock_session_com_lock(mock_item)
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        item_id = uuid4()
        adapter.liberar(item_id, 5)
        mock_item.liberar.assert_called_once_with(5)
        session.scalars.assert_called_once()
        session.get.assert_not_called()

    def test_liberar_item_nao_encontrado_levanta_excecao(self) -> None:
        session = _mock_session_com_lock(None)
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

    def test_obter_servicos_em_lote_set_vazio_nao_consulta_db(self) -> None:
        """Set vazio retorna dict vazio sem chamar ``session.execute``.

        O caminho com ``select(...)`` exige o mapping imperativo
        registrado e fica coberto pela suite de integracao.
        """
        session = MagicMock()
        adapter = CatalogoSQLAlchemyAdapter(session=session)
        assert adapter.obter_servicos_em_lote(set()) == {}
        session.execute.assert_not_called()


class TestEstoqueSQLAlchemyAdapterEmLote:
    def test_obter_itens_em_lote_set_vazio_nao_consulta_db(self) -> None:
        """Set vazio retorna dict vazio sem chamar ``session.execute``.

        O caminho com ``select(...)`` exige o mapping imperativo
        registrado e fica coberto pela suite de integracao.
        """
        session = MagicMock()
        adapter = EstoqueSQLAlchemyAdapter(session=session)
        assert adapter.obter_itens_em_lote(set()) == {}
        session.execute.assert_not_called()


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

    def test_veiculo_pertence_ao_cliente_retorna_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = True
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.veiculo_pertence_ao_cliente(uuid4(), uuid4()) is True

    def test_veiculo_pertence_ao_cliente_retorna_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = False
        adapter = ClienteSQLAlchemyAdapter(session=session)
        assert adapter.veiculo_pertence_ao_cliente(uuid4(), uuid4()) is False
