from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# Registra `clientes` e `veiculos` no metadata para as FKs da OS resolverem.
import src.cliente_veiculo.infraestrutura.mapping  # noqa: F401
from src.compartilhado.infraestrutura.database import metadata
from src.compartilhado.infraestrutura.encryption import EncryptionService
from src.ordem_servico.infraestrutura.mapping import (
    iniciar_mapeamentos,
    ordens_de_servico_table,
)
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)


class TestRepositoryOS:
    def test_init(self) -> None:
        session = MagicMock()
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo._session is session

    def test_obter_por_id(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        result = repo.obter_por_id(MagicMock())
        assert result is None

    def test_salvar(self) -> None:
        session = MagicMock()
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        entity = MagicMock()
        repo.salvar(entity)
        session.add.assert_called_once_with(entity)
        session.flush.assert_called_once()

    def test_contar(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 7
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.contar() == 7

    def test_contar_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.contar() == 0

    def test_contar_por_status(self) -> None:
        session = MagicMock()
        session.execute.return_value.all.return_value = [
            ("recebida", 2),
            ("em_diagnostico", 3),
        ]
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        result = repo.contar_por_status()
        assert result == {"recebida": 2, "em_diagnostico": 3}

    def test_existe_ativa_para_cliente_true(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 1
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_cliente(MagicMock()) is True

    def test_existe_ativa_para_cliente_false(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_cliente(MagicMock()) is False

    def test_existe_ativa_para_veiculo(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_para_veiculo(MagicMock()) is False

    def test_existe_ativa_com_item_estoque(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 0
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.existe_ativa_com_item_estoque(MagicMock()) is False

    def test_calcular_tempo_medio_none(self) -> None:
        session = MagicMock()
        session.scalar.return_value = None
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.calcular_tempo_medio_execucao() is None

    def test_calcular_tempo_medio_com_valor(self) -> None:
        session = MagicMock()
        session.scalar.return_value = 120.5
        repo = OrdemDeServicoSQLAlchemyRepository(session=session)
        assert repo.calcular_tempo_medio_execucao() == 120.5


@pytest.fixture
def engine_sqlite() -> Generator[Engine]:
    iniciar_mapeamentos()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)
        engine.dispose()


class TestRepositoryOSIntegracao:
    def test_listar_paginado_ordenado_por_criado_em_desc(
        self, engine_sqlite: Engine
    ) -> None:
        cliente_id = uuid4()
        veiculo_id = uuid4()
        base = datetime.now(UTC)

        with Session(engine_sqlite) as sessao_setup:
            for i in range(3):
                session_stmt = ordens_de_servico_table.insert().values(
                    id=uuid4(),
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                    status="recebida",
                    orcamento_json=None,
                    criado_em=base + timedelta(minutes=i),
                    atualizado_em=base + timedelta(minutes=i),
                )
                sessao_setup.execute(session_stmt)
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            pagina1 = repo.listar(offset=0, limit=2)
            assert len(pagina1) == 2
            # Ordem decrescente: o mais recente primeiro
            assert pagina1[0].criado_em > pagina1[1].criado_em

            pagina2 = repo.listar(offset=2, limit=2)
            assert len(pagina2) == 1

    def test_obter_por_placa_e_documento_encontra_ordem(
        self, engine_sqlite: Engine
    ) -> None:
        from src.cliente_veiculo.infraestrutura.mapping import (
            clientes_table,
            veiculos_table,
        )

        enc = EncryptionService.instance()
        documento_raw = "12345678901"
        placa_raw = "ABC1D23"
        cliente_id = uuid4()
        veiculo_id = uuid4()
        doc_encrypted = enc.encrypt(documento_raw)
        doc_hash = enc.hash_deterministic(documento_raw)

        with Session(engine_sqlite) as sessao_setup:
            sessao_setup.execute(
                clientes_table.insert().values(
                    id=cliente_id,
                    nome="Cliente Teste",
                    documento=doc_encrypted,
                    documento_hash=doc_hash,
                    tipo_documento="cpf",
                    contato="(11) 99999-9999",
                    ativo=True,
                )
            )
            sessao_setup.execute(
                veiculos_table.insert().values(
                    id=veiculo_id,
                    placa=placa_raw,
                    marca="Fiat",
                    modelo="Uno",
                    ano=2020,
                    cliente_id=cliente_id,
                )
            )
            now = datetime.now(UTC)
            sessao_setup.execute(
                ordens_de_servico_table.insert().values(
                    id=uuid4(),
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                    status="recebida",
                    orcamento_json=None,
                    criado_em=now,
                    atualizado_em=now,
                )
            )
            sessao_setup.commit()

        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            resultados = repo.obter_por_placa_e_documento(
                placa=placa_raw, documento=documento_raw
            )
            assert len(resultados) == 1
            assert resultados[0].cliente_id == cliente_id
            assert resultados[0].veiculo_id == veiculo_id

    def test_obter_por_placa_e_documento_retorna_vazio_quando_nao_casa(
        self, engine_sqlite: Engine
    ) -> None:
        with Session(engine_sqlite) as sessao_query:
            repo = OrdemDeServicoSQLAlchemyRepository(session=sessao_query)
            resultados = repo.obter_por_placa_e_documento(
                placa="XYZ9A99", documento="00000000000"
            )
            assert resultados == []
