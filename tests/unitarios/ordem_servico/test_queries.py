"""Unit tests para queries da aplicacao OrdemDeServico.

Cobrem ``EnriquecerOrdemDeServico``, query que resolve ``servico_nome``
e ``item_estoque_nome`` via ``CatalogoPort`` / ``EstoquePort`` em
batch. Os testes simulam as portas com stubs, mantendo a query
isolada de SQLAlchemy: a propria query nunca toca a session, so os
adapters concretos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.aplicacao.dtos import (
    ItemDaOrdemDTO,
    OrdemDeServicoDTO,
)
from src.ordem_servico.aplicacao.ports import (
    ItemEstoqueDTO,
    ServicoOferecidoDTO,
)
from src.ordem_servico.aplicacao.queries import EnriquecerOrdemDeServico


class _CatalogoStub:
    """Stub de CatalogoPort que devolve um dict pre-configurado.

    Conta chamadas para que os testes possam afirmar que a query roda
    em batch (1 chamada por OS independente do n de itens).
    """

    def __init__(self, servicos: dict[UUID, ServicoOferecidoDTO]) -> None:
        self._servicos = servicos
        self.chamadas_em_lote: list[set[UUID]] = []

    def obter_servico(
        self, servico_id: UUID
    ) -> ServicoOferecidoDTO | None:  # pragma: no cover - usada por outros casos
        return self._servicos.get(servico_id)

    def obter_servicos_em_lote(
        self, servico_ids: set[UUID]
    ) -> dict[UUID, ServicoOferecidoDTO]:
        self.chamadas_em_lote.append(set(servico_ids))
        return {
            sid: self._servicos[sid] for sid in servico_ids if sid in self._servicos
        }


class _EstoqueStub:
    """Stub de EstoquePort foco em ``obter_itens_em_lote``.

    Os outros metodos (reservar/liberar/obter_item) nao sao exercitados
    pela query — ficam como ``pragma: no cover`` para nao distorcer o
    coverage do modulo.
    """

    def __init__(self, itens: dict[UUID, ItemEstoqueDTO]) -> None:
        self._itens = itens
        self.chamadas_em_lote: list[set[UUID]] = []

    def reservar(  # pragma: no cover - nao exercitado pela query
        self, item_estoque_id: UUID, quantidade: int
    ) -> None:
        raise NotImplementedError

    def liberar(  # pragma: no cover - nao exercitado pela query
        self, item_estoque_id: UUID, quantidade: int
    ) -> None:
        raise NotImplementedError

    def obter_item(  # pragma: no cover - nao exercitado pela query
        self, item_estoque_id: UUID
    ) -> ItemEstoqueDTO | None:
        return self._itens.get(item_estoque_id)

    def obter_itens_em_lote(
        self, item_estoque_ids: set[UUID]
    ) -> dict[UUID, ItemEstoqueDTO]:
        self.chamadas_em_lote.append(set(item_estoque_ids))
        return {iid: self._itens[iid] for iid in item_estoque_ids if iid in self._itens}


def _item_dto(
    *,
    servico_id: UUID,
    item_estoque_id: UUID | None = None,
) -> ItemDaOrdemDTO:
    """Cria um ItemDaOrdemDTO minimo (preco/qtd irrelevantes para a query)."""
    return ItemDaOrdemDTO(
        id=uuid4(),
        servico_catalogo_id=servico_id,
        item_estoque_id=item_estoque_id,
        descricao="qualquer",
        quantidade=1,
        preco_unitario_centavos=10000,
        subtotal_centavos=10000,
    )


def _ordem_dto(itens: list[ItemDaOrdemDTO]) -> OrdemDeServicoDTO:
    """Cria uma OrdemDeServicoDTO contendo os itens informados."""
    agora = datetime.now(tz=UTC)
    return OrdemDeServicoDTO(
        id=uuid4(),
        cliente_id=uuid4(),
        veiculo_id=uuid4(),
        status="recebida",
        itens=itens,
        orcamento=None,
        criado_em=agora,
        atualizado_em=agora,
    )


def _servico_dto(*, sid: UUID, nome: str) -> ServicoOferecidoDTO:
    return ServicoOferecidoDTO(id=sid, nome=nome, preco=Dinheiro(valor=100), ativo=True)


def _item_estoque_dto(*, iid: UUID, nome: str) -> ItemEstoqueDTO:
    return ItemEstoqueDTO(id=iid, nome=nome, preco_unitario=Dinheiro(valor=50))


class TestEnriquecerOrdemDeServico:
    def test_resolve_servico_nome_para_linha_de_mao_de_obra(self) -> None:
        sid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
        assert enriquecida.itens[0].item_estoque_nome is None
        # Sem item_estoque_id, a query repassa set vazio para a porta de
        # estoque; o adapter real trata como no-op (nao toca o DB).
        assert estoque.chamadas_em_lote == [set()]

    def test_resolve_servico_e_item_estoque_para_peca_consumida(self) -> None:
        sid = uuid4()
        eid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({eid: _item_estoque_dto(iid=eid, nome="Filtro de oleo")})
        ordem = _ordem_dto([_item_dto(servico_id=sid, item_estoque_id=eid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
        assert enriquecida.itens[0].item_estoque_nome == "Filtro de oleo"
        assert catalogo.chamadas_em_lote == [{sid}]
        assert estoque.chamadas_em_lote == [{eid}]

    def test_servico_inexistente_deixa_nome_none(self) -> None:
        """Catalogo limpo apos OS criada — UI cai pro placeholder."""
        sid = uuid4()
        catalogo = _CatalogoStub({})  # nada no catalogo
        estoque = _EstoqueStub({})
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida.itens[0].servico_nome is None
        assert enriquecida.itens[0].item_estoque_nome is None

    def test_item_estoque_inexistente_deixa_nome_none(self) -> None:
        """Servico encontrado mas peca nao — caso edge de cleanup parcial."""
        sid = uuid4()
        eid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})  # peca foi removida do estoque
        ordem = _ordem_dto([_item_dto(servico_id=sid, item_estoque_id=eid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
        assert enriquecida.itens[0].item_estoque_nome is None

    def test_lista_vazia_devolve_dto_sem_consultar_portas(self) -> None:
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        ordem = _ordem_dto([])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida is ordem
        assert catalogo.chamadas_em_lote == []
        assert estoque.chamadas_em_lote == []

    def test_batch_dedupe_servicos_iguais(self) -> None:
        """N itens com mesmo servico_catalogo_id => 1 chamada batch resolvida."""
        sid = uuid4()
        eid_b = uuid4()
        eid_c = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub(
            {
                eid_b: _item_estoque_dto(iid=eid_b, nome="Filtro"),
                eid_c: _item_estoque_dto(iid=eid_c, nome="Oleo"),
            }
        )
        ordem = _ordem_dto(
            [
                _item_dto(servico_id=sid),
                _item_dto(servico_id=sid, item_estoque_id=eid_b),
                _item_dto(servico_id=sid, item_estoque_id=eid_c),
            ]
        )

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        nomes_servico = [i.servico_nome for i in enriquecida.itens]
        assert nomes_servico == ["Troca de oleo", "Troca de oleo", "Troca de oleo"]
        assert enriquecida.itens[1].item_estoque_nome == "Filtro"
        assert enriquecida.itens[2].item_estoque_nome == "Oleo"
        # Set deduplica os tres servico_ids iguais em UM lookup batch.
        assert catalogo.chamadas_em_lote == [{sid}]
        assert estoque.chamadas_em_lote == [{eid_b, eid_c}]

    def test_dto_original_nao_e_mutado(self) -> None:
        """A query devolve um novo DTO; o original mantem ``servico_nome=None``."""
        sid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque).executar(ordem)

        assert enriquecida is not ordem
        assert ordem.itens[0].servico_nome is None
        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
