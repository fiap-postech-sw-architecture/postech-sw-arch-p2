from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException
from src.ordem_servico.aplicacao.dtos import (
    AdicionarItemDTO,
    CancelarOrdemDTO,
    CriarOrdemDTO,
)
from src.ordem_servico.aplicacao.ports import ServicoOferecidoDTO
from src.ordem_servico.aplicacao.use_cases import (
    AdicionarItem,
    AprovarOrcamento,
    AprovarOrcamentoComplementar,
    CancelarOrdem,
    ConsultarAcompanhamento,
    CriarOrdem,
    FinalizarServico,
    GerarOrcamento,
    GerarOrcamentoComplementar,
    IniciarDiagnostico,
    ListarOrdens,
    ObterMetricas,
    ObterOrdem,
    RegistrarEntrega,
    RejeitarOrcamentoComplementar,
    RemoverItem,
)
from src.ordem_servico.dominio.exceptions import (
    ClienteNaoEncontradoException,
    ItemDaOrdemNaoEncontradoException,
    OrdemNaoEncontradaException,
    VeiculoNaoEncontradoException,
)
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeOrdemDeServicoRepository:
    def __init__(self) -> None:
        self._ordens: dict[UUID, OrdemDeServico] = {}
        self._placa_documento: dict[tuple[str, str], list[OrdemDeServico]] = {}

    def obter_por_id(self, ordem_id: UUID) -> OrdemDeServico | None:
        return self._ordens.get(ordem_id)

    def salvar(self, ordem: OrdemDeServico) -> None:
        self._ordens[ordem.id] = ordem

    def listar(self, offset: int = 0, limit: int = 20) -> list[OrdemDeServico]:
        return list(self._ordens.values())[offset : offset + limit]

    def contar(self) -> int:
        return len(self._ordens)

    def contar_por_status(self) -> dict[str, int]:
        resultado: dict[str, int] = {}
        for ordem in self._ordens.values():
            status_val = ordem.status.value
            resultado[status_val] = resultado.get(status_val, 0) + 1
        return resultado

    def existe_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        return False

    def existe_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        return False

    def existe_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        return False

    def obter_por_placa_e_documento(
        self, placa: str, documento: str
    ) -> list[OrdemDeServico]:
        return list(self._placa_documento.get((placa, documento), []))

    def adicionar_para_placa_documento(
        self, placa: str, documento: str, ordem: OrdemDeServico
    ) -> None:
        chave = (placa, documento)
        if chave not in self._placa_documento:
            self._placa_documento[chave] = []
        self._placa_documento[chave].append(ordem)
        self._ordens[ordem.id] = ordem

    def calcular_tempo_medio_execucao(self) -> float | None:
        from src.ordem_servico.dominio.status import StatusOrdem

        finalizados = [
            o
            for o in self._ordens.values()
            if o.status in {StatusOrdem.ENTREGUE, StatusOrdem.FINALIZADA}
        ]
        if not finalizados:
            return None
        total_minutos = sum(
            (o.atualizado_em - o.criado_em).total_seconds() / 60.0 for o in finalizados
        )
        return total_minutos / len(finalizados)


class StubClientePort:
    def __init__(
        self,
        cliente_ok: bool = True,
        veiculo_pertence: bool = True,
    ) -> None:
        self._cliente_ok = cliente_ok
        self._veiculo_pertence = veiculo_pertence

    def cliente_existe(self, cliente_id: UUID) -> bool:
        return self._cliente_ok

    def veiculo_pertence_ao_cliente(self, cliente_id: UUID, veiculo_id: UUID) -> bool:
        return self._veiculo_pertence


class StubCatalogoPort:
    def __init__(self, servico: ServicoOferecidoDTO | None = None) -> None:
        self._servico = servico

    def obter_servico(self, servico_id: UUID) -> ServicoOferecidoDTO | None:
        return self._servico


class StubEstoquePort:
    def __init__(self, item: object | None = None) -> None:
        self.reservas: list[tuple[UUID, int]] = []
        self.liberacoes: list[tuple[UUID, int]] = []
        # ItemEstoqueDTO opcional: usado por AdicionarItem.executar quando
        # a linha tem item_estoque_id (preco vem do estoque, nao do servico).
        self._item = item

    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        self.reservas.append((item_estoque_id, quantidade))

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        self.liberacoes.append((item_estoque_id, quantidade))

    def obter_item(self, item_estoque_id: UUID) -> object | None:
        return self._item


def _servico_dto() -> ServicoOferecidoDTO:
    return ServicoOferecidoDTO(
        id=uuid4(),
        nome="Troca de oleo",
        preco=Dinheiro(valor=Decimal("100.00")),
        ativo=True,
    )


def _criar_ordem_com_item(
    repo: FakeOrdemDeServicoRepository,
) -> OrdemDeServico:
    ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
    item = ItemDaOrdem(
        _servico_catalogo_id=uuid4(),
        _descricao="Troca de oleo",
        _quantidade=1,
        _preco_unitario=Dinheiro(valor=Decimal("100.00")),
    )
    ordem.adicionar_item(item)
    ordem.limpar_eventos()
    repo.salvar(ordem)
    return ordem


class TestCriarOrdem:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort()
        uc = CriarOrdem(repo=repo, uow=uow, cliente_port=cp)
        dto = CriarOrdemDTO(cliente_id=uuid4(), veiculo_id=uuid4())
        result = uc.executar(dto)
        assert result.status == "recebida"

    def test_cliente_nao_encontrado(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort(cliente_ok=False)
        uc = CriarOrdem(repo=repo, uow=uow, cliente_port=cp)
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(CriarOrdemDTO(uuid4(), uuid4()))

    def test_veiculo_nao_pertence_ao_cliente(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort(veiculo_pertence=False)
        uc = CriarOrdem(repo=repo, uow=uow, cliente_port=cp)
        with pytest.raises(VeiculoNaoEncontradoException):
            uc.executar(CriarOrdemDTO(uuid4(), uuid4()))


class TestAdicionarItem:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()
        cp = StubCatalogoPort(servico=servico)
        ep = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=None,
            descricao="Servico extra",
            quantidade=1,
        )
        result = uc.executar(ordem.id, dto)
        assert len(result.itens) == 2

    def test_servico_nao_encontrado(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubCatalogoPort(servico=None)
        ep = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=uuid4(),
            item_estoque_id=None,
            descricao="X",
            quantidade=1,
        )
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(ordem.id, dto)

    def test_servico_inativo(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = ServicoOferecidoDTO(
            id=uuid4(),
            nome="Inativo",
            preco=Dinheiro(valor=Decimal("10.00")),
            ativo=False,
        )
        cp = StubCatalogoPort(servico=servico)
        ep = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=None,
            descricao="X",
            quantidade=1,
        )
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(ordem.id, dto)

    def test_item_estoque_id_usa_preco_do_estoque(self) -> None:
        """Bug historico (corrigido): quando ``item_estoque_id`` era informado
        o ``preco_unitario`` ainda vinha do servico — o preco da peca era
        silenciosamente ignorado e o orcamento ficava subavaliado.

        Agora o preco vem do estoque (linha de peca consumida), enquanto
        servico.preco continua sendo usado pra linhas de mao de obra (sem
        item_estoque_id)."""
        from src.ordem_servico.aplicacao.ports import ItemEstoqueDTO

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()  # preco R$ 100.00 (mao de obra)
        cp = StubCatalogoPort(servico=servico)
        peca = ItemEstoqueDTO(
            id=uuid4(),
            nome="Filtro de oleo",
            preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        ep = StubEstoquePort(item=peca)
        ordem = _criar_ordem_com_item(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=peca.id,
            descricao="Filtro consumido",
            quantidade=2,
        )

        result = uc.executar(ordem.id, dto)

        # Linha nova: 2x R$ 35,00 = R$ 70,00 (NAO 2x R$ 100 = R$ 200)
        nova = next(i for i in result.itens if i.descricao == "Filtro consumido")
        assert nova.preco_unitario_centavos == 3500, (
            "Bug regressado: preco_unitario veio do servico em vez do estoque"
        )
        assert nova.subtotal_centavos == 7000

    def test_item_estoque_inexistente_levanta(self) -> None:
        """``EstoquePort.obter_item`` retornando None deve resultar em
        ViolacaoRegraDeNegocio (mapeada pra 409 no router) — alinhado com o
        comportamento de servico-not-found."""
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()
        cp = StubCatalogoPort(servico=servico)
        ep = StubEstoquePort(item=None)  # obter_item retorna None
        ordem = _criar_ordem_com_item(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=uuid4(),
            descricao="Peca fantasma",
            quantidade=1,
        )
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(ordem.id, dto)


class TestIniciarDiagnostico:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        uc = IniciarDiagnostico(repo=repo, uow=uow)
        result = uc.executar(ordem.id)
        assert result.status == "em_diagnostico"

    def test_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = IniciarDiagnostico(repo=repo, uow=uow)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4())


class TestGerarOrcamento:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.limpar_eventos()
        uc = GerarOrcamento(repo=repo, uow=uow)
        result = uc.executar(ordem.id)
        assert result.status == "aguardando_aprovacao"
        assert result.orcamento is not None

    def test_sem_itens(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = OrdemDeServico.criar(uuid4(), uuid4())
        ordem.iniciar_diagnostico()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = GerarOrcamento(repo=repo, uow=uow)
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(ordem.id)


class TestAprovarOrcamento:
    def test_sucesso_com_estoque(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        estoque_id = uuid4()
        ordem = OrdemDeServico.criar(uuid4(), uuid4())
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _item_estoque_id=estoque_id,
            _descricao="Filtro",
            _quantidade=2,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        ordem.adicionar_item(item)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = AprovarOrcamento(repo=repo, uow=uow, estoque_port=estoque)
        uc.executar(ordem.id)
        assert len(estoque.reservas) == 1
        assert estoque.reservas[0] == (estoque_id, 2)


class TestCancelarOrdem:
    def test_sucesso_recebida(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        uc = CancelarOrdem(repo=repo, uow=uow, estoque_port=estoque)
        uc.executar(ordem.id, CancelarOrdemDTO(motivo="Desistiu"))
        assert len(estoque.liberacoes) == 0

    def test_em_execucao_libera_estoque(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        estoque_id = uuid4()
        ordem = OrdemDeServico.criar(uuid4(), uuid4())
        item = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _item_estoque_id=estoque_id,
            _descricao="Filtro",
            _quantidade=2,
            _preco_unitario=Dinheiro(valor=Decimal("50.00")),
        )
        ordem.adicionar_item(item)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = CancelarOrdem(repo=repo, uow=uow, estoque_port=estoque)
        uc.executar(ordem.id, CancelarOrdemDTO(motivo="Erro"))
        assert len(estoque.liberacoes) == 1


class TestComplementar:
    def test_fluxo_completo(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.limpar_eventos()
        gerar = GerarOrcamentoComplementar(repo=repo, uow=uow)
        result = gerar.executar(ordem.id)
        assert result.status == "aguardando_aprovacao_complementar"
        aprovar = AprovarOrcamentoComplementar(repo=repo, uow=uow)
        result = aprovar.executar(ordem.id)
        assert result.status == "em_execucao"

    def test_rejeitar(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.gerar_orcamento_complementar()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        rejeitar = RejeitarOrcamentoComplementar(repo=repo, uow=uow)
        result = rejeitar.executar(ordem.id)
        assert result.status == "em_execucao"


class TestListarOrdens:
    def test_vazio(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uc = ListarOrdens(repo=repo)
        assert uc.executar() == []

    def test_com_dados(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        uc = ListarOrdens(repo=repo)
        assert len(uc.executar()) == 1


class TestObterOrdem:
    def test_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        ordem = _criar_ordem_com_item(repo)
        uc = ObterOrdem(repo=repo)
        result = uc.executar(ordem.id)
        assert result.id == ordem.id

    def test_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uc = ObterOrdem(repo=repo)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4())


class TestObterMetricas:
    def test_metricas(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        uc = ObterMetricas(repo=repo)
        result = uc.executar()
        assert result.total == 1
        assert result.por_status["recebida"] == 1


class TestRemoverItem:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        item_id = ordem.itens[0].id
        uc = RemoverItem(repo=repo, uow=uow)
        result = uc.executar(ordem.id, item_id)
        assert len(result.itens) == 0

    def test_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = RemoverItem(repo=repo, uow=uow)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4(), uuid4())

    def test_item_nao_encontrado(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        uc = RemoverItem(repo=repo, uow=uow)
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(ordem.id, uuid4())


class TestFinalizarServico:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = FinalizarServico(repo=repo, uow=uow)
        result = uc.executar(ordem.id)
        assert result.status == "finalizada"

    def test_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = FinalizarServico(repo=repo, uow=uow)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4())


class TestRegistrarEntrega:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.finalizar_servico()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = RegistrarEntrega(repo=repo, uow=uow)
        result = uc.executar(ordem.id)
        assert result.status == "entregue"

    def test_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = RegistrarEntrega(repo=repo, uow=uow)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4())


class TestConsultarAcompanhamento:
    def test_os_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        ordem = _criar_ordem_com_item(repo)
        repo.adicionar_para_placa_documento("ABC1234", "12345678901", ordem)
        uc = ConsultarAcompanhamento(repo=repo)
        result = uc.executar(placa="ABC1234", documento="12345678901")
        assert result is not None
        assert result.status == "recebida"

    def test_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uc = ConsultarAcompanhamento(repo=repo)
        result = uc.executar(placa="ZZZ9999", documento="00000000000")
        assert result is None

    def test_retorna_mais_recente(self) -> None:
        from datetime import UTC, datetime

        repo = FakeOrdemDeServicoRepository()
        ordem_antiga = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem_antiga._criado_em = datetime(2024, 1, 1, tzinfo=UTC)
        ordem_antiga.limpar_eventos()

        ordem_recente = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem_recente._criado_em = datetime(2024, 6, 1, tzinfo=UTC)
        ordem_recente.limpar_eventos()

        repo.adicionar_para_placa_documento("ABC1234", "12345678901", ordem_antiga)
        repo.adicionar_para_placa_documento("ABC1234", "12345678901", ordem_recente)
        uc = ConsultarAcompanhamento(repo=repo)
        result = uc.executar(placa="ABC1234", documento="12345678901")
        assert result is not None
        assert result.criado_em == datetime(2024, 6, 1, tzinfo=UTC)


class TestObterMetricasComTempo:
    def test_metricas_com_tempo_medio(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.finalizar_servico()
        ordem.registrar_entrega()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = ObterMetricas(repo=repo)
        result = uc.executar()
        assert result.tempo_medio_execucao_minutos is not None
        assert isinstance(result.tempo_medio_execucao_minutos, float)

    def test_metricas_sem_os_finalizadas(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        uc = ObterMetricas(repo=repo)
        result = uc.executar()
        assert result.tempo_medio_execucao_minutos is None


class TestItemDaOrdemNaoEncontradoException:
    def test_mensagem_padrao(self) -> None:
        exc = ItemDaOrdemNaoEncontradoException()
        assert exc.mensagem == "Item da ordem nao encontrado"
        assert exc.codigo == "ENTIDADE_NAO_ENCONTRADA"

    def test_mensagem_customizada(self) -> None:
        exc = ItemDaOrdemNaoEncontradoException(mensagem="Item especifico")
        assert exc.mensagem == "Item especifico"


class TestListarOrdensContar:
    def test_contar_vazio(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uc = ListarOrdens(repo=repo)
        assert uc.contar() == 0

    def test_contar_com_dados(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        _criar_ordem_com_item(repo)
        uc = ListarOrdens(repo=repo)
        assert uc.contar() == 2


class _RaisingEstoquePort:
    """Stub de EstoquePort que levanta excecao em reservar/liberar."""

    def __init__(self) -> None:
        from src.compartilhado.dominio.exceptions import (
            EntidadeNaoEncontradaException,
        )

        self._exc_cls = EntidadeNaoEncontradaException

    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        raise self._exc_cls(mensagem="Item de estoque nao encontrado")

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        raise self._exc_cls(mensagem="Item de estoque nao encontrado")


class TestUoWBoundaryAndMissingNegatives:
    """Regressao para gaps do review step 10 (P4 F1 + F2).

    - Toda use case mutadora deve marcar `uow.committed = True` no
      happy path (caso contrario uma regressao que remove o
      `with self._uow:` nao seria detectada).
    - `GerarOrcamentoComplementar` precisa cobrir empty items
      (PR #61 lesson) e invalid state.
    - `AprovarOrcamento` precisa cobrir o caso em que
      `EstoquePort.reservar` levanta.
    - `CancelarOrdem` precisa cobrir not-found e o caso em que
      `EstoquePort.liberar` levanta (dentro da UoW).
    """

    def _setup_em_execucao(self, repo: FakeOrdemDeServicoRepository) -> OrdemDeServico:
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.limpar_eventos()
        return ordem

    def test_criar_ordem_commit_da_uow(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = CriarOrdem(repo=repo, uow=uow, cliente_port=StubClientePort())
        uc.executar(CriarOrdemDTO(cliente_id=uuid4(), veiculo_id=uuid4()))
        assert uow.committed is True

    def test_iniciar_diagnostico_commit_da_uow(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        uc = IniciarDiagnostico(repo=repo, uow=uow)
        uc.executar(ordem.id)
        assert uow.committed is True

    def test_aprovar_orcamento_commit_da_uow(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.limpar_eventos()
        uc = AprovarOrcamento(repo=repo, uow=uow, estoque_port=StubEstoquePort())
        uc.executar(ordem.id)
        assert uow.committed is True

    def test_cancelar_ordem_commit_da_uow(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        uc = CancelarOrdem(repo=repo, uow=uow, estoque_port=StubEstoquePort())
        uc.executar(ordem.id, CancelarOrdemDTO(motivo="Teste"))
        assert uow.committed is True

    def test_gerar_orcamento_complementar_commit_da_uow(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = self._setup_em_execucao(repo)
        uc = GerarOrcamentoComplementar(repo=repo, uow=uow)
        uc.executar(ordem.id)
        assert uow.committed is True

    def test_gerar_orcamento_complementar_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = GerarOrcamentoComplementar(repo=repo, uow=uow)
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4())

    def test_gerar_orcamento_complementar_em_estado_invalido(self) -> None:
        """PR #61 lesson: transicao invalida deve ser primary error."""
        from src.compartilhado.dominio.exceptions import (
            TransicaoStatusInvalidaException,
        )

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        # Ordem ainda em RECEBIDA — gerar_orcamento_complementar so e
        # valido a partir de EM_EXECUCAO
        uc = GerarOrcamentoComplementar(repo=repo, uow=uow)
        with pytest.raises(TransicaoStatusInvalidaException):
            uc.executar(ordem.id)

    def test_aprovar_orcamento_port_levanta(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        from src.compartilhado.dominio.exceptions import (
            EntidadeNaoEncontradaException,
        )

        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        item_com_estoque = ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _item_estoque_id=uuid4(),
            _descricao="Peca",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
        # Nova ordem do zero com item_estoque_id para exercitar EstoquePort.reservar.
        ordem2 = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem2.adicionar_item(item_com_estoque)
        ordem2.iniciar_diagnostico()
        ordem2.gerar_orcamento()
        ordem2.limpar_eventos()
        repo.salvar(ordem2)
        uc = AprovarOrcamento(repo=repo, uow=uow, estoque_port=_RaisingEstoquePort())
        with pytest.raises(EntidadeNaoEncontradaException):
            uc.executar(ordem2.id)
        # UoW nao deve ter comitado (rollback path)
        assert uow.committed is False

    def test_cancelar_ordem_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = CancelarOrdem(repo=repo, uow=uow, estoque_port=StubEstoquePort())
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4(), CancelarOrdemDTO(motivo="qualquer"))

    def test_cancelar_ordem_port_liberar_levanta(self) -> None:
        from src.compartilhado.dominio.exceptions import (
            EntidadeNaoEncontradaException,
        )

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        # Ordem em EM_EXECUCAO com item_estoque_id — liberar sera chamado
        ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem.adicionar_item(
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _item_estoque_id=uuid4(),
                _descricao="Peca",
                _quantidade=1,
                _preco_unitario=Dinheiro(valor=Decimal("100.00")),
            )
        )
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = CancelarOrdem(repo=repo, uow=uow, estoque_port=_RaisingEstoquePort())
        with pytest.raises(EntidadeNaoEncontradaException):
            uc.executar(ordem.id, CancelarOrdemDTO(motivo="qualquer"))
        # UoW nao deve ter comitado
        assert uow.committed is False
