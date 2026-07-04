from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.catalogo_servicos.dominio.events import ServicoCadastradoEvent
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

    Mutacoes passam por metodos de dominio (``atualizar``, ``desativar``),
    nunca por setters diretos. Hoje apenas a factory ``criar`` emite evento
    (``ServicoCadastradoEvent``); as mutacoes nao emitem eventos proprios.
    """

    _nome: str = ""
    _descricao: str = ""
    # Default None permite ao SQLAlchemy construir a instancia antes do
    # evento ``load`` rehidratar ``_preco`` via ``preco_valor``/``preco_moeda``.
    _preco: Dinheiro | None = None
    _ativo: bool = True

    def __post_init__(self) -> None:
        super().__post_init__()
        _validar_nome_e_descricao(self._nome, self._descricao)
        if self._preco is None:
            msg = "Preco do servico e obrigatorio"
            raise ValueError(msg)

    @classmethod
    def criar(cls, *, nome: str, descricao: str, preco: Dinheiro) -> ServicoOferecido:
        """Factory de cadastro: constroi o servico e registra o evento de criacao.

        A emissao do `ServicoCadastradoEvent` vive aqui, e nao no
        construtor/`__post_init__`. Assim so o cadastro real (via `criar`)
        emite: construcao crua e a reconstituicao do repository (que passa por
        `__new__`, sem `__init__`) ficam sem evento.
        """
        servico = cls(_nome=nome, _descricao=descricao, _preco=preco)
        servico._registrar_evento(ServicoCadastradoEvent(agregado_id=servico.id))
        return servico

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def descricao(self) -> str:
        return self._descricao

    @property
    def preco(self) -> Dinheiro:
        if self._preco is None:
            msg = "Preco do servico nao pode ser nulo"
            raise ValueError(msg)
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
