"""Casos de uso da aplicacao Ordem de Servico.

Cada classe expoe um unico metodo ``executar(...)`` que orquestra o
repositorio, o ``UnitOfWork`` e, quando aplicavel, as portas para outros
bounded contexts (``EstoquePort``, ``CatalogoPort``, ``ClientePort``).
As regras de negocio ficam no agregado ``OrdemDeServico``; os casos de
uso apenas compoem a sequencia de operacoes, mapeiam entrada/saida para
DTOs e garantem a fronteira transacional via ``with self._uow:``.

Eventos (RF-024 via RF-018/TD-008): as transicoes registram eventos no
agregado e a ``UnitOfWork`` enfileira os ``IntegrationEvent`` na outbox
no MESMO commit da transicao; o relay (``python -m relay``) entrega as
notificacoes de forma duravel. Os casos de uso nao publicam nada
diretamente. ``CriarOrdem`` nao notifica por desenho: criacao nao e
atualizacao de status.
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
from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
from src.ordem_servico.dominio.status import StatusOrdem

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from uuid import UUID

    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork
    from src.ordem_servico.aplicacao.dtos import CriarOrdemDTO
    from src.ordem_servico.aplicacao.ports import (
        CatalogoPort,
        ClientePort,
        EstoquePort,
    )
    from src.ordem_servico.dominio.orcamento import Orcamento
    from src.ordem_servico.dominio.repository import OrdemDeServicoRepository

# Vocabulario do canal externo de decisao de orcamento (RF-022 / ADR-021).
# O schema HTTP restringe via Literal; o caso de uso revalida (defesa em
# profundidade) e usa o motivo fixo na recusa via CancelarOrdem.
DECISAO_APROVADA = "aprovada"
DECISAO_RECUSADA = "recusada"
MOTIVO_RECUSA_EXTERNA = "orcamento recusado pelo cliente"


def _item_dto(item: ItemDaOrdem) -> ItemDaOrdemDTO:
    """Projeta um ``ItemDaOrdem`` para ``ItemDaOrdemDTO``."""
    return ItemDaOrdemDTO(
        id=item.id,
        servico_catalogo_id=item.servico_catalogo_id,
        item_estoque_id=item.item_estoque_id,
        descricao=item.descricao,
        quantidade=item.quantidade,
        preco_unitario_centavos=item.preco_unitario.em_centavos,
        subtotal_centavos=item.subtotal.em_centavos,
    )


def _orcamento_dto(orc: Orcamento | None) -> OrcamentoDTO | None:
    """Projeta ``Orcamento`` para ``OrcamentoDTO``, ou ``None``."""
    if orc is None:
        return None
    linhas = tuple(
        LinhaOrcamentoDTO(
            descricao=linha.descricao,
            quantidade=linha.quantidade,
            preco_unitario_centavos=linha.preco_unitario.em_centavos,
            subtotal_centavos=linha.subtotal.em_centavos,
        )
        for linha in orc.itens
    )
    return OrcamentoDTO(
        total_centavos=orc.total.em_centavos,
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
        itens=tuple(_item_dto(i) for i in os.itens),
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
        raise OrdemNaoEncontradaException(ordem_id)
    return ordem


def _reservas_de_itens_ordenadas(
    itens: Iterable[ItemDaOrdem],
) -> list[tuple[UUID, int]]:
    """``(item_estoque_id, quantidade)`` das pecas, em ordem de ``id``.

    Reserva/liberacao de varios itens numa transacao deve adquirir os locks
    pessimistas (``FOR UPDATE``) sempre na MESMA ordem global de id (issue
    #83). Sem isso, duas aprovacoes que tocam os mesmos itens em ordens
    de insercao diferentes poderiam cruzar locks e deadlockar. Itens de mao
    de obra (``item_estoque_id is None``) ficam de fora — nao reservam; o
    filtro tambem estreita o tipo para ``UUID`` (nao ``UUID | None``).
    """
    pares = [
        (item.item_estoque_id, item.quantidade)
        for item in itens
        if item.item_estoque_id is not None
    ]
    return sorted(pares, key=lambda par: par[0])


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
    # IDs no texto do erro (UUID, nao-PII): num CriarOrdem multi-linha (RF-020)
    # varias linhas falham do mesmo jeito — sem o id ofensor e impossivel saber
    # QUAL servico/peca quebrou.
    servico = catalogo_port.obter_servico(dto.servico_catalogo_id)
    if servico is None:
        raise ViolacaoRegraDeNegocioException(
            mensagem=f"Servico {dto.servico_catalogo_id} nao encontrado no catalogo"
        )
    if not servico.ativo:
        raise ViolacaoRegraDeNegocioException(
            mensagem=f"Servico {dto.servico_catalogo_id} inativo"
        )

    if dto.item_estoque_id is not None:
        peca = estoque_port.obter_item(dto.item_estoque_id)
        if peca is None:
            raise ViolacaoRegraDeNegocioException(
                mensagem=f"Item de estoque {dto.item_estoque_id} nao encontrado"
            )
        # Peca desativada nao entra em OS nova (issue #120): espelha a rejeicao
        # de servico inativo acima e fecha a brecha do guard de
        # DesativarItemEstoque (que so impede desativar item COM OS ativa).
        if not peca.ativo:
            raise ViolacaoRegraDeNegocioException(
                mensagem=f"Item de estoque {dto.item_estoque_id} inativo"
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

    return ItemDaOrdem.criar(
        servico_catalogo_id=dto.servico_catalogo_id,
        item_estoque_id=dto.item_estoque_id,
        descricao=descricao,
        quantidade=dto.quantidade,
        preco_unitario=preco_unitario,
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
        if not self._cliente_port.cliente_existe(dto.cliente_id):
            raise ClienteNaoEncontradoException(dto.cliente_id)
        if not self._cliente_port.veiculo_pertence_ao_cliente(
            dto.cliente_id,
            dto.veiculo_id,
        ):
            raise VeiculoNaoEncontradoException(dto.veiculo_id)
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

        Ordem custo-gradiente: o guard de estado (``validar_pode_adicionar_item``)
        roda ANTES de consultar catalogo/estoque em ``_montar_item`` — adicionar
        item em estado que nao permite (ex.: FINALIZADA) falha com o erro CERTO
        sem tocar os ports vizinhos.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            ViolacaoRegraDeNegocioException: estado invalido para adicao,
                servico inativo, servico/peca inexistente.
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        ordem.validar_pode_adicionar_item()
        item = _montar_item(self._catalogo_port, self._estoque_port, dto)
        ordem.adicionar_item(item)
        with self._uow:
            # Em EM_EXECUCAO o item e trabalho extra (orcamento complementar,
            # #80): reserva o estoque na hora. Os itens do orcamento original ja
            # foram reservados na aprovacao -> reservar so o novo evita dupla
            # reserva. A OS ja esta travada (com_lock), preservando a ordem de
            # lock OS -> Estoque (anti-deadlock, #82/#83).
            if (
                ordem.status == StatusOrdem.EM_EXECUCAO
                and item.item_estoque_id is not None
            ):
                self._estoque_port.reservar(item.item_estoque_id, item.quantidade)
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


class TransitarStatus:
    """Caso de uso generico de transicao de status sem orquestracao extra.

    Carrega a ordem sob lock pessimista, delega a ``transicao`` do agregado
    (que valida a maquina de status, aplica invariantes e emite o evento
    correspondente) e persiste na fronteira da UnitOfWork. As seis transicoes
    puras sao subclasses finas que so fixam o unbound method (ex.:
    ``OrdemDeServico.iniciar_diagnostico``) — type-safe: um metodo inexistente
    ou de assinatura errada e erro de tipo em vez de ``AttributeError`` em
    runtime. Transicoes que orquestram estoque (``AprovarOrcamento``,
    ``CancelarOrdem``, ``RejeitarOrcamentoComplementar``) tem casos de uso
    proprios.
    """

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        transicao: Callable[[OrdemDeServico], None],
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._transicao = transicao

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao metodo de transicao do agregado e commita.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual nao permite a
                transicao.
            ViolacaoRegraDeNegocioException: invariante do metodo delegado
                violada (ex.: gerar orcamento sem itens).
        """
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        self._transicao(ordem)
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class IniciarDiagnostico(TransitarStatus):
    """Transita a ordem para EM_DIAGNOSTICO (emite ``DiagnosticoIniciadoEvent``)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(repo, uow, transicao=OrdemDeServico.iniciar_diagnostico)


class GerarOrcamento(TransitarStatus):
    """Gera o ``Orcamento`` a partir dos itens e transita para AGUARDANDO_APROVACAO.

    O calculo e a exigencia de pelo menos um item sao do agregado
    (``OrdemDeServico.gerar_orcamento``).
    """

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(repo, uow, transicao=OrdemDeServico.gerar_orcamento)


class AprovarOrcamento:
    """Aprova o orcamento, reserva itens no estoque e transita para EM_EXECUCAO."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        estoque_port: EstoquePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._estoque_port = estoque_port

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Aprova o orcamento (valida status) e ENTAO reserva o estoque.

        Ordem custo-gradiente: ``aprovar_orcamento`` (validacao in-memory da
        maquina de status, que tambem congela o escopo aprovado) roda ANTES do
        loop de reserva. Uma dupla-aprovacao / estado invalido falha com o erro
        CERTO (``TransicaoStatusInvalidaException``) sem tocar o estoque — antes,
        a reserva acontecia primeiro e uma 2a aprovacao reservava de novo antes
        de a maquina rejeitar. ``aprovar_orcamento`` nao depende de nada
        reservado (so transiciona + snapshota ids ja no agregado), entao pode
        preceder a reserva com seguranca. Tudo dentro da UoW: se a reserva ou o
        ``salvar`` falharem, a transicao e revertida no rollback da sessao.

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
            # Valida o status ANTES de reservar (custo-gradiente): estado
            # invalido/duplo-aprovar aborta sem tocar o estoque.
            ordem.aprovar_orcamento()
            # Ordem determinista de id ao reservar varios itens (anti-deadlock).
            for item_estoque_id, quantidade in _reservas_de_itens_ordenadas(
                ordem.itens
            ):
                self._estoque_port.reservar(item_estoque_id, quantidade)
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class FinalizarServico(TransitarStatus):
    """Transita a ordem para FINALIZADA (emite ``ServicoFinalizadoEvent``).

    O guard de escopo aprovado (#122) e do agregado
    (``OrdemDeServico.finalizar_servico``).
    """

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(repo, uow, transicao=OrdemDeServico.finalizar_servico)


class RegistrarEntrega(TransitarStatus):
    """Transita a ordem para ENTREGUE (emite ``EntregaRegistradaEvent``)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(repo, uow, transicao=OrdemDeServico.registrar_entrega)


class CancelarOrdem:
    """Cancela a ordem e libera reservas de estoque ativas (se houver)."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        estoque_port: EstoquePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._estoque_port = estoque_port

    def executar(self, ordem_id: UUID, dto: CancelarOrdemDTO) -> OrdemDeServicoDTO:
        """Delega ao agregado ``cancelar`` e ENTAO libera reservas (se aplicavel).

        Ordem custo-gradiente: ``cancelar`` (valida a transicao pela maquina de
        status E o motivo, in-memory) roda ANTES da liberacao de estoque. Um
        cancelamento invalido (estado terminal) ou motivo vazio falha com o erro
        CERTO sem tocar o estoque — antes, a liberacao acontecia primeiro e um
        cancelamento invalido soltava reservas indevidamente. A decisao de
        liberar usa o ``status_anterior`` (capturado ANTES do cancelamento, que
        muta o status para CANCELADA): so EM_EXECUCAO / AGUARDANDO_APROVACAO_
        COMPLEMENTAR tinham reservas ativas. Liberacao + cancelamento
        compartilham o escopo transacional via ``with self._uow:`` — se a
        liberacao falhar, o cancelamento e revertido no rollback da sessao.
        Retorna o DTO completo da ordem ja cancelada para consistencia com os
        outros casos de uso de escrita.

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
        # status_anterior antes de cancelar() mutar para CANCELADA: so os
        # estados com reserva ativa liberam estoque.
        status_anterior = ordem.status
        with self._uow:
            # Valida transicao + motivo ANTES de liberar (custo-gradiente):
            # cancelamento invalido/motivo vazio aborta sem tocar o estoque.
            ordem.cancelar(dto.motivo)
            if status_anterior in {
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
            }:
                # Ordem determinista de id ao liberar (anti-deadlock, igual
                # ao caminho de reserva de AprovarOrcamento).
                for item_estoque_id, quantidade in _reservas_de_itens_ordenadas(
                    ordem.itens
                ):
                    self._estoque_port.liberar(item_estoque_id, quantidade)
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class GerarOrcamentoComplementar(TransitarStatus):
    """Gera um orcamento complementar a partir dos itens adicionais."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(
            repo, uow, transicao=OrdemDeServico.gerar_orcamento_complementar
        )


class AprovarOrcamentoComplementar(TransitarStatus):
    """Aprova o orcamento complementar, retornando a ordem a EM_EXECUCAO.

    Sem reserva de estoque aqui: os itens extras ja foram reservados no
    ``AdicionarItem`` em EM_EXECUCAO (#80).
    """

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        super().__init__(
            repo, uow, transicao=OrdemDeServico.aprovar_orcamento_complementar
        )


class RejeitarOrcamentoComplementar:
    """Rejeita o orcamento complementar: reverte o escopo e libera reservas."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        estoque_port: EstoquePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._estoque_port = estoque_port

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado e LIBERA as reservas dos itens revertidos (#111).

        ``rejeitar_orcamento_complementar`` remove do agregado os itens
        adicionados apos a ultima aprovacao (e restaura o orcamento aprovado),
        retornando-os; aqui liberamos as reservas de estoque desses itens na
        MESMA transacao (atomico com o save). As reservas sao calculadas ANTES
        do save (que deleta os itens via cascade) e liberadas em ordem de id
        (anti-deadlock, igual a AprovarOrcamento/CancelarOrdem).

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            EntidadeNaoEncontradaException: item de estoque inexistente.
        """
        # com_lock=True: OS travada antes do Estoque (ordem global de locks),
        # retido ate o commit da UoW.
        ordem = _obter_ordem(self._repo, ordem_id, com_lock=True)
        itens_removidos = ordem.rejeitar_orcamento_complementar()
        reservas = _reservas_de_itens_ordenadas(itens_removidos)
        with self._uow:
            self._repo.salvar(ordem)
            for item_estoque_id, quantidade in reservas:
                self._estoque_port.liberar(item_estoque_id, quantidade)
            self._uow.commit()
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

    def _exigir_estado_de_espera(self, ordem: OrdemDeServico) -> None:
        """Levanta ``TransicaoStatusInvalidaException`` fora da espera de aprovacao."""
        if ordem.status not in self._ESTADOS_DE_ESPERA:
            validos = sorted(s.value for s in self._ESTADOS_DE_ESPERA)
            raise TransicaoStatusInvalidaException(
                mensagem=(
                    f"Decisao externa de orcamento invalida em "
                    f"{ordem.status.value}; valida apenas em {validos}"
                )
            )

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
        self._exigir_estado_de_espera(ordem)
        if decisao == DECISAO_RECUSADA:
            # Revalida o estado de espera SOB LOCK (#119): o guard acima le sem
            # lock e ``CancelarOrdem`` (delegado) aceita QUALQUER estado ativo
            # sem revalidar a espera. Sem esta releitura travada, uma aprovacao
            # interna concorrente (AGUARDANDO_APROVACAO -> EM_EXECUCAO) entre o
            # guard e o cancelamento faria a recusa externa cancelar uma OS ja
            # em execucao. A session e compartilhada (composition root), entao o
            # FOR UPDATE adquirido aqui e retido ate o commit da UoW de
            # CancelarOrdem — a mesma transacao.
            ordem_travada = _obter_ordem(self._repo, ordem_id, com_lock=True)
            self._exigir_estado_de_espera(ordem_travada)
            return self._cancelar_ordem.executar(
                ordem_id, CancelarOrdemDTO(motivo=MOTIVO_RECUSA_EXTERNA)
            )
        # Roteamento aprova↔complementar por status lido SEM lock (best-effort,
        # Copilot #142): se o estado mudar de forma concorrente entre o guard e
        # aqui, o delegado escolhido pode ser o "errado", mas NAO ha corrupcao —
        # cada aprovacao delegada re-le a ordem com_lock=True e a maquina de
        # status rejeita a transicao ilegal (TransicaoStatusInvalidaException).
        # A autoridade final e a revalidacao sob lock do delegado, nao este
        # roteamento. (O caminho 'recusada' acima precisa da revalidacao
        # explicita porque CancelarOrdem aceita qualquer estado ativo.)
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
        """Retorna a ordem mais recente para o par placa+documento, ou ``None``.

        A escolha da mais recente e do repositorio (``ORDER BY criado_em
        DESC LIMIT 1``): a consulta publica nao hidrata o historico
        completo do par.
        """
        ordem = self._repo.obter_mais_recente_por_placa_e_documento(placa, documento)
        if ordem is None:
            return None
        return AcompanhamentoDTO(
            status=ordem.status.value,
            criado_em=ordem.criado_em,
            atualizado_em=ordem.atualizado_em,
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
