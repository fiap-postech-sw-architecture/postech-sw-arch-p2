from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

# Importar o mapping de cliente_veiculo apenas para registrar as tabelas
# `clientes` e `veiculos` no metadata compartilhado; as FKs da OS apontam
# para esses destinos e `metadata.create_all` precisa resolve-los.
import src.cliente_veiculo.infraestrutura.mapping  # noqa: F401
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.infraestrutura.database import metadata
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura import mapping as os_mapping_module
from src.ordem_servico.infraestrutura.mapping import (
    iniciar_mapeamentos,
    itens_da_ordem_table,
    ordens_de_servico_table,
)


class TestMappingOS:
    def test_ordens_nome_tabela(self) -> None:
        assert ordens_de_servico_table.name == "ordens_de_servico"

    def test_ordens_colunas(self) -> None:
        colunas = {c.name for c in ordens_de_servico_table.columns}
        assert colunas == {
            "id",
            "cliente_id",
            "veiculo_id",
            "status",
            "orcamento_json",
            "criado_em",
            "atualizado_em",
        }

    def test_ordens_id_primary_key(self) -> None:
        assert ordens_de_servico_table.c.id.primary_key

    def test_itens_nome_tabela(self) -> None:
        assert itens_da_ordem_table.name == "itens_da_ordem"

    def test_itens_colunas(self) -> None:
        colunas = {c.name for c in itens_da_ordem_table.columns}
        assert colunas == {
            "id",
            "ordem_id",
            "servico_catalogo_id",
            "item_estoque_id",
            "descricao",
            "quantidade",
            "preco_unitario_valor",
            "preco_unitario_moeda",
        }

    def test_itens_id_primary_key(self) -> None:
        assert itens_da_ordem_table.c.id.primary_key

    def test_ordem_id_foreign_key(self) -> None:
        fk_names = {
            fk.target_fullname for fk in itens_da_ordem_table.c.ordem_id.foreign_keys
        }
        assert "ordens_de_servico.id" in fk_names

    def test_status_default(self) -> None:
        assert ordens_de_servico_table.c.status.default is not None

    def test_iniciar_mapeamentos_e_idempotente(self) -> None:
        iniciar_mapeamentos()
        iniciar_mapeamentos()
        assert os_mapping_module._mapeamento_iniciado is True


@pytest.fixture
def engine_sqlite() -> Generator[Engine, None, None]:
    iniciar_mapeamentos()
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        metadata.drop_all(engine)
        engine.dispose()


def _criar_item(preco: Dinheiro | None = None, quantidade: int = 1) -> ItemDaOrdem:
    if preco is None:
        preco = Dinheiro(valor=Decimal("50.00"), moeda="BRL")
    return ItemDaOrdem(
        _servico_catalogo_id=uuid4(),
        _descricao="Troca de oleo",
        _quantidade=quantidade,
        _preco_unitario=preco,
    )


class TestEventosMapeamentoOS:
    def test_insert_e_load_preservam_status_e_ids(self, engine_sqlite: Engine) -> None:
        cliente_id = uuid4()
        veiculo_id = uuid4()
        with Session(engine_sqlite) as sessao_insert:
            ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
            ordem.limpar_eventos()
            sessao_insert.add(ordem)
            sessao_insert.commit()
            ordem_id = ordem.id

        with Session(engine_sqlite) as sessao_load:
            carregado = sessao_load.get(OrdemDeServico, ordem_id)
            assert carregado is not None
            assert carregado.status == StatusOrdem.RECEBIDA
            assert carregado.cliente_id == cliente_id
            assert carregado.veiculo_id == veiculo_id
            assert carregado.orcamento is None

    def test_instancia_carregada_rejeita_mutacao_de_id(
        self, engine_sqlite: Engine
    ) -> None:
        """Regressao PR #60: SQLAlchemy nao chama __post_init__ ao reidratar,
        entao o listener ``load`` precisa ativar _id_atribuido para que
        Entity.__setattr__ continue bloqueando mutacao de id."""
        with Session(engine_sqlite) as sessao_insert:
            ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
            ordem.limpar_eventos()
            sessao_insert.add(ordem)
            sessao_insert.commit()
            ordem_id = ordem.id

        with Session(engine_sqlite) as sessao_load:
            carregado = sessao_load.get(OrdemDeServico, ordem_id)
            assert carregado is not None
            with pytest.raises(
                AttributeError, match="nao pode ser alterada apos criacao"
            ):
                carregado.id = uuid4()

    def test_update_transicao_status_persiste(self, engine_sqlite: Engine) -> None:
        with Session(engine_sqlite) as sessao_insert:
            ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
            ordem.adicionar_item(_criar_item())
            ordem.limpar_eventos()
            sessao_insert.add(ordem)
            sessao_insert.commit()
            ordem_id = ordem.id

        with Session(engine_sqlite) as sessao_update:
            carregada = sessao_update.get(OrdemDeServico, ordem_id)
            assert carregada is not None
            carregada.iniciar_diagnostico()
            carregada.limpar_eventos()
            sessao_update.commit()

        with Session(engine_sqlite) as sessao_reload:
            recarregada = sessao_reload.get(OrdemDeServico, ordem_id)
            assert recarregada is not None
            assert recarregada.status == StatusOrdem.EM_DIAGNOSTICO

    def test_item_da_ordem_decompoe_e_reconstroi_preco(
        self, engine_sqlite: Engine
    ) -> None:
        preco = Dinheiro(valor=Decimal("75.50"), moeda="BRL")
        with Session(engine_sqlite) as sessao_insert:
            ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
            ordem.adicionar_item(_criar_item(preco=preco, quantidade=3))
            ordem.limpar_eventos()
            sessao_insert.add(ordem)
            sessao_insert.commit()
            ordem_id = ordem.id

        with Session(engine_sqlite) as sessao_load:
            carregada = sessao_load.get(OrdemDeServico, ordem_id)
            assert carregada is not None
            assert len(carregada.itens) == 1
            item = carregada.itens[0]
            assert isinstance(item.preco_unitario, Dinheiro)
            assert item.preco_unitario.valor == Decimal("75.50")
            assert item.preco_unitario.moeda == "BRL"
            assert item.quantidade == 3

    def test_orcamento_json_round_trip(self, engine_sqlite: Engine) -> None:
        """Cobre a serializacao/desserializacao do orcamento em JSON via
        os listeners before_insert/load da OrdemDeServico."""
        with Session(engine_sqlite) as sessao_insert:
            ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
            ordem.adicionar_item(
                _criar_item(
                    preco=Dinheiro(valor=Decimal("100.00"), moeda="BRL"),
                    quantidade=2,
                )
            )
            ordem.iniciar_diagnostico()
            ordem.gerar_orcamento()
            ordem.limpar_eventos()
            sessao_insert.add(ordem)
            sessao_insert.commit()
            ordem_id = ordem.id

        with Session(engine_sqlite) as sessao_load:
            carregada = sessao_load.get(OrdemDeServico, ordem_id)
            assert carregada is not None
            assert carregada.status == StatusOrdem.AGUARDANDO_APROVACAO
            assert carregada.orcamento is not None
            assert carregada.orcamento.total == Dinheiro(
                valor=Decimal("200.00"), moeda="BRL"
            )
            assert len(carregada.orcamento.itens) == 1
            linha = carregada.orcamento.itens[0]
            assert linha.quantidade == 2
            assert linha.preco_unitario.valor == Decimal("100.00")
            assert linha.subtotal.valor == Decimal("200.00")
            assert isinstance(carregada.orcamento.gerado_em, datetime)
            assert carregada.orcamento.gerado_em.tzinfo is UTC
