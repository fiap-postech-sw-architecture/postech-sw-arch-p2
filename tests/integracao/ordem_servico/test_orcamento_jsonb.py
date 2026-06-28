"""Integracao: snapshot do orcamento como JSONB nativo (TD-005).

Prova que a coluna ``ordens_de_servico.orcamento_json`` guarda ``jsonb``
nativo (um ``dict``) e NAO uma string JSON duplamente codificada — ou seja,
que a camada manual ``json.dumps``/``json.loads`` foi de fato removida e o
``dict`` cru e passado para a coluna (mesmo padrao de ``outbox.payload``).

Roda contra Postgres real (testcontainers) porque os operadores ``jsonb``
(``jsonb_typeof``, ``->>``) so existem no PostgreSQL: no sqlite o tipo
degrada para ``JSON`` (TEXT) e essas asserts nao teriam significado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.repository import (
    OrdemDeServicoSQLAlchemyRepository,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integracao


def _criar_item(descricao: str, preco: Dinheiro, quantidade: int) -> ItemDaOrdem:
    from uuid import uuid4

    return ItemDaOrdem(
        _servico_catalogo_id=uuid4(),
        _descricao=descricao,
        _quantidade=quantidade,
        _preco_unitario=preco,
    )


def _os_com_orcamento(session: Session) -> UUID:
    """OS aprovada com orcamento de 2 linhas, persistida via repository real."""
    cliente = Cliente(
        _nome="Cliente JSONB",
        _documento=CPF(numero="21249722519"),
        _contato="11999990000",
    )
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    ClienteSQLAlchemyRepository(session=session).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor="JSB1234"), marca="Fiat", modelo="Uno", ano=2020
    )
    session.flush()
    veiculo = cliente.veiculos[0]

    ordem = OrdemDeServico.criar(cliente_id=cliente.id, veiculo_id=veiculo.id)
    ordem.adicionar_item(
        _criar_item(
            "Troca de oleo",
            Dinheiro(valor=Decimal("120.00"), moeda="BRL"),
            quantidade=2,
        )
    )
    ordem.adicionar_item(
        _criar_item(
            "Alinhamento",
            Dinheiro(valor=Decimal("80.50"), moeda="BRL"),
            quantidade=1,
        )
    )
    ordem.iniciar_diagnostico()
    ordem.gerar_orcamento()
    ordem.limpar_eventos()

    OrdemDeServicoSQLAlchemyRepository(session=session).salvar(ordem)
    return ordem.id


class TestOrcamentoJsonb:
    def test_orcamento_vo_round_trip_em_postgres(self, session: Session) -> None:
        """O VO ``Orcamento`` reidrata identico apos save/reload no Postgres."""
        ordem_id = _os_com_orcamento(session)

        # Expira para forcar releitura do banco (e nao do identity map).
        session.expire_all()
        recarregada = OrdemDeServicoSQLAlchemyRepository(session=session).obter_por_id(
            ordem_id
        )

        assert recarregada is not None
        assert recarregada.status == StatusOrdem.AGUARDANDO_APROVACAO
        orcamento = recarregada.orcamento
        assert orcamento is not None
        # total = 120.00 * 2 + 80.50 * 1 = 320.50
        assert orcamento.total == Dinheiro(valor=Decimal("320.50"), moeda="BRL")
        assert len(orcamento.itens) == 2
        por_descricao = {linha.descricao: linha for linha in orcamento.itens}
        oleo = por_descricao["Troca de oleo"]
        assert oleo.quantidade == 2
        assert oleo.preco_unitario == Dinheiro(valor=Decimal("120.00"), moeda="BRL")
        assert oleo.subtotal == Dinheiro(valor=Decimal("240.00"), moeda="BRL")
        alinhamento = por_descricao["Alinhamento"]
        assert alinhamento.quantidade == 1
        assert alinhamento.preco_unitario == Dinheiro(
            valor=Decimal("80.50"), moeda="BRL"
        )
        assert alinhamento.subtotal == Dinheiro(valor=Decimal("80.50"), moeda="BRL")
        assert orcamento.gerado_em is not None
        assert orcamento.versao_schema == 1

    def test_coluna_e_jsonb_nativo_nao_string_duplo_codificada(
        self, session: Session
    ) -> None:
        """A coluna guarda jsonb (``dict``), nao uma string JSON aninhada.

        Se a camada ``json.dumps`` tivesse sobrevivido, o valor seria uma
        string JSON dentro do jsonb -> ``jsonb_typeof`` retornaria
        ``'string'`` e o operador ``->>`` nao alcancaria as chaves. Com o
        ``dict`` cru, ``jsonb_typeof`` e ``'object'`` e ``->>`` funciona.
        """
        ordem_id = _os_com_orcamento(session)

        tipo = session.execute(
            text(
                "SELECT jsonb_typeof(orcamento_json) "
                "FROM ordens_de_servico WHERE id = :id"
            ),
            {"id": ordem_id},
        ).scalar_one()
        assert tipo == "object"

        # Operador jsonb ``->>`` so funciona sobre jsonb real (object); em
        # string duplamente codificada retornaria NULL.
        versao = session.execute(
            text(
                "SELECT orcamento_json->>'versao_schema' "
                "FROM ordens_de_servico WHERE id = :id"
            ),
            {"id": ordem_id},
        ).scalar_one()
        assert versao == "1"

        # E as linhas sao um array jsonb navegavel (prova adicional de que o
        # dict aninhado nao virou string).
        n_itens = session.execute(
            text(
                "SELECT jsonb_array_length(orcamento_json->'itens') "
                "FROM ordens_de_servico WHERE id = :id"
            ),
            {"id": ordem_id},
        ).scalar_one()
        assert n_itens == 2
