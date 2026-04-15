from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.catalogo_servicos.infraestrutura import mapping as mapping_module
from src.catalogo_servicos.infraestrutura.mapping import (
    iniciar_mapeamentos,
    servicos_oferecidos_table,
)
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata


class TestMappingCatalogo:
    def test_nome_tabela(self) -> None:
        assert servicos_oferecidos_table.name == "servicos_oferecidos"

    def test_colunas(self) -> None:
        colunas = {c.name for c in servicos_oferecidos_table.columns}
        assert colunas == {
            "id",
            "nome",
            "descricao",
            "preco_valor",
            "preco_moeda",
            "ativo",
        }

    def test_id_primary_key(self) -> None:
        assert servicos_oferecidos_table.c.id.primary_key

    def test_nome_nao_nullable(self) -> None:
        assert not servicos_oferecidos_table.c.nome.nullable

    def test_ativo_default(self) -> None:
        assert servicos_oferecidos_table.c.ativo.default is not None

    def test_iniciar_mapeamentos_e_idempotente(self) -> None:
        iniciar_mapeamentos()
        iniciar_mapeamentos()  # segunda chamada deve ser no-op
        assert mapping_module._mapeamento_iniciado is True


@pytest.fixture
def engine_sqlite() -> object:
    iniciar_mapeamentos()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)
        engine.dispose()


class TestEventosMapeamentoServico:
    def test_insert_e_load_decompoe_e_reconstroi_preco(
        self, engine_sqlite: object
    ) -> None:
        servico_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            servico = ServicoOferecido(
                id=servico_id,
                _nome="Troca de oleo",
                _descricao="Troca completa incluindo filtro",
                _preco=Dinheiro(valor=Decimal("150.00"), moeda="BRL"),
            )
            sessao_insert.add(servico)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_load:  # type: ignore[arg-type]
            carregado = sessao_load.get(ServicoOferecido, servico_id)
            assert carregado is not None
            assert isinstance(carregado._preco, Dinheiro)
            assert carregado._preco.valor == Decimal("150.00")
            assert carregado._preco.moeda == "BRL"
            assert carregado.nome == "Troca de oleo"

    def test_update_decompoe_preco(self, engine_sqlite: object) -> None:
        servico_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:  # type: ignore[arg-type]
            servico = ServicoOferecido(
                id=servico_id,
                _nome="Troca de oleo",
                _descricao="Troca completa",
                _preco=Dinheiro(valor=Decimal("100.00"), moeda="BRL"),
            )
            sessao_insert.add(servico)
            sessao_insert.commit()

        with Session(engine_sqlite) as sessao_update:  # type: ignore[arg-type]
            servico = sessao_update.get(ServicoOferecido, servico_id)
            assert servico is not None
            servico.atualizar(
                nome="Troca de oleo premium",
                descricao="Troca completa com filtro sintetico",
                preco=Dinheiro(valor=Decimal("250.00"), moeda="BRL"),
            )
            sessao_update.commit()

        with Session(engine_sqlite) as sessao_reload:  # type: ignore[arg-type]
            recarregado = sessao_reload.get(ServicoOferecido, servico_id)
            assert recarregado is not None
            assert recarregado._preco.valor == Decimal("250.00")
            assert recarregado.nome == "Troca de oleo premium"
