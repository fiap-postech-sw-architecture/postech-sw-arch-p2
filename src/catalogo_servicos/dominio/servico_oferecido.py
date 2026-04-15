from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.compartilhado.dominio.aggregate_root import AggregateRoot

if TYPE_CHECKING:
    from src.compartilhado.dominio.dinheiro import Dinheiro


def _validar_nome_e_descricao(nome: str, descricao: str) -> None:
    """Valida invariantes de texto do servico."""
    if not nome:
        msg = f"Nome do servico nao pode ser vazio (recebido: {nome!r})"
        raise ValueError(msg)
    if not descricao:
        msg = f"Descricao do servico nao pode ser vazia (recebido: {descricao!r})"
        raise ValueError(msg)


@dataclass(eq=False)
class ServicoOferecido(AggregateRoot):
    """Aggregate root do contexto Catalogo de Servicos.

    Representa um servico oferecido pela oficina (troca de oleo, alinhamento,
    etc.). Invariantes garantidas por ``__post_init__``:

    - ``nome`` e ``descricao`` nao vazios
    - ``preco`` obrigatorio e do tipo ``Dinheiro``

    Mutacoes passam por metodos de dominio (``atualizar``, ``desativar``,
    ``ativar``), nunca por setters diretos.
    """

    _nome: str = ""
    _descricao: str = ""
    # Default None permite ao SQLAlchemy construir a instancia antes do
    # evento ``load`` rehidratar ``_preco`` via ``preco_valor``/``preco_moeda``.
    _preco: Dinheiro = None  # type: ignore[assignment]
    _ativo: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        _validar_nome_e_descricao(self._nome, self._descricao)
        if self._preco is None:
            msg = "Preco do servico e obrigatorio"
            raise ValueError(msg)

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def descricao(self) -> str:
        return self._descricao

    @property
    def preco(self) -> Dinheiro:
        return self._preco

    @property
    def ativo(self) -> bool:
        return self._ativo

    def atualizar(self, nome: str, descricao: str, preco: Dinheiro) -> None:
        """Atualiza os atributos mutaveis do servico, reaplicando invariantes."""
        _validar_nome_e_descricao(nome, descricao)
        if preco is None:
            msg = "Preco do servico e obrigatorio"
            raise ValueError(msg)
        self._nome = nome
        self._descricao = descricao
        self._preco = preco

    def desativar(self) -> None:
        """Marca o servico como indisponivel. Idempotente."""
        self._ativo = False

    def ativar(self) -> None:
        """Marca o servico como disponivel. Idempotente."""
        self._ativo = True
