"""Entity ``ItemDaOrdem``: linha de servico ou peca dentro de uma OrdemDeServico."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.compartilhado.dominio.entity import Entity

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.dominio.dinheiro import Dinheiro


@dataclass(eq=False)
class ItemDaOrdem(Entity):
    """Linha de servico ou peca dentro de uma OrdemDeServico.

    Identificada por ``id`` (Entity), mantem invariantes:

    - ``descricao`` nao vazia
    - ``quantidade`` > 0
    - ``servico_catalogo_id`` obrigatorio
    - ``preco_unitario`` obrigatorio (``Dinheiro`` nao nulo) e ``valor`` > 0

    Os campos obrigatorios sao ``kw_only`` sem default (padrao de
    ``DomainEvent.ocorrido_em``): omiti-los falha na construcao em vez de
    escorregar como sentinela ``None`` ate o guard do ``__post_init__``. A
    reidratacao ORM (map_imperatively) escreve direto no ``__dict__`` sem
    passar pelo ``__init__``, entao ``kw_only`` nao a afeta.
    ``_item_estoque_id`` segue genuinamente opcional (mao de obra nao tem
    contrapartida no estoque).
    """

    _servico_catalogo_id: UUID = field(kw_only=True, repr=False)
    _item_estoque_id: UUID | None = field(default=None, kw_only=True, repr=False)
    _descricao: str = field(kw_only=True)
    _quantidade: int = field(kw_only=True)
    _preco_unitario: Dinheiro = field(kw_only=True)

    def __post_init__(self) -> None:
        super().__post_init__()
        # Campo obrigatorio via kw_only sem default: a OMISSAO ja falha na
        # construcao. O guard aqui defende o None EXPLICITO (caller passando
        # None por engano) e a reidratacao ORM, que bypassa o __init__.
        if self._servico_catalogo_id is None:
            msg = "servico_catalogo_id e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if not self._descricao:
            msg = (
                f"Descricao do item nao pode ser vazia (recebido: {self._descricao!r})"
            )
            raise ValueError(msg)
        if self._quantidade <= 0:
            msg = f"Quantidade deve ser maior que zero (recebido: {self._quantidade})"
            raise ValueError(msg)
        if self._preco_unitario is None:
            msg = "preco_unitario do item e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if self._preco_unitario.valor <= 0:
            msg = (
                f"preco_unitario do item deve ser maior que zero "
                f"(recebido: {self._preco_unitario.valor})"
            )
            raise ValueError(msg)

    @classmethod
    def criar(
        cls,
        *,
        servico_catalogo_id: UUID,
        item_estoque_id: UUID | None,
        descricao: str,
        quantidade: int,
        preco_unitario: Dinheiro,
    ) -> ItemDaOrdem:
        """Factory de linha: constroi o item sem expor os campos privados.

        Espelha ``ItemEstoque.criar``. Usado por ``_montar_item`` para nao
        acoplar a camada de aplicacao aos nomes privados (``_descricao``, ...).
        """
        return cls(
            _servico_catalogo_id=servico_catalogo_id,
            _item_estoque_id=item_estoque_id,
            _descricao=descricao,
            _quantidade=quantidade,
            _preco_unitario=preco_unitario,
        )

    @property
    def servico_catalogo_id(self) -> UUID:
        if self._servico_catalogo_id is None:
            msg = "servico_catalogo_id nao pode ser nulo"
            raise ValueError(msg)
        return self._servico_catalogo_id

    @property
    def item_estoque_id(self) -> UUID | None:
        return self._item_estoque_id

    @property
    def descricao(self) -> str:
        return self._descricao

    @property
    def quantidade(self) -> int:
        return self._quantidade

    @property
    def preco_unitario(self) -> Dinheiro:
        if self._preco_unitario is None:
            msg = "preco_unitario nao pode ser nulo"
            raise ValueError(msg)
        return self._preco_unitario

    @property
    def subtotal(self) -> Dinheiro:
        preco_unitario = self.preco_unitario
        return preco_unitario * self._quantidade
