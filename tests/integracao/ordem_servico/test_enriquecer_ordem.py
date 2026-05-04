"""Integracao: ``EnriquecerOrdemDeServico`` contra Postgres real.

Exercita o caminho completo da query — ``select(...).where(id.in_(...))``
nos adapters SQLAlchemy + mapping imperativo dos contextos vizinhos —
que os unit tests nao alcancam (mocks de session nao registram tabelas).

Cobre os casos de leitura cross-context:
- linha de mao de obra (servico_nome resolvido, item_estoque_nome None)
- linha de peca consumida (ambos resolvidos via duas queries batch)
- catalogo limpo apos OS criada (servico_nome cai pra None, sem 500)
- cliente_nome / veiculo_placa resolvidos via ``ClientePort`` (single + lote)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.estoque.dominio.item_estoque import ItemEstoque
from src.ordem_servico.aplicacao.dtos import (
    ItemDaOrdemDTO,
    OrdemDeServicoDTO,
    OrdemResumoDTO,
)
from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico
from src.ordem_servico.infraestrutura.adapters import (
    CatalogoSQLAlchemyAdapter,
    ClienteSQLAlchemyAdapter,
    EstoqueSQLAlchemyAdapter,
)

if TYPE_CHECKING:
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


def _persistir_cliente_e_veiculo(
    session: Session,
    *,
    nome: str,
    cpf_numero: str,
    placa_valor: str,
) -> tuple[UUID, UUID]:
    """Cria cliente CPF + 1 veiculo e devolve ``(cliente_id, veiculo_id)``."""
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    cliente = Cliente(
        _nome=nome,
        _documento=CPF(numero=cpf_numero),
        _contato="11999990000",
    )
    cliente.adicionar_veiculo(
        placa=Placa(valor=placa_valor),
        marca="Marca",
        modelo="Modelo",
        ano=2020,
    )
    ClienteSQLAlchemyRepository(session=session).salvar(cliente)
    veiculo_id = next(iter(cliente.veiculos)).id
    return cliente.id, veiculo_id


def _ordem_dto_com_itens(
    *,
    itens: list[ItemDaOrdemDTO],
    instante: datetime,
    cliente_id: UUID | None = None,
    veiculo_id: UUID | None = None,
) -> OrdemDeServicoDTO:
    return OrdemDeServicoDTO(
        id=uuid4(),
        cliente_id=cliente_id or uuid4(),
        veiculo_id=veiculo_id or uuid4(),
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
    return ItemDaOrdemDTO(
        id=uuid4(),
        servico_catalogo_id=servico_id,
        item_estoque_id=item_estoque_id,
        descricao=descricao,
        quantidade=1,
        preco_unitario_centavos=15000,
        subtotal_centavos=15000,
    )


def _query(session: Session) -> EnriquecerOrdemDeServico:
    return EnriquecerOrdemDeServico(
        catalogo_port=CatalogoSQLAlchemyAdapter(session=session),
        estoque_port=EstoqueSQLAlchemyAdapter(session=session),
        cliente_port=ClienteSQLAlchemyAdapter(session=session),
    )


class TestEnriquecerOrdemDeServicoIntegracao:
    """Roda contra Postgres real (via testcontainers ou TEST_DATABASE_URL)."""

    def test_resolve_nomes_via_adapters_reais(self, session: Session) -> None:
        servico_id = _persistir_servico(
            session, nome="Troca de oleo", preco_centavos=15000
        )
        item_estoque_id = _persistir_item_estoque(
            session, nome="Filtro de oleo", preco_centavos=2500
        )
        cliente_id, veiculo_id = _persistir_cliente_e_veiculo(
            session,
            nome="Maria Silva",
            cpf_numero="21249722519",
            placa_valor="ABC1234",
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
            cliente_id=cliente_id,
            veiculo_id=veiculo_id,
        )

        enriquecida = _query(session).executar(ordem)

        assert [i.servico_nome for i in enriquecida.itens] == [
            "Troca de oleo",
            "Troca de oleo",
        ]
        assert enriquecida.itens[0].item_estoque_nome is None
        assert enriquecida.itens[1].item_estoque_nome == "Filtro de oleo"
        assert enriquecida.cliente_nome == "Maria Silva"
        assert enriquecida.veiculo_placa == "ABC1234"

    def test_servico_inexistente_nao_quebra_resposta(self, session: Session) -> None:
        """Servico apagado do catalogo apos OS criada — fallback graceful."""
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

        enriquecida = _query(session).executar(ordem)

        assert enriquecida.itens[0].servico_nome is None
        assert enriquecida.itens[0].item_estoque_nome is None
        # cliente/veiculo aleatorios tambem caem para None (fallback graceful).
        assert enriquecida.cliente_nome is None
        assert enriquecida.veiculo_placa is None

    def test_executar_lote_resolve_em_batch(self, session: Session) -> None:
        """Lista de OrdemResumoDTO recebe cliente_nome + veiculo_placa em batch."""
        # CPFs distintos por teste para resiliencia se o session fixture mudar
        # de escopo (rollback deixar de isolar) — UNIQUE em ``documento_hash``
        # do ClienteSQLAlchemyRepository nao re-falha entre testes.
        cliente_a, veiculo_a = _persistir_cliente_e_veiculo(
            session,
            nome="Ana",
            cpf_numero="57648016648",
            placa_valor="AAA0001",
        )
        cliente_b, veiculo_b = _persistir_cliente_e_veiculo(
            session,
            nome="Bruno",
            cpf_numero="11144477735",
            placa_valor="BBB0002",
        )
        session.flush()

        instante = datetime.now(tz=UTC)
        ordens = [
            OrdemResumoDTO(
                id=uuid4(),
                cliente_id=cliente_a,
                veiculo_id=veiculo_a,
                status="recebida",
                criado_em=instante,
            ),
            OrdemResumoDTO(
                id=uuid4(),
                cliente_id=cliente_b,
                veiculo_id=veiculo_b,
                status="recebida",
                criado_em=instante,
            ),
        ]

        enriquecidas = _query(session).executar_lote(ordens)

        assert [o.cliente_nome for o in enriquecidas] == ["Ana", "Bruno"]
        assert [o.veiculo_placa for o in enriquecidas] == ["AAA0001", "BBB0002"]
