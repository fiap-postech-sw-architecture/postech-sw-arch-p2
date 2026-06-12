from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from src.cliente_veiculo.infraestrutura.repository import (
    ClienteSQLAlchemyRepository,
)


class TestClienteSQLAlchemyRepository:
    def test_obter_por_id_delega_para_session(self) -> None:
        session = MagicMock()
        repo = ClienteSQLAlchemyRepository(session=session)
        cliente_id = uuid4()
        repo.obter_por_id(cliente_id)
        session.get.assert_called_once()

    def test_salvar_adiciona_e_flush(self) -> None:
        session = MagicMock()
        repo = ClienteSQLAlchemyRepository(session=session)
        cliente = MagicMock()
        repo.salvar(cliente)
        session.add.assert_called_once_with(cliente)
        session.flush.assert_called_once()

    def test_contar_usa_count(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 5
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.contar() == 5

    def test_contar_retorna_zero_quando_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

    def test_protocolo_metodos_existem(self) -> None:
        assert hasattr(ClienteSQLAlchemyRepository, "obter_por_id")
        assert hasattr(ClienteSQLAlchemyRepository, "salvar")
        assert hasattr(ClienteSQLAlchemyRepository, "listar")
        assert hasattr(ClienteSQLAlchemyRepository, "contar")
        assert hasattr(ClienteSQLAlchemyRepository, "obter_por_documento")
        assert hasattr(ClienteSQLAlchemyRepository, "placa_existe")

    def test_placa_existe_retorna_true(self) -> None:
        from src.cliente_veiculo.dominio.placa import Placa

        session = MagicMock()
        session.scalar.return_value = 1
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.placa_existe(Placa(valor="ABC1D23")) is True

    def test_placa_existe_retorna_false(self) -> None:
        from src.cliente_veiculo.dominio.placa import Placa

        session = MagicMock()
        session.scalar.return_value = 0
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.placa_existe(Placa(valor="ABC1D23")) is False

    def test_placa_existe_com_exclusao_de_cliente(self) -> None:
        from src.cliente_veiculo.dominio.placa import Placa

        session = MagicMock()
        session.scalar.return_value = 0
        repo = ClienteSQLAlchemyRepository(session=session)
        cid = uuid4()
        result = repo.placa_existe(Placa(valor="ABC1D23"), excluir_cliente_id=cid)
        assert result is False

    def test_placa_existe_retorna_false_quando_none(self) -> None:
        from src.cliente_veiculo.dominio.placa import Placa

        session = MagicMock()
        session.scalar.return_value = None
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.placa_existe(Placa(valor="ABC1D23")) is False

    def test_listar_delega_para_scalars(self) -> None:
        session = MagicMock()
        session.scalars.return_value = iter([MagicMock(), MagicMock()])
        repo = ClienteSQLAlchemyRepository(session=session)
        resultado = repo.listar(offset=10, limit=5)
        assert len(resultado) == 2
        session.scalars.assert_called_once()

    def test_obter_por_documento_usa_hash(self) -> None:
        from src.cliente_veiculo.dominio.cpf import CPF

        session = MagicMock()
        cliente_mock = MagicMock()
        session.scalars.return_value.first.return_value = cliente_mock
        repo = ClienteSQLAlchemyRepository(session=session)
        resultado = repo.obter_por_documento(CPF(numero="21249722519"))
        assert resultado is cliente_mock
        session.scalars.assert_called_once()

    def test_obter_por_documento_retorna_none_quando_nao_encontra(self) -> None:
        from src.cliente_veiculo.dominio.cpf import CPF

        session = MagicMock()
        session.scalars.return_value.first.return_value = None
        repo = ClienteSQLAlchemyRepository(session=session)
        assert repo.obter_por_documento(CPF(numero="21249722519")) is None
