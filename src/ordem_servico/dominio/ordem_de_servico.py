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

# Itens so podem ser adicionados/removidos antes do orcamento ser gerado.
_ESTADOS_PERMITE_ITENS: Final[frozenset[StatusOrdem]] = frozenset(
    {StatusOrdem.RECEBIDA, StatusOrdem.EM_DIAGNOSTICO}
)
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

    def _validar_modificacao_itens(self) -> None:
        if self._status not in _ESTADOS_PERMITE_ITENS:
            permitidos = sorted(s.value for s in _ESTADOS_PERMITE_ITENS)
            raise ViolacaoRegraDeNegocioException(
                mensagem=(
                    f"Itens so podem ser modificados nos estados {permitidos}; "
                    f"estado atual: {self._status.value}"
                )
            )

    def adicionar_item(self, item: ItemDaOrdem) -> None:
        """Adiciona um item; valido apenas em RECEBIDA ou EM_DIAGNOSTICO."""
        if item is None:
            msg = "item e obrigatorio em adicionar_item (recebido: None)"
            raise ValueError(msg)
        self._validar_modificacao_itens()
        self._itens.append(item)
        self._marcar_atualizado()

    def remover_item(self, item_id: UUID) -> None:
        """Remove um item por id; valido apenas em RECEBIDA ou EM_DIAGNOSTICO."""
        if item_id is None:
            msg = "item_id e obrigatorio em remover_item (recebido: None)"
            raise ValueError(msg)
        self._validar_modificacao_itens()
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

    def aprovar_orcamento(self) -> None:
        """AGUARDANDO_APROVACAO -> EM_EXECUCAO; emite ``OrcamentoAprovadoEvent``."""
        self._transicionar(StatusOrdem.EM_EXECUCAO)
        self._registrar_evento(OrcamentoAprovadoEvent(agregado_id=self.id))

    def finalizar_servico(self) -> None:
        """EM_EXECUCAO -> FINALIZADA; emite ``ServicoFinalizadoEvent``."""
        self._transicionar(StatusOrdem.FINALIZADA)
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
        """AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO; emite o evento."""
        self._transicionar(StatusOrdem.EM_EXECUCAO)
        self._registrar_evento(OrcamentoComplementarAprovadoEvent(agregado_id=self.id))

    def rejeitar_orcamento_complementar(self) -> None:
        """AGUARDANDO_APROVACAO_COMPLEMENTAR -> EM_EXECUCAO; emite o evento."""
        self._transicionar(StatusOrdem.EM_EXECUCAO)
        self._registrar_evento(OrcamentoComplementarRejeitadoEvent(agregado_id=self.id))
