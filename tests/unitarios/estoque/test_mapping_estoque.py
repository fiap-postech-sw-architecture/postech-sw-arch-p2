from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata
from src.estoque.dominio.item_estoque import ItemEstoque
from src.estoque.infraestrutura import mapping as mapping_module
from src.estoque.infraestrutura.mapping import (
    iniciar_mapeamentos,
    itens_estoque_table,
)


class TestMappingEstoque:
    def test_nome_tabela(self) -> None:
        assert itens_estoque_table.name == "itens_estoque"

    def test_colunas(self) -> None:
        colunas = {c.name for c in itens_estoque_table.columns}
        assert colunas == {
            "id",
            "nome",
            "descricao",
            "quantidade",
            "preco_unitario_valor",
            "preco_unitario_moeda",
            "ativo",
        }

    def test_id_primary_key(self) -> None:
        assert itens_estoque_table.c.id.primary_key

    def test_quantidade_nao_nullable(self) -> None:
        assert not itens_estoque_table.c.quantidade.nullable

    def test_ativo_default(self) -> None:
        assert itens_estoque_table.c.ativo.default is not None

    def test_iniciar_mapeamentos_e_idempotente(self) -> None:
        iniciar_mapeamentos()
        iniciar_mapeamentos()
        assert mapping_module._mapeamento_iniciado is True


@pytest.fixture
def engine_sqlite() -> Generator[Engine]:
    iniciar_mapeamentos()
    engine = create_engine("sqlite:///:memory:")
    # Cria apenas `itens_estoque`, nao o metadata compartilhado inteiro.
    # Rodando so o dir de estoque, importar o adapter de estoque
    # (em test_adapters_estoque.py) registra `ordens_de_servico` no metadata
    # compartilhado — cuja FK aponta para `clientes`/`veiculos`, que nunca sao
    # importadas nesse subconjunto — e um `create_all` cru falharia com
    # NoReferencedTableError. `itens_estoque` nao tem FKs, entao limitar o
    # create/drop a ela mantem este teste hermetico e imune a ordem de coleta.
    metadata.create_all(engine, tables=[itens_estoque_table])
    try:
        yield engine
    finally:
        metadata.drop_all(engine, tables=[itens_estoque_table])
        engine.dispose()


class TestEventosMapeamentoEstoque:
    def test_insert_e_load_decompoe_e_reconstroi_preco(
        self, engine_sqlite: Engine
    ) -> None:
        item_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:
            item = ItemEstoque(
                id=item_id,
                _nome="Filtro de oleo",
                _descricao="Filtro completo",
                _quantidade=10,
                _preco_unitario=Dinheiro(valor=Decimal("25.50"), moeda="BRL"),
            )
            sessao_insert.add(item)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:
            carregado = sessao_load.get(ItemEstoque, item_id)
            assert carregado is not None
            assert isinstance(carregado._preco_unitario, Dinheiro)
            assert carregado._preco_unitario.valor == Decimal("25.50")
            assert carregado._preco_unitario.moeda == "BRL"
            assert carregado.nome == "Filtro de oleo"
            assert carregado.quantidade == 10

    def test_instancia_carregada_rejeita_mutacao_de_id(
        self, engine_sqlite: Engine
    ) -> None:
        # Regressao: SQLAlchemy nao chama __post_init__ ao reidratar,
        # entao o listener ``load`` precisa ativar _id_atribuido para
        # que Entity.__setattr__ continue bloqueando mutacao de id.
        from uuid import uuid4

        item_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:
            item = ItemEstoque(
                id=item_id,
                _nome="Filtro",
                _descricao="Desc",
                _quantidade=1,
                _preco_unitario=Dinheiro(valor=Decimal("10.00"), moeda="BRL"),
            )
            sessao_insert.add(item)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:
            carregado = sessao_load.get(ItemEstoque, item_id)
            assert carregado is not None
            with pytest.raises(
                AttributeError, match="nao pode ser alterada apos criacao"
            ):
                carregado.id = uuid4()

    def test_update_decompoe_preco_e_persiste_ativo(
        self, engine_sqlite: Engine
    ) -> None:
        item_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:
            item = ItemEstoque(
                id=item_id,
                _nome="Filtro de oleo",
                _descricao="Filtro padrao",
                _quantidade=5,
                _preco_unitario=Dinheiro(valor=Decimal("20.00"), moeda="BRL"),
            )
            sessao_insert.add(item)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_update:
            item = sessao_update.get(ItemEstoque, item_id)
            assert item is not None
            item.atualizar(
                nome="Filtro premium",
                descricao="Filtro sintetico",
                preco_unitario=Dinheiro(valor=Decimal("45.00"), moeda="BRL"),
            )
            item.desativar()
            sessao_update.commit()

        with Session(engine_sqlite) as sessao_reload:
            recarregado = sessao_reload.get(ItemEstoque, item_id)
            assert recarregado is not None
            assert recarregado._preco_unitario.valor == Decimal("45.00")
            assert recarregado.nome == "Filtro premium"
            assert recarregado.ativo is False
