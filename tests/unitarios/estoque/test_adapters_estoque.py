from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.compartilhado.infraestrutura.database import metadata
from src.estoque.aplicacao.ports import OrdemDeServicoPort
from src.estoque.infraestrutura.adapters import OrdemDeServicoSQLAlchemyAdapter
from src.ordem_servico.infraestrutura.mapping import (
    itens_da_ordem_table,
    ordens_de_servico_table,
)


@pytest.fixture
def engine_sqlite() -> Generator[Engine, None, None]:
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)
        engine.dispose()


class TestAdaptersEstoque:
    def test_retorna_false_quando_nao_ha_os(self, engine_sqlite: Engine) -> None:
        with Session(engine_sqlite) as session:
            adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
            assert adapter.existe_os_ativa_com_item_estoque(uuid4()) is False

    def test_retorna_true_quando_os_ativa_referencia_item(
        self, engine_sqlite: Engine
    ) -> None:
        item_estoque_id = uuid4()
        ordem_id = uuid4()
        cliente_id = uuid4()
        veiculo_id = uuid4()

        with Session(engine_sqlite) as session:
            session.execute(
                ordens_de_servico_table.insert().values(
                    id=ordem_id,
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                    status="em_execucao",
                )
            )
            session.execute(
                itens_da_ordem_table.insert().values(
                    id=uuid4(),
                    ordem_id=ordem_id,
                    item_estoque_id=item_estoque_id,
                    quantidade=2,
                    preco_unitario_valor=10,
                    preco_unitario_moeda="BRL",
                )
            )
            session.commit()

            adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
            assert adapter.existe_os_ativa_com_item_estoque(item_estoque_id) is True

    def test_retorna_false_quando_os_esta_em_estado_terminal(
        self, engine_sqlite: Engine
    ) -> None:
        item_estoque_id = uuid4()
        ordem_entregue_id = uuid4()
        ordem_cancelada_id = uuid4()
        cliente_id = uuid4()
        veiculo_id = uuid4()

        with Session(engine_sqlite) as session:
            for ordem_id, status in (
                (ordem_entregue_id, "entregue"),
                (ordem_cancelada_id, "cancelada"),
            ):
                session.execute(
                    ordens_de_servico_table.insert().values(
                        id=ordem_id,
                        cliente_id=cliente_id,
                        veiculo_id=veiculo_id,
                        status=status,
                    )
                )
                session.execute(
                    itens_da_ordem_table.insert().values(
                        id=uuid4(),
                        ordem_id=ordem_id,
                        item_estoque_id=item_estoque_id,
                        quantidade=1,
                        preco_unitario_valor=10,
                        preco_unitario_moeda="BRL",
                    )
                )
            session.commit()

            adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
            assert adapter.existe_os_ativa_com_item_estoque(item_estoque_id) is False

    def test_retorna_false_para_outro_item_estoque(self, engine_sqlite: Engine) -> None:
        outro_item_id = uuid4()
        ordem_id = uuid4()
        cliente_id = uuid4()
        veiculo_id = uuid4()

        with Session(engine_sqlite) as session:
            session.execute(
                ordens_de_servico_table.insert().values(
                    id=ordem_id,
                    cliente_id=cliente_id,
                    veiculo_id=veiculo_id,
                    status="em_execucao",
                )
            )
            session.execute(
                itens_da_ordem_table.insert().values(
                    id=uuid4(),
                    ordem_id=ordem_id,
                    item_estoque_id=outro_item_id,
                    quantidade=1,
                    preco_unitario_valor=10,
                    preco_unitario_moeda="BRL",
                )
            )
            session.commit()

            adapter = OrdemDeServicoSQLAlchemyAdapter(session=session)
            assert adapter.existe_os_ativa_com_item_estoque(uuid4()) is False


class TestOrdemDeServicoPortProtocol:
    def test_protocolo_define_metodo(self) -> None:
        assert hasattr(OrdemDeServicoPort, "existe_os_ativa_com_item_estoque")
