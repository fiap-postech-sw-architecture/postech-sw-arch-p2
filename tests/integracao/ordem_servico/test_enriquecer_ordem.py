"""Integracao: ``EnriquecerOrdemDeServico`` contra Postgres real.

Exercita o caminho completo da query — ``select(...).where(id.in_(...))``
nos adapters SQLAlchemy + mapping imperativo dos contextos vizinhos —
que os unit tests nao alcancam (mocks de session nao registram tabelas).

Cobre os tres casos de leitura cross-context:
- linha de mao de obra (servico_nome resolvido, item_estoque_nome None)
- linha de peca consumida (ambos resolvidos via duas queries batch)
- catalogo limpo apos OS criada (servico_nome cai pra None, sem 500)
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.estoque.dominio.item_estoque import ItemEstoque
from src.ordem_servico.aplicacao.dtos import (
    ItemDaOrdemDTO,
    OrdemDeServicoDTO,
)
from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico
from src.ordem_servico.infraestrutura.adapters import (
    CatalogoSQLAlchemyAdapter,
    EstoqueSQLAlchemyAdapter,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integracao


def _persistir_servico(session: Session, *, nome: str, preco_centavos: int) -> UUID:
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )

    servico = ServicoOferecido(
        _nome=nome,
        _descricao=f"{nome} (descricao)",
        _preco=Dinheiro(valor=Decimal(preco_centavos) / Decimal(100)),
    )
    ServicoOferecidoSQLAlchemyRepository(session=session).salvar(servico)
    return servico.id


def _persistir_item_estoque(
    session: Session, *, nome: str, preco_centavos: int
) -> UUID:
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    item = ItemEstoque(
        _nome=nome,
        _descricao=f"{nome} (descricao)",
        _quantidade=10,
        _preco_unitario=Dinheiro(valor=Decimal(preco_centavos) / Decimal(100)),
    )
    ItemEstoqueSQLAlchemyRepository(session=session).salvar(item)
    return item.id


def _ordem_dto_com_itens(
    *,
    itens: list[ItemDaOrdemDTO],
    instante: datetime,
) -> OrdemDeServicoDTO:
    from uuid import uuid4

    return OrdemDeServicoDTO(
        id=uuid4(),
        cliente_id=uuid4(),
        veiculo_id=uuid4(),
        status="recebida",
        itens=itens,
        orcamento=None,
        criado_em=instante,
        atualizado_em=instante,
    )


def _item_dto(
    *,
    servico_id: UUID,
    item_estoque_id: UUID | None,
    descricao: str,
) -> ItemDaOrdemDTO:
    from uuid import uuid4

    return ItemDaOrdemDTO(
        id=uuid4(),
        servico_catalogo_id=servico_id,
        item_estoque_id=item_estoque_id,
        descricao=descricao,
        quantidade=1,
        preco_unitario_centavos=15000,
        subtotal_centavos=15000,
    )


class TestEnriquecerOrdemDeServicoIntegracao:
    """Roda contra Postgres real (via testcontainers ou TEST_DATABASE_URL)."""

    def test_resolve_nomes_via_adapters_reais(self, session: Session) -> None:
        from datetime import UTC, datetime

        servico_id = _persistir_servico(
            session, nome="Troca de oleo", preco_centavos=15000
        )
        item_estoque_id = _persistir_item_estoque(
            session, nome="Filtro de oleo", preco_centavos=2500
        )
        session.flush()

        ordem = _ordem_dto_com_itens(
            itens=[
                _item_dto(
                    servico_id=servico_id,
                    item_estoque_id=None,
                    descricao="Mao de obra",
                ),
                _item_dto(
                    servico_id=servico_id,
                    item_estoque_id=item_estoque_id,
                    descricao="Peca consumida",
                ),
            ],
            instante=datetime.now(tz=UTC),
        )

        query = EnriquecerOrdemDeServico(
            catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
            estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        )
        enriquecida = query.executar(ordem)

        assert [i.servico_nome for i in enriquecida.itens] == [
            "Troca de oleo",
            "Troca de oleo",
        ]
        assert enriquecida.itens[0].item_estoque_nome is None
        assert enriquecida.itens[1].item_estoque_nome == "Filtro de oleo"

    def test_servico_inexistente_nao_quebra_resposta(self, session: Session) -> None:
        """Servico apagado do catalogo apos OS criada — fallback graceful."""
        from datetime import UTC, datetime
        from uuid import uuid4

        ordem = _ordem_dto_com_itens(
            itens=[
                _item_dto(
                    servico_id=uuid4(),  # nao existe na base
                    item_estoque_id=None,
                    descricao="Servico orfao",
                ),
            ],
            instante=datetime.now(tz=UTC),
        )

        query = EnriquecerOrdemDeServico(
            catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
            estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        )
        enriquecida = query.executar(ordem)

        assert enriquecida.itens[0].servico_nome is None
        assert enriquecida.itens[0].item_estoque_nome is None
