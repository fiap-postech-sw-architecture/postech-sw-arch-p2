"""Unit tests para queries da aplicacao OrdemDeServico.

Cobrem ``EnriquecerOrdemDeServico``, query que resolve ``servico_nome``,
``item_estoque_nome``, ``cliente_nome`` e ``veiculo_placa`` via
``CatalogoPort`` / ``EstoquePort`` / ``ClientePort`` em batch. Os
testes simulam as portas com stubs, mantendo a query isolada de
SQLAlchemy: a propria query nunca toca a session, so os adapters
concretos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.ordem_servico.aplicacao.dtos import (
    ItemDaOrdemDTO,
    OrdemDeServicoDTO,
    OrdemResumoDTO,
)
from src.ordem_servico.aplicacao.ports import (
    ClienteResumoDTO,
    ItemEstoqueDTO,
    ServicoOferecidoDTO,
    VeiculoResumoDTO,
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


class _ClienteStub:
    """Stub de ClientePort foco nos metodos batch.

    ``cliente_existe`` / ``veiculo_pertence_ao_cliente`` nao sao
    exercitados pela query (sao usados pelos use cases de mutacao),
    entao ficam como ``pragma: no cover`` aqui.
    """

    def __init__(
        self,
        clientes: dict[UUID, ClienteResumoDTO] | None = None,
        veiculos: dict[UUID, VeiculoResumoDTO] | None = None,
    ) -> None:
        self._clientes = clientes or {}
        self._veiculos = veiculos or {}
        self.chamadas_clientes: list[set[UUID]] = []
        self.chamadas_veiculos: list[set[UUID]] = []

    def cliente_existe(  # pragma: no cover - nao exercitado pela query
        self, cliente_id: UUID
    ) -> bool:
        return cliente_id in self._clientes

    def veiculo_pertence_ao_cliente(  # pragma: no cover - nao exercitado pela query
        self, cliente_id: UUID, veiculo_id: UUID
    ) -> bool:
        return veiculo_id in self._veiculos

    def obter_clientes_em_lote(
        self, cliente_ids: set[UUID]
    ) -> dict[UUID, ClienteResumoDTO]:
        self.chamadas_clientes.append(set(cliente_ids))
        return {
            cid: self._clientes[cid] for cid in cliente_ids if cid in self._clientes
        }

    def obter_veiculos_em_lote(
        self, veiculo_ids: set[UUID]
    ) -> dict[UUID, VeiculoResumoDTO]:
        self.chamadas_veiculos.append(set(veiculo_ids))
        return {
            vid: self._veiculos[vid] for vid in veiculo_ids if vid in self._veiculos
        }


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


def _ordem_dto(
    itens: list[ItemDaOrdemDTO],
    *,
    cliente_id: UUID | None = None,
    veiculo_id: UUID | None = None,
) -> OrdemDeServicoDTO:
    """Cria uma OrdemDeServicoDTO contendo os itens informados."""
    agora = datetime.now(tz=UTC)
    return OrdemDeServicoDTO(
        id=uuid4(),
        cliente_id=cliente_id or uuid4(),
        veiculo_id=veiculo_id or uuid4(),
        status="recebida",
        itens=itens,
        orcamento=None,
        criado_em=agora,
        atualizado_em=agora,
    )


def _resumo_dto(
    *, cliente_id: UUID | None = None, veiculo_id: UUID | None = None
) -> OrdemResumoDTO:
    return OrdemResumoDTO(
        id=uuid4(),
        cliente_id=cliente_id or uuid4(),
        veiculo_id=veiculo_id or uuid4(),
        status="recebida",
        criado_em=datetime.now(tz=UTC),
    )


def _servico_dto(*, sid: UUID, nome: str) -> ServicoOferecidoDTO:
    return ServicoOferecidoDTO(id=sid, nome=nome, preco=Dinheiro(valor=100), ativo=True)


def _item_estoque_dto(*, iid: UUID, nome: str) -> ItemEstoqueDTO:
    return ItemEstoqueDTO(id=iid, nome=nome, preco_unitario=Dinheiro(valor=50))


def _cliente_dto(*, cid: UUID, nome: str) -> ClienteResumoDTO:
    return ClienteResumoDTO(id=cid, nome=nome)


def _veiculo_dto(*, vid: UUID, placa: str) -> VeiculoResumoDTO:
    return VeiculoResumoDTO(id=vid, placa=placa)


class TestEnriquecerOrdemDeServico:
    def test_resolve_servico_nome_para_linha_de_mao_de_obra(self) -> None:
        sid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub()
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

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
        cliente = _ClienteStub()
        ordem = _ordem_dto([_item_dto(servico_id=sid, item_estoque_id=eid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
        assert enriquecida.itens[0].item_estoque_nome == "Filtro de oleo"
        assert catalogo.chamadas_em_lote == [{sid}]
        assert estoque.chamadas_em_lote == [{eid}]

    def test_servico_inexistente_deixa_nome_none(self) -> None:
        """Catalogo limpo apos OS criada — UI cai pro placeholder."""
        sid = uuid4()
        catalogo = _CatalogoStub({})  # nada no catalogo
        estoque = _EstoqueStub({})
        cliente = _ClienteStub()
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.itens[0].servico_nome is None
        assert enriquecida.itens[0].item_estoque_nome is None

    def test_item_estoque_inexistente_deixa_nome_none(self) -> None:
        """Servico encontrado mas peca nao — caso edge de cleanup parcial."""
        sid = uuid4()
        eid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})  # peca foi removida do estoque
        cliente = _ClienteStub()
        ordem = _ordem_dto([_item_dto(servico_id=sid, item_estoque_id=eid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.itens[0].servico_nome == "Troca de oleo"
        assert enriquecida.itens[0].item_estoque_nome is None

    def test_lista_vazia_consulta_apenas_cliente_e_veiculo(self) -> None:
        """OS sem itens ainda enriquece header (cliente_nome, veiculo_placa)."""
        cid = uuid4()
        vid = uuid4()
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub(
            clientes={cid: _cliente_dto(cid=cid, nome="Maria")},
            veiculos={vid: _veiculo_dto(vid=vid, placa="ABC1234")},
        )
        ordem = _ordem_dto([], cliente_id=cid, veiculo_id=vid)

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.cliente_nome == "Maria"
        assert enriquecida.veiculo_placa == "ABC1234"
        # Sem itens, pula catalogo + estoque (otimizacao).
        assert catalogo.chamadas_em_lote == []
        assert estoque.chamadas_em_lote == []
        # Mas cliente/veiculo sao sempre consultados (1 batch cada).
        assert cliente.chamadas_clientes == [{cid}]
        assert cliente.chamadas_veiculos == [{vid}]

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
        cliente = _ClienteStub()
        ordem = _ordem_dto(
            [
                _item_dto(servico_id=sid),
                _item_dto(servico_id=sid, item_estoque_id=eid_b),
                _item_dto(servico_id=sid, item_estoque_id=eid_c),
            ]
        )

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

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
        cliente = _ClienteStub()
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida is not ordem
        assert ordem.itens[0].servico_nome is None
        assert enriquecida.itens[0].servico_nome == "Troca de oleo"

    def test_resolve_cliente_nome_e_veiculo_placa(self) -> None:
        """Header da OS e enriquecido com cliente_nome e veiculo_placa."""
        cid = uuid4()
        vid = uuid4()
        sid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub(
            clientes={cid: _cliente_dto(cid=cid, nome="Joao")},
            veiculos={vid: _veiculo_dto(vid=vid, placa="XYZ9876")},
        )
        ordem = _ordem_dto([_item_dto(servico_id=sid)], cliente_id=cid, veiculo_id=vid)

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.cliente_nome == "Joao"
        assert enriquecida.veiculo_placa == "XYZ9876"

    def test_cliente_inexistente_deixa_nome_none(self) -> None:
        """Cliente removido apos OS criada — UI cai pro placeholder."""
        sid = uuid4()
        catalogo = _CatalogoStub({sid: _servico_dto(sid=sid, nome="Troca de oleo")})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub()  # vazio
        ordem = _ordem_dto([_item_dto(servico_id=sid)])

        enriquecida = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar(
            ordem
        )

        assert enriquecida.cliente_nome is None
        assert enriquecida.veiculo_placa is None


class TestEnriquecerOrdensEmLote:
    def test_lote_vazio_pula_consulta(self) -> None:
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub()

        resultado = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar_lote(
            []
        )

        assert resultado == []
        assert cliente.chamadas_clientes == []
        assert cliente.chamadas_veiculos == []

    def test_resolve_nomes_em_uma_chamada_batch_por_porta(self) -> None:
        """N ordens => 1 chamada batch para clientes + 1 para veiculos."""
        cid_a, cid_b = uuid4(), uuid4()
        vid_a, vid_b = uuid4(), uuid4()
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub(
            clientes={
                cid_a: _cliente_dto(cid=cid_a, nome="Ana"),
                cid_b: _cliente_dto(cid=cid_b, nome="Bruno"),
            },
            veiculos={
                vid_a: _veiculo_dto(vid=vid_a, placa="AAA0001"),
                vid_b: _veiculo_dto(vid=vid_b, placa="BBB0002"),
            },
        )
        ordens = [
            _resumo_dto(cliente_id=cid_a, veiculo_id=vid_a),
            _resumo_dto(cliente_id=cid_b, veiculo_id=vid_b),
        ]

        resultado = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar_lote(
            ordens
        )

        assert [r.cliente_nome for r in resultado] == ["Ana", "Bruno"]
        assert [r.veiculo_placa for r in resultado] == ["AAA0001", "BBB0002"]
        assert cliente.chamadas_clientes == [{cid_a, cid_b}]
        assert cliente.chamadas_veiculos == [{vid_a, vid_b}]

    def test_lote_dedupe_cliente_repetido(self) -> None:
        """Cliente que aparece em varias OS vira um unico id no batch."""
        cid = uuid4()
        vid_a, vid_b = uuid4(), uuid4()
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub(
            clientes={cid: _cliente_dto(cid=cid, nome="Carlos")},
            veiculos={
                vid_a: _veiculo_dto(vid=vid_a, placa="AAA0001"),
                vid_b: _veiculo_dto(vid=vid_b, placa="BBB0002"),
            },
        )
        ordens = [
            _resumo_dto(cliente_id=cid, veiculo_id=vid_a),
            _resumo_dto(cliente_id=cid, veiculo_id=vid_b),
        ]

        resultado = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar_lote(
            ordens
        )

        assert all(r.cliente_nome == "Carlos" for r in resultado)
        assert cliente.chamadas_clientes == [{cid}]

    def test_lote_cliente_inexistente_deixa_nome_none(self) -> None:
        cid_existente = uuid4()
        cid_removido = uuid4()
        vid = uuid4()
        catalogo = _CatalogoStub({})
        estoque = _EstoqueStub({})
        cliente = _ClienteStub(
            clientes={cid_existente: _cliente_dto(cid=cid_existente, nome="Ok")},
            veiculos={vid: _veiculo_dto(vid=vid, placa="OK01234")},
        )
        ordens = [
            _resumo_dto(cliente_id=cid_existente, veiculo_id=vid),
            _resumo_dto(cliente_id=cid_removido, veiculo_id=vid),
        ]

        resultado = EnriquecerOrdemDeServico(catalogo, estoque, cliente).executar_lote(
            ordens
        )

        assert resultado[0].cliente_nome == "Ok"
        assert resultado[1].cliente_nome is None
