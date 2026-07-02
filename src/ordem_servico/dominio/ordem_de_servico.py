"""Aggregate root ``OrdemDeServico``: invariantes, transicoes de estado e
eventos de dominio do contexto Ordem de Servico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from src.compartilhado.dominio.aggregate_root import AggregateRoot
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException
from src.ordem_servico.dominio.events import (
    DiagnosticoIniciadoEvent,
    EntregaRegistradaEvent,
    OrcamentoAprovadoEvent,
    OrcamentoComplementarAprovadoEvent,
    OrcamentoComplementarGeradoEvent,
    OrcamentoComplementarRejeitadoEvent,
    OrcamentoGeradoEvent,
    OrdemCanceladaEvent,
    OrdemCriadaEvent,
    ServicoFinalizadoEvent,
)
from src.ordem_servico.dominio.maquina_de_status import MaquinaDeStatus
from src.ordem_servico.dominio.orcamento import Orcamento
from src.ordem_servico.dominio.status import StatusOrdem

if TYPE_CHECKING:
    from uuid import UUID

    from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem

# Remocao de item: so antes do orcamento original ser aprovado -- preserva o
# escopo ja aprovado pelo cliente.
_ESTADOS_PERMITE_REMOCAO: Final[frozenset[StatusOrdem]] = frozenset(
    {StatusOrdem.RECEBIDA, StatusOrdem.EM_DIAGNOSTICO}
)
# Adicao de item: tambem em EM_EXECUCAO, para registrar trabalho extra detectado
# durante a execucao -> entra no orcamento complementar, reaprovado pelo cliente
# (#80 / RF-022). NAO se permite remocao em EM_EXECUCAO: itens ja aprovados nao
# saem do escopo sem reaprovacao.
_ESTADOS_PERMITE_ADICAO: Final[frozenset[StatusOrdem]] = _ESTADOS_PERMITE_REMOCAO | {
    StatusOrdem.EM_EXECUCAO
}
# MaquinaDeStatus e stateless (apenas le _TRANSICOES); compartilhar a
# instancia entre todos os agregados e seguro e evita realocacoes.
_maquina: Final[MaquinaDeStatus] = MaquinaDeStatus()


@dataclass(eq=False)
class OrdemDeServico(AggregateRoot):
    """Aggregate root do contexto Ordem de Servico.

    Mantem invariantes na construcao: ``cliente_id`` e ``veiculo_id``
    obrigatorios. As transicoes de estado sao governadas pela
    ``MaquinaDeStatus`` e cada uma emite um evento de dominio.
    Construir preferencialmente via ``OrdemDeServico.criar(...)``.
    """

    _cliente_id: UUID = field(default=None, repr=False)  # type: ignore[assignment]
    _veiculo_id: UUID = field(default=None, repr=False)  # type: ignore[assignment]
    _status: StatusOrdem = StatusOrdem.RECEBIDA
    _itens: list[ItemDaOrdem] = field(default_factory=list, repr=False)
    _orcamento: Orcamento | None = field(default=None, repr=False)
    # Escopo aprovado pelo cliente: snapshot congelado na ULTIMA aprovacao
    # (orcamento + ids dos itens cobertos). A rejeicao de um complementar
    # restaura este orcamento e remove os itens fora dele; ``finalizar_servico``
    # exige que todos os itens atuais estejam aqui (#111/#122). Persistidos
    # juntos na coluna JSONB ``escopo_aprovado_json`` (mapping). Ordens legadas
    # (pre-migracao) chegam sem snapshot -> ``None``/vazio preserva o
    # comportamento antigo.
    _orcamento_aprovado: Orcamento | None = field(default=None, repr=False)
    _itens_aprovados_ids: frozenset[UUID] = field(default_factory=frozenset, repr=False)
    _criado_em: datetime = field(default_factory=lambda: datetime.now(UTC), repr=False)
    _atualizado_em: datetime = field(
        default_factory=lambda: datetime.now(UTC), repr=False
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self._cliente_id is None:
            msg = "cliente_id e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if self._veiculo_id is None:
            msg = "veiculo_id e obrigatorio (recebido: None)"
            raise ValueError(msg)

    @property
    def cliente_id(self) -> UUID:
        return self._cliente_id

    @property
    def veiculo_id(self) -> UUID:
        return self._veiculo_id

    @property
    def status(self) -> StatusOrdem:
        return self._status

    @property
    def itens(self) -> tuple[ItemDaOrdem, ...]:
        """Vista imutavel dos itens; mutar via ``adicionar_item``/``remover_item``."""
        return tuple(self._itens)

    @property
    def orcamento(self) -> Orcamento | None:
        return self._orcamento

    @property
    def criado_em(self) -> datetime:
        return self._criado_em

    @property
    def atualizado_em(self) -> datetime:
        return self._atualizado_em

    @classmethod
    def criar(cls, cliente_id: UUID, veiculo_id: UUID) -> OrdemDeServico:
        """Factory: cria uma nova ordem em ``RECEBIDA`` e emite ``OrdemCriadaEvent``."""
        agora = datetime.now(UTC)
        ordem = cls(
            _cliente_id=cliente_id,
            _veiculo_id=veiculo_id,
            _status=StatusOrdem.RECEBIDA,
            _criado_em=agora,
            _atualizado_em=agora,
        )
        ordem._registrar_evento(
            OrdemCriadaEvent(
                agregado_id=ordem.id,
                cliente_id=cliente_id,
                veiculo_id=veiculo_id,
            )
        )
        return ordem

    def _marcar_atualizado(self) -> None:
        self._atualizado_em = datetime.now(UTC)

    def _validar_transicao(self, novo_status: StatusOrdem) -> None:
        """Valida a transicao SEM mutar o agregado.

        Usado pelas transicoes que precisam executar trabalho adicional
        (calcular orcamento, etc.) ANTES da mutacao do estado, para que
        ``TransicaoStatusInvalidaException`` continue sendo o erro
        primario quando o metodo for chamado em estado invalido.
        """
        _maquina.validar_transicao(self._status, novo_status)

    def _aplicar_transicao(self, novo_status: StatusOrdem) -> None:
        """Aplica a transicao previamente validada.

        Caller deve ter chamado ``_validar_transicao`` antes; este
        metodo nao revalida.
        """
        self._status = novo_status
        self._marcar_atualizado()

    def _transicionar(self, novo_status: StatusOrdem) -> None:
        """Conveniencia: valida e aplica a transicao em um unico passo."""
        self._validar_transicao(novo_status)
        self._aplicar_transicao(novo_status)

    def _validar_estado_para_itens(
        self, permitidos: frozenset[StatusOrdem], acao: str
    ) -> None:
        if self._status not in permitidos:
            estados = sorted(s.value for s in permitidos)
            raise ViolacaoRegraDeNegocioException(
                mensagem=(
                    f"Itens so podem ser {acao} nos estados {estados}; "
                    f"estado atual: {self._status.value}"
                )
            )

    def adicionar_item(self, item: ItemDaOrdem) -> None:
        """Adiciona um item; valido em RECEBIDA, EM_DIAGNOSTICO ou EM_EXECUCAO.

        Em EM_EXECUCAO o item e trabalho extra detectado na execucao e entra no
        orcamento complementar (#80); a reserva de estoque do item novo e feita
        pela camada de aplicacao (``AdicionarItem``).
        """
        if item is None:
            msg = "item e obrigatorio em adicionar_item (recebido: None)"
            raise ValueError(msg)
        self._validar_estado_para_itens(_ESTADOS_PERMITE_ADICAO, "adicionados")
        self._itens.append(item)
        self._marcar_atualizado()

    def remover_item(self, item_id: UUID) -> None:
        """Remove um item por id; valido apenas em RECEBIDA ou EM_DIAGNOSTICO.

        Itens ja aprovados (EM_EXECUCAO em diante) nao saem do escopo sem
        reaprovacao, entao a remocao continua restrita aos estados pre-orcamento.
        """
        if item_id is None:
            msg = "item_id e obrigatorio em remover_item (recebido: None)"
            raise ValueError(msg)
        self._validar_estado_para_itens(_ESTADOS_PERMITE_REMOCAO, "removidos")
        for i, item in enumerate(self._itens):
            if item.id == item_id:
                self._itens.pop(i)
                self._marcar_atualizado()
                return
        raise ViolacaoRegraDeNegocioException(
            mensagem=(f"Item {item_id} nao encontrado na ordem de servico {self.id}")
        )

    def iniciar_diagnostico(self) -> None:
        """RECEBIDA -> EM_DIAGNOSTICO; emite ``DiagnosticoIniciadoEvent``."""
        self._transicionar(StatusOrdem.EM_DIAGNOSTICO)
        self._registrar_evento(DiagnosticoIniciadoEvent(agregado_id=self.id))

    def gerar_orcamento(self) -> None:
        """EM_DIAGNOSTICO -> AGUARDANDO_APROVACAO; emite ``OrcamentoGeradoEvent``.

        Ordem de execucao:

        1. Valida a transicao SEM mutar (``TransicaoStatusInvalidaException``
           continua sendo o erro primario quando o metodo e chamado em
           estado invalido).
        2. Valida o invariante de negocio (pelo menos um item).
        3. Calcula o novo ``Orcamento`` (potencialmente caro; pode levantar
           ``ValueError`` em caso de inconsistencia).
        4. Aplica a transicao de estado.
        5. Atribui o orcamento.
        6. Registra o evento.

        Esta ordem garante que o agregado nunca entra em estado
        inconsistente, evita trabalho desnecessario em estados invalidos,
        e mantem a precedencia de erros previsivel.
        """
        self._validar_transicao(StatusOrdem.AGUARDANDO_APROVACAO)
        if not self._itens:
            raise ViolacaoRegraDeNegocioException(
                mensagem=(
                    f"Ordem {self.id} deve ter pelo menos um item para gerar orcamento"
                )
            )
        novo_orcamento = Orcamento.gerar(self._itens)
        self._aplicar_transicao(StatusOrdem.AGUARDANDO_APROVACAO)
        self._orcamento = novo_orcamento
        self._registrar_evento(OrcamentoGeradoEvent(agregado_id=self.id))

    def _snapshot_escopo_aprovado(self) -> None:
        """Congela o orcamento e os itens que o cliente acabou de aprovar.

        Chamado nas aprovacoes (inicial e complementar). A rejeicao de um
        complementar futuro restaura este orcamento e remove os itens fora do
        conjunto aprovado; ``finalizar_servico`` exige cobertura total (#111/
        #122). No momento da aprovacao ``_orcamento`` ja e o valor aprovado e
        ``_itens`` sao exatamente os itens cobertos.
        """
        self._orcamento_aprovado = self._orcamento
        self._itens_aprovados_ids = frozenset(item.id for item in self._itens)

    def aprovar_orcamento(self) -> None:
        """AGUARDANDO_APROVACAO -> EM_EXECUCAO; emite ``OrcamentoAprovadoEvent``."""
        self._transicionar(StatusOrdem.EM_EXECUCAO)
        self._snapshot_escopo_aprovado()
        self._registrar_evento(OrcamentoAprovadoEvent(agregado_id=self.id))

    def finalizar_servico(self) -> None:
        """EM_EXECUCAO -> FINALIZADA; emite ``ServicoFinalizadoEvent``.

        Guard (#122): nao finaliza se houver itens fora do escopo aprovado —
        itens adicionados em EM_EXECUCAO sem gerar/aprovar o orcamento
        complementar. Sem isso a OS finalizaria (e entregaria) cobrando
        trabalho que o cliente nao aprovou. Ordens legadas (sem snapshot)
        mantem o comportamento antigo.
        """
        self._validar_transicao(StatusOrdem.FINALIZADA)
        ids_atuais = {item.id for item in self._itens}
        if self._itens_aprovados_ids and not ids_atuais <= self._itens_aprovados_ids:
            raise ViolacaoRegraDeNegocioException(
                mensagem=(
                    f"Ordem {self.id} tem itens fora do orcamento aprovado; "
                    f"gere e aprove o orcamento complementar antes de finalizar"
                )
            )
        self._aplicar_transicao(StatusOrdem.FINALIZADA)
        self._registrar_evento(ServicoFinalizadoEvent(agregado_id=self.id))

    def registrar_entrega(self) -> None:
        """FINALIZADA -> ENTREGUE; emite ``EntregaRegistradaEvent``."""
        self._transicionar(StatusOrdem.ENTREGUE)
        self._registrar_evento(EntregaRegistradaEvent(agregado_id=self.id))

    def cancelar(self, motivo: str) -> None:
        """Qualquer estado nao terminal -> CANCELADA; emite ``OrdemCanceladaEvent``.

        Levanta ``ViolacaoRegraDeNegocioException`` se ``motivo`` for vazio
        ou somente espacos: cancelamento sem motivo e anti-padrao de dominio.
        """
        if not motivo or not motivo.strip():
            raise ViolacaoRegraDeNegocioException(
                mensagem="motivo de cancelamento e obrigatorio (recebido vazio)"
            )
        self._transicionar(StatusOrdem.CANCELADA)
        self._registrar_evento(OrdemCanceladaEvent(agregado_id=self.id, motivo=motivo))

    def gerar_orcamento_complementar(self) -> None:
        """EM_EXECUCAO -> AGUARDANDO_APROVACAO_COMPLEMENTAR; emite o evento.

        Mesma ordem de execucao de ``gerar_orcamento``: validar transicao
        (sem mutar) -> validar items -> calcular orcamento -> aplicar
        transicao -> atribuir orcamento -> emitir evento.
        """
        self._validar_transicao(StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR)
        if not self._itens:
            raise ViolacaoRegraDeNegocioException(
                mensagem=(
                    f"Ordem {self.id} deve ter pelo menos um item "
                    f"para gerar orcamento complementar"
                )
            )
        novo_orcamento = Orcamento.gerar(self._itens)
        self._aplicar_transicao(StatusOrdem.AGUARDANDO_APROVACAO_COMPLEMENTAR)
        self._orcamento = novo_orcamento
        self._registrar_evento(OrcamentoComplementarGeradoEvent(agregado_id=self.id))

    def aprovar_orcamento_complementar(self) -> None:
        """AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO; emite o evento.

        Promove o complementar a escopo aprovado: o orcamento corrente (o
        complementar) e os itens atuais passam a ser o snapshot restaurado por
        uma eventual rejeicao futura.
        """
        self._transicionar(StatusOrdem.EM_EXECUCAO)
        self._snapshot_escopo_aprovado()
        self._registrar_evento(OrcamentoComplementarAprovadoEvent(agregado_id=self.id))

    def rejeitar_orcamento_complementar(self) -> tuple[ItemDaOrdem, ...]:
        """AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO, revertendo o escopo.

        Restaura o orcamento aprovado e REMOVE os itens adicionados apos a
        ultima aprovacao (fora de ``_itens_aprovados_ids``), retornando-os para
        que a camada de aplicacao libere as reservas de estoque. Sem isso a OS
        seguiria com o orcamento inflado e itens/reservas do trabalho que o
        cliente recusou (#111). Ordens legadas (sem snapshot) so transicionam.
        """
        self._validar_transicao(StatusOrdem.EM_EXECUCAO)
        if not self._itens_aprovados_ids:
            # Ordem legada (pre-migracao): sem snapshot nao ha como classificar
            # itens aprovados; preserva o comportamento antigo (so transiciona).
            self._aplicar_transicao(StatusOrdem.EM_EXECUCAO)
            self._registrar_evento(
                OrcamentoComplementarRejeitadoEvent(agregado_id=self.id)
            )
            return ()
        removidos = tuple(
            item for item in self._itens if item.id not in self._itens_aprovados_ids
        )
        self._itens = [
            item for item in self._itens if item.id in self._itens_aprovados_ids
        ]
        self._orcamento = self._orcamento_aprovado
        self._aplicar_transicao(StatusOrdem.EM_EXECUCAO)
        self._registrar_evento(OrcamentoComplementarRejeitadoEvent(agregado_id=self.id))
        return removidos
