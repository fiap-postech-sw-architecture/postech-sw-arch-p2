from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.compartilhado.dominio.aggregate_root import AggregateRoot
from src.compartilhado.dominio.exceptions import EstoqueInsuficienteException
from src.estoque.dominio.events import EstoqueLiberadoEvent, EstoqueReservadoEvent

if TYPE_CHECKING:
    from src.compartilhado.dominio.dinheiro import Dinheiro


def _validar_nome(nome: str) -> None:
    if not nome:
        msg = f"Nome do item nao pode ser vazio (recebido: {nome!r})"
        raise ValueError(msg)


def _validar_quantidade_nao_negativa(quantidade: int) -> None:
    if quantidade < 0:
        msg = f"Quantidade nao pode ser negativa (recebido: {quantidade})"
        raise ValueError(msg)


def _validar_preco_obrigatorio(preco: Dinheiro | None) -> None:
    if preco is None:
        msg = "Preco unitario do item e obrigatorio"
        raise ValueError(msg)


@dataclass(eq=False)
class ItemEstoque(AggregateRoot):
    """Aggregate root do contexto Estoque.

    Representa um item em estoque (pecas, fluidos, etc.) com rastreamento
    de quantidade, reservas e emissao de eventos de dominio a cada
    reserva/liberacao. Invariantes verificados na construcao e revalidados
    nos metodos que alteram estado:

    - ``nome`` nao vazio
    - ``quantidade`` >= 0
    - ``preco_unitario`` obrigatorio (``Dinheiro`` nao nulo)
    """

    _nome: str = ""
    _descricao: str = ""
    _quantidade: int = 0
    # Default None; reidratado pelo listener ``load`` do mapper.
    _preco_unitario: Dinheiro = None  # type: ignore[assignment]
    _ativo: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        _validar_nome(self._nome)
        _validar_quantidade_nao_negativa(self._quantidade)
        _validar_preco_obrigatorio(self._preco_unitario)

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def descricao(self) -> str:
        return self._descricao

    @property
    def quantidade(self) -> int:
        return self._quantidade

    @property
    def preco_unitario(self) -> Dinheiro:
        return self._preco_unitario

    @property
    def ativo(self) -> bool:
        return self._ativo

    def reservar(self, quantidade: int) -> None:
        """Reserva ``quantidade`` unidades do estoque.

        Pre-condicoes: ``quantidade > 0`` e ``self.quantidade >= quantidade``.
        Emite ``EstoqueReservadoEvent`` apos a reserva.
        Levanta ``ValueError`` se ``quantidade <= 0`` e
        ``EstoqueInsuficienteException`` se a quantidade disponivel
        for menor que a solicitada.
        """
        if quantidade <= 0:
            msg = f"Quantidade para reserva deve ser positiva (recebido: {quantidade})"
            raise ValueError(msg)
        if self._quantidade < quantidade:
            raise EstoqueInsuficienteException(
                mensagem=(
                    f"Estoque insuficiente: disponivel={self._quantidade},"
                    f" solicitado={quantidade}"
                )
            )
        self._quantidade -= quantidade
        self._registrar_evento(
            EstoqueReservadoEvent(
                agregado_id=self.id,
                quantidade_reservada=quantidade,
                quantidade_restante=self._quantidade,
            )
        )

    def liberar(self, quantidade: int) -> None:
        """Libera (devolve) ``quantidade`` ao estoque.

        Pre-condicao: ``quantidade > 0``. Emite ``EstoqueLiberadoEvent``.
        Levanta ``ValueError`` se ``quantidade <= 0``.
        """
        if quantidade <= 0:
            msg = (
                f"Quantidade para liberacao deve ser positiva (recebido: {quantidade})"
            )
            raise ValueError(msg)
        self._quantidade += quantidade
        self._registrar_evento(
            EstoqueLiberadoEvent(
                agregado_id=self.id,
                quantidade_liberada=quantidade,
                quantidade_atual=self._quantidade,
            )
        )

    def atualizar(self, nome: str, descricao: str, preco_unitario: Dinheiro) -> None:
        """Atualiza nome, descricao e preco. Reaplica invariantes."""
        _validar_nome(nome)
        _validar_preco_obrigatorio(preco_unitario)
        self._nome = nome
        self._descricao = descricao
        self._preco_unitario = preco_unitario

    def ajustar_quantidade(self, nova_quantidade: int) -> None:
        """Ajusta a quantidade total em estoque. Rejeita valores negativos."""
        _validar_quantidade_nao_negativa(nova_quantidade)
        self._quantidade = nova_quantidade

    def desativar(self) -> None:
        """Marca o item como indisponivel. Idempotente."""
        self._ativo = False

    def ativar(self) -> None:
        """Marca o item como disponivel. Idempotente."""
        self._ativo = True
