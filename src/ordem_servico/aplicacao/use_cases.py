"""Casos de uso da aplicacao Ordem de Servico.

Cada classe expoe um unico metodo ``executar(...)`` que orquestra o
repositorio, o ``UnitOfWork`` e, quando aplicavel, as portas para outros
bounded contexts (``EstoquePort``, ``CatalogoPort``, ``ClientePort``).
As regras de negocio ficam no agregado ``OrdemDeServico``; os casos de
uso apenas compoem a sequencia de operacoes, mapeiam entrada/saida para
DTOs e garantem a fronteira transacional via ``with self._uow:``.

Event dispatch (publicacao de eventos de dominio a partir de
``ordem.coletar_eventos()``) esta DEFERIDO para a PR 13 (wiring final do
app e event bus); ate la, os eventos se acumulam em
``_eventos_pendentes`` e sao mantidos junto com a instancia na sessao.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException
from src.ordem_servico.aplicacao.dtos import (
    AcompanhamentoDTO,
    ItemDaOrdemDTO,
    LinhaOrcamentoDTO,
    MetricasDTO,
    OrcamentoDTO,
    OrdemDeServicoDTO,
    OrdemResumoDTO,
)
from src.ordem_servico.dominio.exceptions import OrdemNaoEncontradaException
from src.ordem_servico.dominio.status import StatusOrdem

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork
    from src.compartilhado.dominio.dinheiro import Dinheiro
    from src.ordem_servico.aplicacao.dtos import (
        AdicionarItemDTO,
        CancelarOrdemDTO,
        CriarOrdemDTO,
    )
    from src.ordem_servico.aplicacao.ports import (
        CatalogoPort,
        ClientePort,
        EstoquePort,
    )
    from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem
    from src.ordem_servico.dominio.orcamento import Orcamento
    from src.ordem_servico.dominio.ordem_de_servico import OrdemDeServico
    from src.ordem_servico.dominio.repository import OrdemDeServicoRepository


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


def _obter_ordem(repo: OrdemDeServicoRepository, ordem_id: UUID) -> OrdemDeServico:
    """Busca a ordem ou levanta ``OrdemNaoEncontradaException``."""
    ordem = repo.obter_por_id(ordem_id)
    if ordem is None:
        raise OrdemNaoEncontradaException()
    return ordem


class CriarOrdem:
    """Cria uma nova ``OrdemDeServico`` apos validar cliente e veiculo."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        cliente_port: ClientePort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._cliente_port = cliente_port

    def executar(self, dto: CriarOrdemDTO) -> OrdemDeServicoDTO:
        """Valida cliente + veiculo via ``ClientePort`` e persiste na UoW.

        Raises:
            ViolacaoRegraDeNegocioException: cliente ou veiculo inexistente.
        """
        from src.ordem_servico.dominio.ordem_de_servico import (
            OrdemDeServico,
        )

        if not self._cliente_port.cliente_existe(dto.cliente_id):
            raise ViolacaoRegraDeNegocioException(mensagem="Cliente nao encontrado")
        if not self._cliente_port.veiculo_existe(dto.veiculo_id):
            raise ViolacaoRegraDeNegocioException(mensagem="Veiculo nao encontrado")
        ordem = OrdemDeServico.criar(
            cliente_id=dto.cliente_id, veiculo_id=dto.veiculo_id
        )
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class AdicionarItem:
    """Adiciona um item a uma ordem; consulta preco e status via ``CatalogoPort``."""

    def __init__(
        self,
        repo: OrdemDeServicoRepository,
        uow: UnitOfWork,
        catalogo_port: CatalogoPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._catalogo_port = catalogo_port

    def executar(self, ordem_id: UUID, dto: AdicionarItemDTO) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.adicionar_item``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            ViolacaoRegraDeNegocioException: servico inexistente ou inativo.
        """
        from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem

        ordem = _obter_ordem(self._repo, ordem_id)
        servico = self._catalogo_port.obter_servico(dto.servico_catalogo_id)
        if servico is None:
            raise ViolacaoRegraDeNegocioException(
                mensagem="Servico nao encontrado no catalogo"
            )
        if not servico.ativo:
            raise ViolacaoRegraDeNegocioException(mensagem="Servico inativo")
        item = ItemDaOrdem(
            _servico_catalogo_id=dto.servico_catalogo_id,
            _item_estoque_id=dto.item_estoque_id,
            _descricao=dto.descricao,
            _quantidade=dto.quantidade,
            _preco_unitario=servico.preco,
        )
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
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.remover_item(item_id)
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class IniciarDiagnostico:
    """Transita a ordem para EM_DIAGNOSTICO (emite ``DiagnosticoIniciadoEvent``)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.iniciar_diagnostico``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual nao permite iniciar.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.iniciar_diagnostico()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class GerarOrcamento:
    """Gera o ``Orcamento`` a partir dos itens e transita para AGUARDANDO_APROVACAO."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.gerar_orcamento``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            ViolacaoRegraDeNegocioException: ordem sem itens.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.gerar_orcamento()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


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
        """Reserva estoque e delega ao agregado ``OrdemDeServico.aprovar_orcamento``.

        A reserva acontece DENTRO da UoW, antes da transicao: se a
        transicao ou o ``salvar`` falharem, a reserva e revertida via
        rollback da sessao compartilhada.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            EntidadeNaoEncontradaException: item de estoque inexistente.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        with self._uow:
            for item in ordem.itens:
                if item.item_estoque_id is not None:
                    self._estoque_port.reservar(item.item_estoque_id, item.quantidade)
            ordem.aprovar_orcamento()
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class FinalizarServico:
    """Transita a ordem para FINALIZADA (emite ``ServicoFinalizadoEvent``)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.finalizar_servico``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.finalizar_servico()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class RegistrarEntrega:
    """Transita a ordem para ENTREGUE (emite ``EntregaRegistradaEvent``)."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.registrar_entrega``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.registrar_entrega()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


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
        ordem = _obter_ordem(self._repo, ordem_id)
        # Liberacao de reservas e cancelamento devem compartilhar o mesmo
        # escopo transacional (consistencia com AprovarOrcamento): se o
        # cancelamento falhar apos a liberacao, a UoW faz rollback das
        # duas mudancas atomicamente.
        with self._uow:
            if ordem.status in {
                StatusOrdem.EM_EXECUCAO,
                StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR,
            }:
                for item in ordem.itens:
                    if item.item_estoque_id is not None:
                        self._estoque_port.liberar(
                            item.item_estoque_id, item.quantidade
                        )
            ordem.cancelar(dto.motivo)
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class GerarOrcamentoComplementar:
    """Gera um orcamento complementar a partir dos itens adicionais."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.gerar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
            ViolacaoRegraDeNegocioException: ordem sem itens.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.gerar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class AprovarOrcamentoComplementar:
    """Aprova o orcamento complementar, retornando a ordem a EM_EXECUCAO."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.aprovar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.aprovar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class RejeitarOrcamentoComplementar:
    """Rejeita o orcamento complementar, retornando a ordem a EM_EXECUCAO."""

    def __init__(self, repo: OrdemDeServicoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, ordem_id: UUID) -> OrdemDeServicoDTO:
        """Delega ao agregado ``OrdemDeServico.rejeitar_orcamento_complementar``.

        Raises:
            OrdemNaoEncontradaException: ordem inexistente.
            TransicaoStatusInvalidaException: status atual invalido.
        """
        ordem = _obter_ordem(self._repo, ordem_id)
        ordem.rejeitar_orcamento_complementar()
        with self._uow:
            self._repo.salvar(ordem)
            self._uow.commit()
        return _ordem_dto(ordem)


class ListarOrdens:
    """Listagem paginada de ordens em ``OrdemResumoDTO``."""

    def __init__(self, repo: OrdemDeServicoRepository) -> None:
        self._repo = repo

    def executar(self, offset: int = 0, limit: int = 20) -> list[OrdemResumoDTO]:
        """Pagina ordens em ordem deterministica (criado_em DESC, id)."""
        ordens = self._repo.listar(offset=offset, limit=limit)
        return [_ordem_resumo(o) for o in ordens]

    def contar(self) -> int:
        """Total de ordens persistidas (usado para paginacao junto com ``executar``)."""
        return self._repo.contar()


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
