"""Casos de uso da aplicacao Ordem de Servico.

Cada classe expoe um unico metodo ``executar(...)`` que orquestra o
repositorio, o ``UnitOfWork`` e, quando aplicavel, as portas para outros
bounded contexts (``EstoquePort``, ``CatalogoPort``, ``ClientePort``).
As regras de negocio ficam no agregado ``OrdemDeServico``; os casos de
uso apenas compoem a sequencia de operacoes, mapeiam entrada/saida para
DTOs e garantem a fronteira transacional via ``with self._uow:``.

Event dispatch (RF-024): os casos de uso de TRANSICAO de status aceitam
um ``EventDispatcher`` opcional e entregam ``ordem.coletar_eventos()`` a
ele APOS o commit da UnitOfWork — o handler enxerga a OS ja persistida e
falha de handler nunca desfaz a transicao (o dispatcher engole e loga).
O dispatch nao limpa ``_eventos_pendentes``: agregados sao request-scoped
e a semantica de acumulacao observada desde a fase 1 permanece. Sem
dispatcher injetado (default ``None``), o comportamento da fase 1 e
preservado integralmente. ``CriarOrdem`` nao despacha por desenho:
criacao nao e atualizacao de status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from src.compartilhado.dominio.exceptions import (
    TransicaoStatusInvalidaException,
    ViolacaoRegraDeNegocioException,
)
from src.ordem_servico.aplicacao.dtos import (
    AcompanhamentoDTO,
    AdicionarItemDTO,
    CancelarOrdemDTO,
    ItemDaOrdemDTO,
    LinhaOrcamentoDTO,
    MetricasDTO,
    OrcamentoDTO,
    OrdemDeServicoDTO,
    OrdemResumoDTO,
)
from src.ordem_servico.dominio.exceptions import (
    ClienteNaoEncontradoException,
    OrdemNaoEncontradaException,
    VeiculoNaoEncontradoException,
)
from src.ordem_servico.dominio.status import StatusOrdem

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork
    from src.compartilhado.dominio.dinheiro import Dinheiro
    from src.ordem_servico.aplicacao.dispatcher import EventDispatcher
    from src.ordem_servico.aplicacao.dtos import CriarOrdemDTO
    from src.ordem_servico.aplicacao.ports import (
        CatalogoPort,
        ClientePort,
        EstoquePort,
    )
    from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
    from src.ordem_servico.dominio.orcamento import Orcamento
    from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
    from src.ordem_servico.dominio.repository import OrdemDeServicoRepository

# Vocabulario do canal externo de decisao de orcamento (RF-022 / ADR-021).
# O schema HTTP restringe via Literal; o caso de uso revalida (defesa em
# profundidade) e usa o motivo fixo na recusa via CancelarOrdem.
DECISAO_APROVADA = "aprovada"
DECISAO_RECUSADA = "recusada"
MOTIVO_RECUSA_EXTERNA = "orcamento recusado pelo cliente"


def _to_centavos(dinheiro: Dinheiro) -> int:
    """Converte ``Dinheiro`` para centavos inteiros."""
    return int(dinheiro.valor * 100)


def _item_dto(item: ItemDaOrdem) -> ItemDaOrdemDTO:
    """Projeta um ``ItemDaOrdem`` para ``ItemDaOrdemDTO``."""
    return ItemDaOrdemDTO(
        id=item.id,
        servico_catalogo_id=item.servico_catalogo_id,
        item_estoque_id=item.item_estoque_id,
        descricao=item.descricao,
        quantidade=item.quantidade,
        preco_unitario_centavos=_to_centavos(item.preco_unitario),
        subtotal_centavos=_to_centavos(item.subtotal),
    )


def _orcamento_dto(orc: Orcamento | None) -> OrcamentoDTO | None:
    """Projeta ``Orcamento`` para ``OrcamentoDTO``, ou ``None``."""
    if orc is None:
        return None
    linhas = [
        LinhaOrcamentoDTO(
            descricao=linha.descricao,
            quantidade=linha.quantidade,
            preco_unitario_centavos=_to_centavos(linha.preco_unitario),
            subtotal_centavos=_to_centavos(linha.subtotal),
        )
        for linha in orc.itens
    ]
    return OrcamentoDTO(
        total_centavos=_to_centavos(orc.total),
        gerado_em=orc.gerado_em,
        itens=linhas,
    )


def _ordem_dto(os: OrdemDeServico) -> OrdemDeServicoDTO:
    """Projeta o agregado ``OrdemDeServico`` para ``OrdemDeServicoDTO``."""
    return OrdemDeServicoDTO(
        id=os.id,
        cliente_id=os.cliente_id,
        veiculo_id=os.veiculo_id,
        status=os.status.value,
        itens=[_item_dto(i) for i in os.itens],
        orcamento=_orcamento_dto(os.orcamento),
        criado_em=os.criado_em,
        atualizado_em=os.atualizado_em,
    )


def _ordem_resumo(os: OrdemDeServico) -> OrdemResumoDTO:
    """Projeta o agregado para a forma compacta ``OrdemResumoDTO``."""
    return OrdemResumoDTO(
        id=os.id,
        cliente_id=os.cliente_id,
        veiculo_id=os.veiculo_id,
        status=os.status.value,
        criado_em=os.criado_em,
    )


def _obter_ordem(
    repo: OrdemDeServicoRepository, ordem_id: UUID, *, com_lock: bool = False
) -> OrdemDeServico:
    """Busca a ordem ou levanta ``OrdemNaoEncontradaException``.

    ``com_lock=True`` carrega a ordem com ``SELECT ... FOR UPDATE`` (issue
    #82): os casos de uso de MUTACAO/TRANSICAO passam ``True`` para que a
    linha fique travada durante toda a transacao da transicao — a 2a
    requisicao concorrente bloqueia no lock, re-le o estado pos-commit e a
    maquina de status rejeita a transicao agora ilegal (1 evento, nao N).
    Os caminhos de LEITURA (``ObterOrdem`` e o guard de ``DecidirOrcamento``)
    usam o default ``False``: nunca devem adquirir lock pessimista.
    """
    ordem = repo.obter_por_id(ordem_id, com_lock=com_lock)
    if ordem is None:
        raise OrdemNaoEncontradaException()
    return ordem


def _reservas_de_estoque_ordenadas(ordem: OrdemDeServico) -> list[tuple[UUID, int]]:
    """``(item_estoque_id, quantidade)`` das pecas, em ordem de ``id``.

    Reserva/liberacao de varios itens numa transacao deve adquirir os locks
    pessimistas (``FOR UPDATE``) sempre na MESMA ordem global de id (issue
    #83) — espelha o ``order_by(id)`` de ``obter_por_ids`` do repositorio de
    Estoque. Sem isso, duas aprovacoes que tocam os mesmos itens em ordens
    de insercao diferentes poderiam cruzar locks e deadlockar. Itens de mao
    de obra (``item_estoque_id is None``) ficam de fora — nao reservam; o
    filtro tambem estreita o tipo para ``UUID`` (nao ``UUID | None``).
    """
    pares = [
        (item.item_estoque_id, item.quantidade)
        for item in ordem.itens
        if item.item_estoque_id is not None
    ]
    return sorted(pares, key=lambda par: par[0])


def _despachar_pos_commit(
    dispatcher: EventDispatcher | None, ordem: OrdemDeServico
) -> None:
    """Publica os eventos pendentes da ordem apos o commit (RF-024).

    Chamado pelos casos de uso de transicao DEPOIS do bloco ``with uow``:
    o commit ja aconteceu e o dispatcher engole qualquer falha de handler,
    entao a transicao persistida nunca e afetada. Nao limpa os eventos do
    agregado (semantica request-scoped preservada — ver docstring do
    modulo).
    """
    if dispatcher is None:
        return
    dispatcher.despachar(ordem.coletar_eventos())


def _montar_item(
    catalogo_port: CatalogoPort,
    estoque_port: EstoquePort,
    dto: AdicionarItemDTO,
) -> ItemDaOrdem:
    """Valida servico/peca via ports e monta o ``ItemDaOrdem`` com o preco certo.

    Unica fonte da regra de composicao de linha (compartilhada por
    ``CriarOrdem`` RF-020 e ``AdicionarItem``):

    - ``item_estoque_id`` presente => linha de peca consumida; preco vem
      do ESTOQUE. Bug historico (corrigido): o preco era SEMPRE
      ``servico.preco``, mesmo com ``item_estoque_id`` informado, o que
      omitia o valor da peca no orcamento.
    - ``item_estoque_id`` ausente => linha de mao de obra; preco do
      servico no catalogo.
    - ``descricao`` ``None`` => usa o nome do servico/peca resolvido via
      port (caminho RF-020, em que o payload de criacao nao carrega
      descricao livre).

    Raises:
        ViolacaoRegraDeNegocioException: servico inexistente, servico
            inativo ou item de estoque inexistente.
    """
    from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem

    servico = catalogo_port.obter_servico(dto.servico_catalogo_id)
    if servico is None:
        raise ViolacaoRegraDeNegocioException(
            mensagem="Servico nao encontrado no catalogo"
        )
    if not servico.ativo:
        raise ViolacaoRegraDeNegocioException(mensagem="Servico inativo")

    if dto.item_estoque_id is not None:
        peca = estoque_port.obter_item(dto.item_estoque_id)
        if peca is None:
            raise ViolacaoRegraDeNegocioException(
                mensagem="Item de estoque nao encontrado"
            )
        preco_unitario = peca.preco_unitario
        nome_padrao = peca.nome
    else:
        preco_unitario = servico.preco
        nome_padrao = servico.nome
    # `is None` (e nao falsy): descricao explicita vazia continua chegando
    # ao dominio e falhando na invariante de ItemDaOrdem (422), como antes
    # do RF-020 — apenas a ausencia deliberada resolve para o nome.
    descricao = nome_padrao if dto.descricao is None else dto.descricao

    return ItemDaOrdem(
        _servico_catalogo_id=dto.servico_catalogo_id,
        _item_estoque_id=dto.item_estoque_id,
        _descricao=descricao,
        _quantidade=dto.quantidade,
        _preco_unitario=preco_unitario,
    )


class CriarOrdem:
    """Cria uma ``OrdemDeServico``, opcionalmente ja com servicos e pecas.

    RF-020: a abertura recebe cliente, veiculo e listas opcionais de
    servicos/pecas numa unica chamada. Os itens sao montados com a MESMA
    regra do ``AdicionarItem`` (via ``_montar_item``) e persistidos com o
    agregado na mesma UnitOfWork — falha em qualquer item aborta a
    criacao inteira (a OS nao persiste). Listas vazias reproduzem o
    comportamento da fase 1.
    """

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        cliente_port: ClientePort,
        catalogo_port: CatalogoPort,
        estoque_port: EstoquePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._cliente_port = cliente_port
        self._catalogo_port = catalogo_port
        self._estoque_port = estoque_port

    def executar(self, dto: CriarOrdemDTO) -> OrdemDeServicoDTO:
        """Valida cliente + veiculo, monta itens (se houver) e persiste.

        Toda a montagem acontece em memoria ANTES do unico
        ``repo.salvar`` dentro da UoW: qualquer item invalido levanta
        antes de existir escrita pendente, e o commit unico garante
        atomicidade agregado + itens no banco.

        Raises:
            ClienteNaoEncontradoException: cliente_id nao existe (404).
            VeiculoNaoEncontradoException: veiculo nao existe ou nao pertence
                ao cliente informado (404). Os dois casos sao indistinguiveis
                na resposta para preservar defesa em profundidade.
            ViolacaoRegraDeNegocioException: servico/peca de algum item
                inexistente ou servico inativo (409) — nada e persistido.
        """
        from src.ordem_servico.dominio.ordem_de_servico import (
            OrdemDeServico,
        )

        if not self._cliente_port.cliente_existe(dto.cliente_id):
            raise ClienteNaoEncontradoException()
        if not self._cliente_port.veiculo_pertence_ao_cliente(
            dto.cliente_id,
            dto.veiculo_id,
        ):
            raise VeiculoNaoEncontradoException()
        ordem = OrdemDeServico.criar(
            cliente_id=dto.cliente_id, veiculo_id=dto.veiculo_id
        )
        linhas = [
            AdicionarItemDTO(
                servico_catalogo_id=servico.servico_catalogo_id,
                item_estoque_id=None,
                descricao=None,
                quantidade=servico.quantidade,
            )
            for servico in dto.servicos
        ] + [
            AdicionarItemDTO(
                servico_catalogo_id=peca.servico_catalogo_id,
                item_estoque_id=peca.item_estoque_id,
                descricao=None,
                quantidade=peca.quantidade,
            )
            for peca in dto.pecas
        ]
        for linha in linhas:
            ordem.adicionar_item(
                _montar_item(self._catalogo_port, self._estoque_port, linha)
            )
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class AdicionarItem:
    """Adiciona um item a uma ordem existente.

    A montagem da linha (validacao de servico/peca e resolucao do preco
    da fonte certa) e compartilhada com ``CriarOrdem`` em ``_montar_item``
    — ver docstring do helper para a regra e o bug historico de preco.
    """

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        catalogo_port: CatalogoPort,
        estoque_port: EstoquePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._catalogo_port = catalogo_port
        self._estoque_port = estoque_port

    def executar(self, ordem_id: UUID, dto: AdicionarItemDTO) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.adicionar_item``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            ViolacaoRegraDeNegocioException: servico inativo, servico/peca
                inexistente.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        item = _montar_item(self._catalogo_port, self._estoque_port, dto)
        ordem.adicionar_item(item)
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class RemoverItem:
    """Remove um item de uma ordem (valido apenas em RECEBIDA / EM_DIAGNOSTICO)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID, item_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.remover_item``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            ViolacaoRegraDeNegocioException: item inexistente ou status invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.remover_item(item_id)
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class IniciarDiagnostico:
    """Transita a ordem para EM_DIAGNOSTICO (emite ``DiagnosticoIniciadoEvent``)."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.iniciar_diagnostico``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual nao permite iniciar.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.iniciar_diagnostico()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class GerarOrcamento:
    """Gera o ``Orcamento`` a partir dos itens e transita para AGUARDANDO_APROVACAO."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.gerar_orcamento``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            ViolacaoRegraDeNegocioException: ordem sem itens.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.gerar_orcamento()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class AprovarOrcamento:
    """Aprova o orcamento, reserva itens no estoque e transita para EM_EXECUCAO."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        estoque_port: EstoquePort,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._estoque_port = estoque_port
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Reserva estoque e delega ao agregado ``OrdemDeServico.aprovar_orcamento``.

        A reserva acontece DENTRO da UoW, antes da transicao: se a
        transicao ou o ``salvar`` falharem, a reserva e revertida via
        rollback da sessao compartilhada.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            EntidadeNaoEncontradaException: item de estoque inexistente.
        """
        # com_lock=True trava a OS ANTES de reservar estoque: define a ordem
        # global de aquisicao de locks OS -> Estoque (issue #82 + #83), o que
        # evita deadlock cruzado com outros caminhos que tocam os dois
        # agregados. O lock e retido ate o commit da UoW (mesma session/tx).
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        with self._uow:
            # Ordem determinista de id ao reservar varios itens (anti-deadlock).
            for item_estoque_id, quantidade in _reservas_de_estoque_ordenadas(ordem):
                self._estoque_port.reservar(item_estoque_id, quantidade)
            ordem.aprovar_orcamento()
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class FinalizarServico:
    """Transita a ordem para FINALIZADA (emite ``ServicoFinalizadoEvent``)."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.finalizar_servico``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.finalizar_servico()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class RegistrarEntrega:
    """Transita a ordem para ENTREGUE (emite ``EntregaRegistradaEvent``)."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.registrar_entrega``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.registrar_entrega()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class CancelarOrdem:
    """Cancela a ordem e libera reservas de estoque ativas (se houver)."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        estoque_port: EstoquePort,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._estoque_port = estoque_port
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID, dto: CancelarOrdemDTO) -> OrdemDeServicoDTO:
        """Libera reservas (se aplicavel) e delega ao agregado ``cancelar``.

        Liberacao + cancelamento acontecem no mesmo escopo transacional
        via ``with self._uow:`` — se o cancelamento falhar, a liberacao
        e revertida pelo rollback da sessao. Retorna o DTO completo da
        ordem ja cancelada para consistencia com os outros casos de uso
        de escrita (o router PR 11 pode responder HTTP 200 com o recurso
        atualizado).

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status ja em estado terminal.
            ViolacaoRegraDeNegocioException: motivo vazio.
            EntidadeNaoEncontradaException: item de estoque inexistente.
        """
        # com_lock=True: mesma ordem de aquisicao OS -> Estoque de
        # AprovarOrcamento (a liberacao de reservas trava os itens depois da
        # OS), retido ate o commit da UoW.
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        # Liberacao de reservas e cancelamento devem compartilhar o mesmo
        # escopo transacional (consistencia com AprovarOrcamento): se o
        # cancelamento falhar apos a liberacao, a UoW faz rollback das
        # duas mudancas atomicamente.
        with self._uow:
            if ordem.status in {
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
            }:
                # Ordem determinista de id ao liberar (anti-deadlock, igual
                # ao caminho de reserva de AprovarOrcamento).
                for item_estoque_id, quantidade in _reservas_de_estoque_ordenadas(
                    ordem
                ):
                    self._estoque_port.liberar(item_estoque_id, quantidade)
            ordem.cancelar(dto.motivo)
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class GerarOrcamentoComplementar:
    """Gera um orcamento complementar a partir dos itens adicionais."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.gerar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            ViolacaoRegraDeNegocioException: ordem sem itens.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.gerar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class AprovarOrcamentoComplementar:
    """Aprova o orcamento complementar, retornando a ordem a EM_EXECUCAO."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.aprovar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.aprovar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class RejeitarOrcamentoComplementar:
    """Rejeita o orcamento complementar, retornando a ordem a EM_EXECUCAO."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._dispatcher = dispatcher

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.rejeitar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.rejeitar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        _despachar_pos_commit(self._dispatcher, ordem)
        return _ordem_dto(ordem)


class DecidirOrcamento:
    """Processa a decisao externa (aprovada/recusada) do orcamento corrente.

    RF-022 (ADR-021): compoe os casos de uso existentes em vez de duplicar
    regra — ``aprovada`` delega a ``AprovarOrcamento`` (espera inicial) ou
    ``AprovarOrcamentoComplementar`` (complementar pendente, espelhando o
    endpoint interno correspondente); ``recusada`` delega a
    ``CancelarOrdem`` com ``MOTIVO_RECUSA_EXTERNA`` (desistencia total,
    incluindo liberacao de reservas de estoque quando aplicavel).

    O guard de estado e indispensavel: ``CancelarOrdem`` aceita qualquer
    estado ativo, entao sem o guard uma recusa via canal externo
    cancelaria OS em ``RECEBIDA``/``EM_EXECUCAO``. A decisao externa so
    vale nos dois estados de espera de aprovacao.
    """

    _ESTADOS_DE_ESPERA: ClassVar[frozenset[StatusOrdem]] = frozenset(
        {
            StatusOrdem.AGUARDANDO_APROVACAO,
            StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
        }
    )

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        aprovar_orcamento: AprovarOrcamento,
        aprovar_complementar: AprovarOrcamentoComplementar,
        cancelar_ordem: CancelarOrdem,
    ) -> None:
        self._repo = repo
        self._aprovar_orcamento = aprovar_orcamento
        self._aprovar_complementar = aprovar_complementar
        self._cancelar_ordem = cancelar_ordem

    def executar(self, ordem_id: UUID, *, decisao: str) -> OrdemDeServicoDTO:
        """Aplica a decisao externa sobre o orcamento aguardando aprovacao.

        Raises:
            ValueError: decisao fora do vocabulario aprovada/recusada
                (o handler global converte em 422).
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: ordem fora dos estados de
                espera de aprovacao.
        """
        if decisao not in (DECISAO_APROVADA, DECISAO_RECUSADA):
            raise ValueError(
                f"decisao invalida: {decisao!r}; "
                f"use {DECISAO_APROVADA!r} ou {DECISAO_RECUSADA!r}"
            )
        # Leitura de GUARD sem lock (issue #82): aqui so checamos o estado de
        # espera; a transicao real (e o FOR UPDATE) acontece dentro do caso de
        # uso delegado abaixo, que re-le a ordem com_lock=True.
        ordem = _obter_ordem(self._repo, ordem_id)
        if ordem.status not in self._ESTADOS_DE_ESPERA:
            validos = sorted(s.value for s in self._ESTADOS_DE_ESPERA)
            raise TransicaoStatusInvalidaException(
                mensagem=(
                    f"Decisao externa de orcamento invalida em "
                    f"{ordem.status.value}; valida apenas em {validos}"
                )
            )
        if decisao == DECISAO_RECUSADA:
            return self._cancelar_ordem.executar(
                ordem_id, CancelarOrdemDTO(motivo=MOTIVO_RECUSA_EXTERNA)
            )
        if ordem.status is StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR:
            return self._aprovar_complementar.executar(ordem_id)
        return self._aprovar_orcamento.executar(ordem_id)


class ListarOrdens:
    """Listagem paginada de ordens em ``OrdemResumoDTO``."""

    def __init__(self, repo: OrdemDeServicoRepository) -> None:
        self._repo = repo

    def executar(
        self,
        offset: int = 0,
        limit: int = 20,
        *,
        incluir_encerradas: bool = False,
    ) -> list[OrdemResumoDTO]:
        """Pagina ordens por prioridade de status + antiguidade (RF-023).

        Default exclui estados encerrados (RN-019/RN-020);
        ``incluir_encerradas=True`` preserva a visao administrativa
        completa, com encerradas ao final da ordenacao.
        """
        ordens = self._repo.listar(
            offset=offset, limit=limit, incluir_encerradas=incluir_encerradas
        )
        return [_ordem_resumo(o) for o in ordens]

    def contar(self, *, incluir_encerradas: bool = False) -> int:
        """Total do universo listado (paginacao consistente com ``executar``)."""
        return self._repo.contar(incluir_encerradas=incluir_encerradas)


class ObterOrdem:
    """Projecao completa de uma ordem por id."""

    def __init__(self, repo: OrdemDeServicoRepository) -> None:
        self._repo = repo

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Retorna o DTO completo da ordem.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        return _ordem_dto(ordem)


class ConsultarAcompanhamento:
    """Consulta publica de acompanhamento por placa + documento (CPF/CNPJ)."""

    def __init__(self, repo: OrdemDeServicoRepository) -> None:
        self._repo = repo

    def executar(self, placa: str, documento: str) -> AcompanhamentoDTO | None:
        """Retorna a ordem mais recente para o par placa+documento, ou ``None``."""
        ordens = self._repo.obter_por_placa_e_documento(placa, documento)
        if not ordens:
            return None
        mais_recente = max(ordens, key=lambda o: o.criado_em)
        return AcompanhamentoDTO(
            status=mais_recente.status.value,
            criado_em=mais_recente.criado_em,
            atualizado_em=mais_recente.atualizado_em,
        )


class ObterMetricas:
    """Projecao de metricas agregadas: total, contagem por status, tempo medio."""

    def __init__(self, repo: OrdemDeServicoRepository) -> None:
        self._repo = repo

    def executar(self) -> MetricasDTO:
        """Calcula as metricas via repositorio; preenche zeros para status ausentes."""
        total = self._repo.contar()
        por_status = self._repo.contar_por_status()
        for s in StatusOrdem:
            if s.value not in por_status:
                por_status[s.value] = 0
        tempo_medio = self._repo.calcular_tempo_medio_execucao()
        return MetricasDTO(
            total=total,
            por_status=por_status,
            tempo_medio_execucao_minutos=tempo_medio,
        )
