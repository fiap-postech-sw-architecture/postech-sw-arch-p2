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

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from src.cliente_veiculo.dominio.cliente import Cliente
from src.cliente_veiculo.dominio.contato import Contato
from src.cliente_veiculo.dominio.cpf import CPF
from src.cliente_veiculo.dominio.placa import Placa
from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import ordens_de_servico_table
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


def _criar_cliente_veiculo(
    session: Session, *, cpf: str, placa: str
) -> tuple[UUID, UUID]:
    """Persiste um cliente com um veiculo via repository real e devolve os ids.

    Existe para que insercoes cruas em ``ordens_de_servico`` (FKs NOT NULL
    para ``clientes``/``veiculos``) tenham linhas-pai validas.
    """
    cliente = Cliente(
        _nome="Cliente JSONB",
        _documento=CPF(numero=cpf),
        _contato=Contato(valor="11999990000"),
    )
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    ClienteSQLAlchemyRepository(session=session).salvar(cliente)
    cliente.adicionar_veiculo(
        placa=Placa(valor=placa), marca="Fiat", modelo="Uno", ano=2020
    )
    session.flush()
    return cliente.id, cliente.veiculos[0].id


def _os_com_orcamento(session: Session) -> UUID:
    """OS aprovada com orcamento de 2 linhas, persistida via repository real."""
    cliente_id, veiculo_id = _criar_cliente_veiculo(
        session, cpf="21249722519", placa="JSB1234"
    )

    ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
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
        # Snapshot novo: v2 (moeda por linha e no total persistidas).
        assert orcamento.versao_schema == 2

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
        assert versao == "2"

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

    def test_orcamento_none_round_trip_em_postgres(self, session: Session) -> None:
        """OS sem orcamento: ``orcamento is None`` reidrata pelo ramo NULL.

        Cobre o ramo de escrita ``else: target._orcamento_json = None``
        (``mapping.py`` ``_decompor_os``) e o ramo de leitura "vazio"
        (``if data:`` falso -> ``_orcamento = None`` em ``_reconstruir_os``)
        no backend real.

        Com ``none_as_null=True`` no tipo da coluna, atribuir ``None``
        (Python) grava SQL ``NULL`` (nao o token JSON ``'null'::jsonb``),
        igual ao comportamento da coluna ``Text`` anterior e consistente com
        linhas legadas. As duas pontas sao validadas: ``orcamento_json IS
        NULL`` (lado da escrita) e ``recarregada.orcamento is None`` (leitura).
        """
        cliente_id, veiculo_id = _criar_cliente_veiculo(
            session, cpf="52998224725", placa="NUL0000"
        )
        ordem = OrdemDeServico.criar(cliente_id=cliente_id, veiculo_id=veiculo_id)
        assert ordem.orcamento is None
        ordem.limpar_eventos()
        OrdemDeServicoSQLAlchemyRepository(session=session).salvar(ordem)
        ordem_id = ordem.id

        # Forca releitura do banco (e nao do identity map).
        session.expire_all()
        recarregada = OrdemDeServicoSQLAlchemyRepository(session=session).obter_por_id(
            ordem_id
        )
        assert recarregada is not None
        # Ramo de leitura NULL: o orcamento reidrata como None.
        assert recarregada.orcamento is None

        # Ramo de escrita ``else``: a coluna guarda SQL NULL (none_as_null),
        # que o psycopg2 traz de volta como None na leitura.
        col_is_null = session.execute(
            text("SELECT orcamento_json IS NULL FROM ordens_de_servico WHERE id = :id"),
            {"id": ordem_id},
        ).scalar_one()
        assert col_is_null is True

    def test_snapshot_legado_sem_moeda_usa_fallback_brl(self, session: Session) -> None:
        """Snapshot legado (``versao_schema`` 1, sem ``moeda``) reidrata como BRL.

        Linhas escritas antes do campo de moeda nao tem ``moeda`` por linha
        nem ``moeda_total``; o read listener (``_reconstruir_os``) cai para
        ``"BRL"`` via ``li.get("moeda", "BRL")`` e
        ``data.get("moeda_total", "BRL")``. Escritas novas sempre emitem
        ``moeda``, entao este ramo so e alcancavel por linhas pre-existentes
        — por isso inserimos a linha legada diretamente no jsonb e validamos
        a reidratacao via repository.
        """
        from uuid import uuid4

        cliente_id, veiculo_id = _criar_cliente_veiculo(
            session, cpf="11144477735", placa="LEG0001"
        )

        # Forma legada MINIMA que o read listener espera, MENOS as chaves de
        # moeda: itens[].{descricao, quantidade, preco_unitario_centavos,
        # subtotal_centavos}, total_centavos, gerado_em (ISO), versao_schema=1.
        # SEM "moeda" por linha e SEM "moeda_total" — exatamente o gatilho do
        # fallback. Centavos consistentes com as invariantes dos VOs
        # (subtotal == preco_unitario * quantidade; total == soma dos subtotais).
        orcamento_legado = {
            "total_centavos": 32050,
            "gerado_em": "2024-01-15T10:30:00+00:00",
            "versao_schema": 1,
            "itens": [
                {
                    "descricao": "Troca de oleo",
                    "quantidade": 2,
                    "preco_unitario_centavos": 12000,
                    "subtotal_centavos": 24000,
                },
                {
                    "descricao": "Alinhamento",
                    "quantidade": 1,
                    "preco_unitario_centavos": 8050,
                    "subtotal_centavos": 8050,
                },
            ],
        }

        ordem_id = uuid4()
        now = datetime.now(UTC)
        session.execute(
            ordens_de_servico_table.insert().values(
                id=ordem_id,
                cliente_id=cliente_id,
                veiculo_id=veiculo_id,
                status=StatusOrdem.AGUARDANDO_APROVACAO.value,
                orcamento_json=orcamento_legado,
                criado_em=now,
                atualizado_em=now,
            )
        )
        session.flush()

        session.expire_all()
        recarregada = OrdemDeServicoSQLAlchemyRepository(session=session).obter_por_id(
            ordem_id
        )
        assert recarregada is not None
        orcamento = recarregada.orcamento
        assert orcamento is not None
        assert orcamento.versao_schema == 1

        # Toda moeda cai para "BRL" (fallback), com os valores reconstruidos
        # corretamente a partir dos centavos.
        assert orcamento.total == Dinheiro(valor=Decimal("320.50"), moeda="BRL")
        assert orcamento.total.moeda == "BRL"
        assert len(orcamento.itens) == 2
        por_descricao = {linha.descricao: linha for linha in orcamento.itens}
        oleo = por_descricao["Troca de oleo"]
        assert oleo.preco_unitario == Dinheiro(valor=Decimal("120.00"), moeda="BRL")
        assert oleo.preco_unitario.moeda == "BRL"
        assert oleo.subtotal == Dinheiro(valor=Decimal("240.00"), moeda="BRL")
        assert oleo.subtotal.moeda == "BRL"
        alinhamento = por_descricao["Alinhamento"]
        assert alinhamento.preco_unitario == Dinheiro(
            valor=Decimal("80.50"), moeda="BRL"
        )
        assert alinhamento.preco_unitario.moeda == "BRL"
        assert alinhamento.subtotal == Dinheiro(valor=Decimal("80.50"), moeda="BRL")
        assert alinhamento.subtotal.moeda == "BRL"
