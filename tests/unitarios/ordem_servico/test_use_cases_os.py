from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import (
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)
from src.ordem_servico.aplicacao.dtos import (
    AdicionarItemDTO,
    CancelarOrdemDTO,
    CriarOrdemDTO,
    PecaDaOrdemDTO,
    ServicoDaOrdemDTO,
)
from src.ordem_servico.aplicacao.ports import ItemEstoqueDTO, ServicoOferecidoDTO
from src.ordem_servico.aplicacao.use_cases import (
    MOTIVO_RECUSA_EXTERNA,
    AdicionarItem,
    AprovarOrcamento,
    AprovarOrcamentoComplementar,
    CancelarOrdem,
    ConsultarAcompanhamento,
    CriarOrdem,
    DecidirOrcamento,
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
from src.ordem_servico.dominio.events import (
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrdemCanceladaEvent,
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


# Estados fora da listagem padrao (RN-019/RN-020) — espelha o repositorio real.
_STATUS_ENCERRADOS = frozenset({"finalizada", "entregue", "cancelada"})


class FakeOrdemDeServicoRepository:
    def __init__(self) -> None:
        self._ordens: dict[UUID, OrdemDeServico] = {}
        self._placa_documento: dict[tuple[str, str], list[OrdemDeServico]] = {}
        self.chamadas_obter_por_id: list[tuple[UUID, bool]] = []

    def obter_por_id(
        self, ordem_id: UUID, *, com_lock: bool = False
    ) -> OrdemDeServico | None:
        # Registra cada chamada (id, com_lock) para os testes afirmarem que o
        # caminho de transicao trava (com_lock=True) e o de leitura nao.
        self.chamadas_obter_por_id.append((ordem_id, com_lock))
        return self._ordens.get(ordem_id)

    def salvar(self, ordem: OrdemDeServico) -> None:
        self._ordens[ordem.id] = ordem

    def listar(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        incluir_encerradas: bool = False,
    ) -> list[OrdemDeServico]:
        # Espelha o filtro de leitura RN-019/RN-020 do repositorio real.
        ordens = [
            ordem
            for ordem in self._ordens.values()
            if incluir_encerradas or ordem.status.value not in _STATUS_ENCERRADOS
        ]
        return ordens[offset : offset + limit]

    def contar(self, *, incluir_encerradas: bool = True) -> int:
        if incluir_encerradas:
            return len(self._ordens)
        return sum(
            1
            for ordem in self._ordens.values()
            if ordem.status.value not in _STATUS_ENCERRADOS
        )

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


class CatalogoPorIdStub:
    """``CatalogoPort`` fake que resolve servicos pelo id (multi-servico).

    ``StubCatalogoPort`` devolve sempre o mesmo DTO; os cenarios RF-020
    com mais de um servico precisam de resolucao por id para validar
    que cada linha recebe o preco/nome do servico certo.
    """

    def __init__(self, servicos: dict[UUID, ServicoOferecidoDTO]) -> None:
        self._servicos = servicos

    def obter_servico(self, servico_id: UUID) -> ServicoOferecidoDTO | None:
        return self._servicos.get(servico_id)


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


def _criar_ordem_em_execucao(
    repo: FakeOrdemDeServicoRepository,
) -> OrdemDeServico:
    """OS aprovada e EM_EXECUCAO (transicoes de dominio, sem reserva real)."""
    ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
    ordem.adicionar_item(
        ItemDaOrdem(
            _servico_catalogo_id=uuid4(),
            _descricao="Servico original",
            _quantidade=1,
            _preco_unitario=Dinheiro(valor=Decimal("100.00")),
        )
    )
    ordem.iniciar_diagnostico()
    ordem.gerar_orcamento()
    ordem.aprovar_orcamento()
    ordem.limpar_eventos()
    repo.salvar(ordem)
    return ordem


class TestCriarOrdem:
    def test_sucesso(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort()
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=cp,
            catalogo_port=StubCatalogoPort(),
            estoque_port=StubEstoquePort(),
        )
        dto = CriarOrdemDTO(cliente_id=uuid4(), veiculo_id=uuid4())
        result = uc.executar(dto)
        assert result.status == "recebida"

    def test_cliente_nao_encontrado(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort(cliente_ok=False)
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=cp,
            catalogo_port=StubCatalogoPort(),
            estoque_port=StubEstoquePort(),
        )
        with pytest.raises(ClienteNaoEncontradoException):
            uc.executar(CriarOrdemDTO(uuid4(), uuid4()))

    def test_veiculo_nao_pertence_ao_cliente(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        cp = StubClientePort(veiculo_pertence=False)
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=cp,
            catalogo_port=StubCatalogoPort(),
            estoque_port=StubEstoquePort(),
        )
        with pytest.raises(VeiculoNaoEncontradoException):
            uc.executar(CriarOrdemDTO(uuid4(), uuid4()))


class TestCriarOrdemComItens:
    """RF-020: abertura de OS ja com servicos e pecas em uma unica chamada.

    A criacao orquestra a montagem dos itens (validacao via ports de
    catalogo/estoque, preco da fonte certa) e persiste agregado + itens
    na MESMA UnitOfWork: falha em qualquer item significa rollback total
    (a OS nao pode aparecer no repositorio).
    """

    def _servico(self, nome: str, preco: str) -> ServicoOferecidoDTO:
        return ServicoOferecidoDTO(
            id=uuid4(),
            nome=nome,
            preco=Dinheiro(valor=Decimal(preco)),
            ativo=True,
        )

    def test_cria_os_com_dois_servicos_e_uma_peca(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        troca = self._servico("Troca de oleo", "100.00")
        alinhamento = self._servico("Alinhamento", "80.00")
        peca = ItemEstoqueDTO(
            id=uuid4(),
            nome="Filtro de oleo",
            preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub(
                {troca.id: troca, alinhamento.id: alinhamento}
            ),
            estoque_port=StubEstoquePort(item=peca),
        )
        dto = CriarOrdemDTO(
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            servicos=(
                ServicoDaOrdemDTO(servico_catalogo_id=troca.id),
                ServicoDaOrdemDTO(servico_catalogo_id=alinhamento.id, quantidade=2),
            ),
            pecas=(
                PecaDaOrdemDTO(
                    servico_catalogo_id=troca.id,
                    item_estoque_id=peca.id,
                    quantidade=2,
                ),
            ),
        )

        result = uc.executar(dto)

        assert result.status == "recebida"
        assert len(result.itens) == 3
        # Linha de servico puro: preco do catalogo, descricao = nome do
        # servico, sem contrapartida no estoque; quantidade default 1.
        linha_troca = next(i for i in result.itens if i.descricao == "Troca de oleo")
        assert linha_troca.item_estoque_id is None
        assert linha_troca.quantidade == 1
        assert linha_troca.preco_unitario_centavos == 10000
        linha_alinhamento = next(
            i for i in result.itens if i.descricao == "Alinhamento"
        )
        assert linha_alinhamento.subtotal_centavos == 16000
        # Linha de peca: preco do ESTOQUE (nao do servico), descricao =
        # nome da peca — mesma regra do AdicionarItem (bug historico).
        linha_peca = next(i for i in result.itens if i.descricao == "Filtro de oleo")
        assert linha_peca.item_estoque_id == peca.id
        assert linha_peca.servico_catalogo_id == troca.id
        assert linha_peca.preco_unitario_centavos == 3500
        assert linha_peca.subtotal_centavos == 7000
        # Agregado completo persistido na mesma UoW.
        assert uow.committed is True
        persistida = repo.obter_por_id(result.id)
        assert persistida is not None
        assert len(persistida.itens) == 3

    def test_cria_os_com_peca_inativa_rejeitada(self) -> None:
        # Issue #120: peca desativada nao entra em OS nova (nem e reservada).
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        troca = self._servico("Troca de oleo", "100.00")
        peca_inativa = ItemEstoqueDTO(
            id=uuid4(),
            nome="Filtro descontinuado",
            preco_unitario=Dinheiro(valor=Decimal("35.00")),
            ativo=False,
        )
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub({troca.id: troca}),
            estoque_port=StubEstoquePort(item=peca_inativa),
        )
        dto = CriarOrdemDTO(
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            servicos=(ServicoDaOrdemDTO(servico_catalogo_id=troca.id),),
            pecas=(
                PecaDaOrdemDTO(
                    servico_catalogo_id=troca.id,
                    item_estoque_id=peca_inativa.id,
                    quantidade=1,
                ),
            ),
        )
        with pytest.raises(ViolacaoRegraDeNegocioException, match="inativo"):
            uc.executar(dto)
        assert uow.committed is False  # nada persistido

    def test_rollback_total_com_peca_inexistente(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        troca = self._servico("Troca de oleo", "100.00")
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub({troca.id: troca}),
            estoque_port=StubEstoquePort(item=None),
        )
        dto = CriarOrdemDTO(
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            servicos=(ServicoDaOrdemDTO(servico_catalogo_id=troca.id),),
            pecas=(
                PecaDaOrdemDTO(
                    servico_catalogo_id=troca.id,
                    item_estoque_id=uuid4(),
                    quantidade=1,
                ),
            ),
        )

        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(dto)

        # Rollback TOTAL: nem a OS nem o servico valido persistem.
        assert repo.contar() == 0
        assert uow.committed is False

    def test_rollback_total_com_servico_inexistente(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub({}),
            estoque_port=StubEstoquePort(),
        )
        dto = CriarOrdemDTO(
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            servicos=(ServicoDaOrdemDTO(servico_catalogo_id=uuid4()),),
        )

        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(dto)

        assert repo.contar() == 0
        assert uow.committed is False

    def test_rollback_total_com_servico_inativo(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        inativo = ServicoOferecidoDTO(
            id=uuid4(),
            nome="Servico desativado",
            preco=Dinheiro(valor=Decimal("10.00")),
            ativo=False,
        )
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub({inativo.id: inativo}),
            estoque_port=StubEstoquePort(),
        )
        dto = CriarOrdemDTO(
            cliente_id=uuid4(),
            veiculo_id=uuid4(),
            servicos=(ServicoDaOrdemDTO(servico_catalogo_id=inativo.id),),
        )

        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(dto)

        assert repo.contar() == 0
        assert uow.committed is False

    def test_sem_itens_mantem_comportamento_fase_1(self) -> None:
        """Payload sem listas continua criando OS vazia (compatibilidade)."""
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=CatalogoPorIdStub({}),
            estoque_port=StubEstoquePort(item=None),
        )

        result = uc.executar(CriarOrdemDTO(cliente_id=uuid4(), veiculo_id=uuid4()))

        assert result.status == "recebida"
        assert result.itens == []
        assert uow.committed is True
        assert repo.contar() == 1


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

    def test_em_execucao_reserva_estoque_do_item_novo(self) -> None:
        """#80: adicionar peca em EM_EXECUCAO reserva o estoque do item novo."""
        from src.ordem_servico.aplicacao.ports import ItemEstoqueDTO

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()
        cp = StubCatalogoPort(servico=servico)
        peca = ItemEstoqueDTO(
            id=uuid4(),
            nome="Filtro extra",
            preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        ep = StubEstoquePort(item=peca)
        ordem = _criar_ordem_em_execucao(repo)
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=peca.id,
            descricao="Filtro extra",
            quantidade=2,
        )
        uc.executar(ordem.id, dto)
        assert ep.reservas == [(peca.id, 2)]

    def test_pre_execucao_nao_reserva_estoque_no_add(self) -> None:
        """Antes de EM_EXECUCAO o add NAO reserva (a reserva e na aprovacao)."""
        from src.ordem_servico.aplicacao.ports import ItemEstoqueDTO

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()
        cp = StubCatalogoPort(servico=servico)
        peca = ItemEstoqueDTO(
            id=uuid4(),
            nome="Filtro",
            preco_unitario=Dinheiro(valor=Decimal("35.00")),
        )
        ep = StubEstoquePort(item=peca)
        ordem = _criar_ordem_com_item(repo)  # RECEBIDA
        uc = AdicionarItem(repo=repo, uow=uow, catalogo_port=cp, estoque_port=ep)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=peca.id,
            descricao="Filtro",
            quantidade=2,
        )
        uc.executar(ordem.id, dto)
        assert ep.reservas == []

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

    def test_descricao_vazia_explicita_continua_invalida(self) -> None:
        """``descricao=""`` NAO cai no fallback de nome (so ``None`` cai):
        a string vazia segue chegando ao dominio e violando a invariante
        de ``ItemDaOrdem``, como antes do RF-020."""
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        servico = _servico_dto()
        uc = AdicionarItem(
            repo=repo,
            uow=uow,
            catalogo_port=StubCatalogoPort(servico=servico),
            estoque_port=StubEstoquePort(),
        )
        ordem = _criar_ordem_com_item(repo)
        dto = AdicionarItemDTO(
            servico_catalogo_id=servico.id,
            item_estoque_id=None,
            descricao="",
            quantidade=1,
        )
        with pytest.raises(ValueError, match="Descricao"):
            uc.executar(ordem.id, dto)

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
        rejeitar = RejeitarOrcamentoComplementar(
            repo=repo, uow=uow, estoque_port=StubEstoquePort()
        )
        result = rejeitar.executar(ordem.id)
        assert result.status == "em_execucao"

    def test_rejeitar_libera_reserva_do_item_removido(self) -> None:
        # #111: o item adicionado apos a aprovacao e removido na rejeicao e sua
        # reserva de estoque e liberada na MESMA transacao (uow commitada).
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.aprovar_orcamento()
        item_estoque_id = uuid4()
        ordem.adicionar_item(
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _item_estoque_id=item_estoque_id,
                _descricao="Peca extra",
                _quantidade=3,
                _preco_unitario=Dinheiro(valor=Decimal("50.00")),
            )
        )
        ordem.gerar_orcamento_complementar()
        ordem.limpar_eventos()
        repo.salvar(ordem)

        rejeitar = RejeitarOrcamentoComplementar(
            repo=repo, uow=uow, estoque_port=estoque
        )
        result = rejeitar.executar(ordem.id)

        assert result.status == "em_execucao"
        assert estoque.liberacoes == [(item_estoque_id, 3)]
        assert uow.committed is True


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

    def test_default_exclui_encerradas(self) -> None:
        """RF-023: listagem padrao nao expoe ordens encerradas (RN-019/RN-020)."""
        repo = FakeOrdemDeServicoRepository()
        ativa = _criar_ordem_com_item(repo)
        cancelada = _criar_ordem_com_item(repo)
        cancelada.cancelar(motivo="Cliente desistiu")

        uc = ListarOrdens(repo=repo)
        resultado = uc.executar()

        assert [dto.id for dto in resultado] == [ativa.id]

    def test_incluir_encerradas_devolve_visao_completa(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        cancelada = _criar_ordem_com_item(repo)
        cancelada.cancelar(motivo="Cliente desistiu")

        uc = ListarOrdens(repo=repo)
        resultado = uc.executar(incluir_encerradas=True)

        assert len(resultado) == 2


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


class TestLockPessimistaNasTransicoes:
    """Contrato de lock (issue #82): transicoes travam, leituras nao.

    Afere o flag ``com_lock`` repassado ao repositorio (instrumentado pelo
    fake) em vez do efeito SQL — o FOR UPDATE real e provado na suite de
    integracao (``test_concorrencia_lock.py``). Aqui garantimos que NENHUMA
    transicao perca o lock por engano e que o caminho de LEITURA jamais o
    adquira.
    """

    def test_iniciar_diagnostico_carrega_com_lock(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        repo.chamadas_obter_por_id.clear()
        IniciarDiagnostico(repo=repo, uow=uow).executar(ordem.id)
        assert repo.chamadas_obter_por_id == [(ordem.id, True)]

    def test_aprovar_orcamento_carrega_com_lock(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = OrdemDeServico.criar(uuid4(), uuid4())
        ordem.adicionar_item(
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _item_estoque_id=uuid4(),
                _descricao="Filtro",
                _quantidade=2,
                _preco_unitario=Dinheiro(valor=Decimal("50.00")),
            )
        )
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        repo.chamadas_obter_por_id.clear()
        AprovarOrcamento(repo=repo, uow=uow, estoque_port=estoque).executar(ordem.id)
        assert repo.chamadas_obter_por_id == [(ordem.id, True)]

    def test_cancelar_ordem_carrega_com_lock(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = _criar_ordem_com_item(repo)
        repo.chamadas_obter_por_id.clear()
        CancelarOrdem(repo=repo, uow=uow, estoque_port=estoque).executar(
            ordem.id, CancelarOrdemDTO(motivo="Desistiu")
        )
        assert repo.chamadas_obter_por_id == [(ordem.id, True)]

    def test_obter_ordem_nao_trava_a_linha(self) -> None:
        # Caminho read-only compartilha _obter_ordem -> deve usar com_lock=False.
        repo = FakeOrdemDeServicoRepository()
        ordem = _criar_ordem_com_item(repo)
        repo.chamadas_obter_por_id.clear()
        ObterOrdem(repo=repo).executar(ordem.id)
        assert repo.chamadas_obter_por_id == [(ordem.id, False)]


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

    def test_contar_acompanha_filtro_de_encerradas(self) -> None:
        """Total de paginacao consistente com o universo listado (RF-023)."""
        repo = FakeOrdemDeServicoRepository()
        _criar_ordem_com_item(repo)
        cancelada = _criar_ordem_com_item(repo)
        cancelada.cancelar(motivo="Cliente desistiu")

        uc = ListarOrdens(repo=repo)

        assert uc.contar() == 1
        assert uc.contar(incluir_encerradas=True) == 2


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
        uc = CriarOrdem(
            repo=repo,
            uow=uow,
            cliente_port=StubClientePort(),
            catalogo_port=StubCatalogoPort(),
            estoque_port=StubEstoquePort(),
        )
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


class TestDecidirOrcamento:
    """RF-022 (ADR-021): decisao externa sobre o orcamento corrente.

    ``DecidirOrcamento`` compoe os casos de uso existentes:
    ``aprovada`` delega a ``AprovarOrcamento`` (inicial) ou
    ``AprovarOrcamentoComplementar`` (complementar pendente);
    ``recusada`` delega a ``CancelarOrdem`` com motivo fixo. Fora dos
    dois estados de espera, o guard levanta o erro de transicao ANTES
    de qualquer delegacao — sem ele, uma recusa externa cancelaria OS
    em qualquer estado ativo (``CancelarOrdem`` aceita todos).
    """

    def _montar_uc(
        self,
        repo: FakeOrdemDeServicoRepository,
        uow: FakeUnitOfWork,
        estoque: StubEstoquePort,
    ) -> DecidirOrcamento:
        return DecidirOrcamento(
            repo=repo,
            aprovar_orcamento=AprovarOrcamento(
                repo=repo, uow=uow, estoque_port=estoque
            ),
            aprovar_complementar=AprovarOrcamentoComplementar(repo=repo, uow=uow),
            cancelar_ordem=CancelarOrdem(repo=repo, uow=uow, estoque_port=estoque),
        )

    def _ordem_aguardando_aprovacao(
        self, repo: FakeOrdemDeServicoRepository, *, com_estoque: bool = False
    ) -> OrdemDeServico:
        ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem.adicionar_item(
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _item_estoque_id=uuid4() if com_estoque else None,
                _descricao="Troca de oleo",
                _quantidade=2,
                _preco_unitario=Dinheiro(valor=Decimal("100.00")),
            )
        )
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        return ordem

    def _ordem_aguardando_complementar(
        self, repo: FakeOrdemDeServicoRepository, *, com_estoque: bool = False
    ) -> OrdemDeServico:
        ordem = self._ordem_aguardando_aprovacao(repo, com_estoque=com_estoque)
        ordem.aprovar_orcamento()
        ordem.gerar_orcamento_complementar()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        return ordem

    def test_aprovada_em_aguardando_aprovacao_reserva_e_executa(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = self._ordem_aguardando_aprovacao(repo, com_estoque=True)
        uc = self._montar_uc(repo, uow, estoque)

        result = uc.executar(ordem.id, decisao="aprovada")

        assert result.status == "em_execucao"
        # Delegou a AprovarOrcamento: reserva de estoque aconteceu.
        assert len(estoque.reservas) == 1
        assert uow.committed is True

    def test_guard_le_sem_lock_e_delegada_le_com_lock(self) -> None:
        # Issue #82: o guard de estado de DecidirOrcamento e uma LEITURA (sem
        # lock); a transicao real (AprovarOrcamento delegada) re-le com lock.
        # Esperado: 1a chamada com_lock=False (guard), 2a com_lock=True (delega).
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = self._ordem_aguardando_aprovacao(repo, com_estoque=True)
        uc = self._montar_uc(repo, uow, estoque)
        repo.chamadas_obter_por_id.clear()

        uc.executar(ordem.id, decisao="aprovada")

        assert repo.chamadas_obter_por_id == [(ordem.id, False), (ordem.id, True)]

    def test_recusada_revalida_espera_sob_lock(self) -> None:
        # Issue #119: uma aprovacao interna concorrente move a OS de
        # AGUARDANDO_APROVACAO para EM_EXECUCAO entre o guard (sem lock) e a
        # delegacao. A releitura SOB LOCK do caminho 'recusada' deve rejeitar,
        # em vez de cancelar uma OS ja em execucao (CancelarOrdem aceitaria
        # qualquer estado ativo).
        from src.ordem_servico.dominio.status import StatusOrdem

        ordem = OrdemDeServico.criar(cliente_id=uuid4(), veiculo_id=uuid4())
        ordem.adicionar_item(
            ItemDaOrdem(
                _servico_catalogo_id=uuid4(),
                _item_estoque_id=None,
                _descricao="Troca de oleo",
                _quantidade=1,
                _preco_unitario=Dinheiro(valor=Decimal("100.00")),
            )
        )
        ordem.iniciar_diagnostico()
        ordem.gerar_orcamento()  # AGUARDANDO_APROVACAO
        ordem.limpar_eventos()

        class RepoAprovacaoConcorrente:
            """Fake que simula a aprovacao interna chegando no momento do lock:
            a leitura de GUARD (com_lock=False) ve AGUARDANDO_APROVACAO; a
            releitura SOB LOCK (com_lock=True) ja encontra EM_EXECUCAO."""

            def obter_por_id(
                self, ordem_id: UUID, *, com_lock: bool = False
            ) -> OrdemDeServico:
                if com_lock and ordem.status is StatusOrdem.AGUARDANDO_APROVACAO:
                    ordem.aprovar_orcamento()
                    ordem.limpar_eventos()
                return ordem

            def salvar(self, _o: OrdemDeServico) -> None:
                pass

        repo = RepoAprovacaoConcorrente()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        uc = DecidirOrcamento(
            repo=repo,  # type: ignore[arg-type]  # fake de teste
            aprovar_orcamento=AprovarOrcamento(
                repo=repo,  # type: ignore[arg-type]
                uow=uow,
                estoque_port=estoque,
            ),
            aprovar_complementar=AprovarOrcamentoComplementar(
                repo=repo,  # type: ignore[arg-type]
                uow=uow,
            ),
            cancelar_ordem=CancelarOrdem(
                repo=repo,  # type: ignore[arg-type]
                uow=uow,
                estoque_port=estoque,
            ),
        )

        with pytest.raises(TransicaoStatusInvalidaException):
            uc.executar(ordem.id, decisao="recusada")
        # Nao cancelou: a OS segue em execucao, sem commit.
        assert ordem.status is StatusOrdem.EM_EXECUCAO
        assert uow.committed is False

    def test_aprovada_em_complementar_usa_caminho_complementar(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = self._ordem_aguardando_complementar(repo, com_estoque=True)
        reservas_antes = len(estoque.reservas)
        uc = self._montar_uc(repo, uow, estoque)

        result = uc.executar(ordem.id, decisao="aprovada")

        assert result.status == "em_execucao"
        # Caminho correto: AprovarOrcamentoComplementar nao re-reserva
        # estoque nem emite OrcamentoAprovadoEvent (semantica interna).
        assert len(estoque.reservas) == reservas_antes
        eventos = repo.obter_por_id(ordem.id).coletar_eventos()  # type: ignore[union-attr]
        assert any(isinstance(e, OrcamentoComplementarAprovadoEvent) for e in eventos)
        assert not any(isinstance(e, OrcamentoAprovadoEvent) for e in eventos)

    def test_recusada_em_aguardando_aprovacao_cancela_com_motivo_fixo(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = self._ordem_aguardando_aprovacao(repo)
        uc = self._montar_uc(repo, uow, estoque)

        result = uc.executar(ordem.id, decisao="recusada")

        assert result.status == "cancelada"
        eventos = repo.obter_por_id(ordem.id).coletar_eventos()  # type: ignore[union-attr]
        cancelamentos = [e for e in eventos if isinstance(e, OrdemCanceladaEvent)]
        assert len(cancelamentos) == 1
        assert cancelamentos[0].motivo == MOTIVO_RECUSA_EXTERNA
        # Sem reserva ativa em AGUARDANDO_APROVACAO: nada a liberar.
        assert estoque.liberacoes == []

    def test_recusada_em_complementar_cancela_e_libera_estoque(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        estoque = StubEstoquePort()
        ordem = self._ordem_aguardando_complementar(repo, com_estoque=True)
        uc = self._montar_uc(repo, uow, estoque)

        result = uc.executar(ordem.id, decisao="recusada")

        assert result.status == "cancelada"
        # CancelarOrdem libera a reserva feita na aprovacao do inicial.
        assert len(estoque.liberacoes) == 1

    def test_recusada_fora_de_espera_nao_cancela(self) -> None:
        """Guard: sem ele, CancelarOrdem aceitaria cancelar OS RECEBIDA."""
        from src.compartilhado.dominio.exceptions import (
            TransicaoStatusInvalidaException,
        )

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)  # RECEBIDA
        uc = self._montar_uc(repo, uow, StubEstoquePort())

        with pytest.raises(TransicaoStatusInvalidaException):
            uc.executar(ordem.id, decisao="recusada")

        assert repo.obter_por_id(ordem.id).status.value == "recebida"  # type: ignore[union-attr]
        assert uow.committed is False

    def test_aprovada_fora_de_espera_levanta_transicao_invalida(self) -> None:
        from src.compartilhado.dominio.exceptions import (
            TransicaoStatusInvalidaException,
        )

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = self._ordem_aguardando_aprovacao(repo)
        ordem.aprovar_orcamento()  # EM_EXECUCAO
        ordem.limpar_eventos()
        repo.salvar(ordem)
        uc = self._montar_uc(repo, uow, StubEstoquePort())

        with pytest.raises(TransicaoStatusInvalidaException):
            uc.executar(ordem.id, decisao="aprovada")
        assert uow.committed is False

    def test_ordem_inexistente_levanta_nao_encontrada(self) -> None:
        repo = FakeOrdemDeServicoRepository()
        uc = self._montar_uc(repo, FakeUnitOfWork(), StubEstoquePort())
        with pytest.raises(OrdemNaoEncontradaException):
            uc.executar(uuid4(), decisao="aprovada")

    def test_decisao_invalida_levanta_value_error(self) -> None:
        """Defesa em profundidade: o schema HTTP ja restringe via Literal,
        mas o caso de uso nao confia na borda (422 via handler global)."""
        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = self._ordem_aguardando_aprovacao(repo)
        uc = self._montar_uc(repo, uow, StubEstoquePort())

        with pytest.raises(ValueError, match="decisao"):
            uc.executar(ordem.id, decisao="talvez")
        assert uow.committed is False


class TestDispatchDeEventosPosCommit:
    """RF-024: casos de uso de transicao despacham eventos APOS o commit.

    O dispatcher e opcional (default ``None`` preserva o comportamento da
    fase 1); quando presente, recebe ``ordem.coletar_eventos()`` somente
    depois de ``uow.commit()`` — o handler enxerga a OS ja persistida.
    O dispatch NAO limpa ``_eventos_pendentes`` (semantica observada
    pelos testes existentes e pela fase 1 permanece intacta).
    """

    @staticmethod
    def _ordem_em(
        repo: FakeOrdemDeServicoRepository, *transicoes: str
    ) -> OrdemDeServico:
        ordem = _criar_ordem_com_item(repo)
        for nome in transicoes:
            getattr(ordem, nome)()
        ordem.limpar_eventos()
        repo.salvar(ordem)
        return ordem

    def test_iniciar_diagnostico_despacha_apos_commit_com_ordem_persistida(
        self,
    ) -> None:
        from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
        from src.ordem_servico.dominio.events import DiagnosticoIniciadoEvent

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)
        visto: list[tuple[type, bool, str]] = []

        def handler(evento: object) -> None:
            persistida = repo.obter_por_id(ordem.id)
            assert persistida is not None
            visto.append((type(evento), uow.committed, persistida.status.value))

        uc = IniciarDiagnostico(
            repo=repo, uow=uow, dispatcher=EventDispatcher(handlers=(handler,))
        )
        uc.executar(ordem.id)

        # Uma unica notificacao, depois do commit, com o estado novo visivel.
        assert visto == [(DiagnosticoIniciadoEvent, True, "em_diagnostico")]

    def test_dispatch_nao_limpa_eventos_pendentes(self) -> None:
        from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
        from src.ordem_servico.dominio.events import DiagnosticoIniciadoEvent

        repo = FakeOrdemDeServicoRepository()
        ordem = _criar_ordem_com_item(repo)
        uc = IniciarDiagnostico(
            repo=repo,
            uow=FakeUnitOfWork(),
            dispatcher=EventDispatcher(handlers=()),
        )

        uc.executar(ordem.id)

        eventos = ordem.coletar_eventos()
        assert len(eventos) == 1
        assert isinstance(eventos[0], DiagnosticoIniciadoEvent)

    def test_falha_de_handler_nao_afeta_a_transicao(self) -> None:
        from src.ordem_servico.aplicacao.dispatcher import EventDispatcher

        repo = FakeOrdemDeServicoRepository()
        uow = FakeUnitOfWork()
        ordem = _criar_ordem_com_item(repo)

        def handler_quebrado(_evento: object) -> None:
            raise RuntimeError("notificacao falhou")

        uc = IniciarDiagnostico(
            repo=repo, uow=uow, dispatcher=EventDispatcher(handlers=(handler_quebrado,))
        )
        result = uc.executar(ordem.id)

        assert result.status == "em_diagnostico"
        assert uow.committed is True
        assert repo.obter_por_id(ordem.id).status.value == "em_diagnostico"  # type: ignore[union-attr]

    def test_todas_as_transicoes_despacham_o_evento_correspondente(self) -> None:
        """Cobertura exaustiva: TODOS os casos de uso que mudam status
        publicam o evento da transicao quando ha dispatcher injetado.
        ``CriarOrdem`` fica de fora por desenho (criacao nao e mudanca
        de status — RF-024 notifica atualizacoes).
        """
        from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
        from src.ordem_servico.dominio.events import (
            DiagnosticoIniciadoEvent,
            EntregaRegistradaEvent,
            OrcamentoComplementarGeradoEvent,
            OrcamentoComplementarRejeitadoEvent,
            OrcamentoGeradoEvent,
            ServicoFinalizadoEvent,
        )

        ate_execucao = ("iniciar_diagnostico", "gerar_orcamento", "aprovar_orcamento")
        casos = [
            (
                (),
                lambda r, u, d: IniciarDiagnostico(repo=r, uow=u, dispatcher=d),
                lambda uc, oid: uc.executar(oid),
                DiagnosticoIniciadoEvent,
            ),
            (
                ("iniciar_diagnostico",),
                lambda r, u, d: GerarOrcamento(repo=r, uow=u, dispatcher=d),
                lambda uc, oid: uc.executar(oid),
                OrcamentoGeradoEvent,
            ),
            (
                ("iniciar_diagnostico", "gerar_orcamento"),
                lambda r, u, d: AprovarOrcamento(
                    repo=r, uow=u, estoque_port=StubEstoquePort(), dispatcher=d
                ),
                lambda uc, oid: uc.executar(oid),
                OrcamentoAprovadoEvent,
            ),
            (
                ate_execucao,
                lambda r, u, d: FinalizarServico(repo=r, uow=u, dispatcher=d),
                lambda uc, oid: uc.executar(oid),
                ServicoFinalizadoEvent,
            ),
            (
                (*ate_execucao, "finalizar_servico"),
                lambda r, u, d: RegistrarEntrega(repo=r, uow=u, dispatcher=d),
                lambda uc, oid: uc.executar(oid),
                EntregaRegistradaEvent,
            ),
            (
                (),
                lambda r, u, d: CancelarOrdem(
                    repo=r, uow=u, estoque_port=StubEstoquePort(), dispatcher=d
                ),
                lambda uc, oid: uc.executar(
                    oid, CancelarOrdemDTO(motivo="desistencia")
                ),
                OrdemCanceladaEvent,
            ),
            (
                ate_execucao,
                lambda r, u, d: GerarOrcamentoComplementar(repo=r, uow=u, dispatcher=d),
                lambda uc, oid: uc.executar(oid),
                OrcamentoComplementarGeradoEvent,
            ),
            (
                (*ate_execucao, "gerar_orcamento_complementar"),
                lambda r, u, d: AprovarOrcamentoComplementar(
                    repo=r, uow=u, dispatcher=d
                ),
                lambda uc, oid: uc.executar(oid),
                OrcamentoComplementarAprovadoEvent,
            ),
            (
                (*ate_execucao, "gerar_orcamento_complementar"),
                lambda r, u, d: RejeitarOrcamentoComplementar(
                    repo=r, uow=u, estoque_port=StubEstoquePort(), dispatcher=d
                ),
                lambda uc, oid: uc.executar(oid),
                OrcamentoComplementarRejeitadoEvent,
            ),
        ]

        for transicoes, montar_uc, executar, evento_esperado in casos:
            repo = FakeOrdemDeServicoRepository()
            uow = FakeUnitOfWork()
            ordem = self._ordem_em(repo, *transicoes)
            despachados: list[object] = []
            uc = montar_uc(repo, uow, EventDispatcher(handlers=(despachados.append,)))

            executar(uc, ordem.id)

            tipos = [type(e) for e in despachados]
            assert tipos == [evento_esperado], (
                f"{type(uc).__name__} deveria despachar {evento_esperado.__name__}, "
                f"despachou {tipos}"
            )
