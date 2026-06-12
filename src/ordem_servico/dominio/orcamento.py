"""Value Objects ``LinhaOrcamento`` e ``Orcamento``: snapshot imutavel
do calculo do orcamento gerado a partir dos itens da OrdemDeServico.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import reduce
from operator import add
from typing import TYPE_CHECKING

from src.compartilhado.dominio.value_object import ValueObject

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.compartilhado.dominio.dinheiro import Dinheiro
    from src.ordem_servico.dominio.item_da_ordem import ItemDaOrdem


@dataclass(frozen=True, slots=True)
class LinhaOrcamento(ValueObject):
    """Linha imutavel de um orcamento.

    Mantem a invariante ``subtotal == preco_unitario * quantidade`` e
    rejeita campos obrigatorios ausentes (``descricao``, ``preco_unitario``,
    ``subtotal``) ou ``quantidade <= 0``.
    """

    descricao: str = ""
    quantidade: int = 0
    _preco_unitario: Dinheiro | None = None
    _subtotal: Dinheiro | None = None

    def __post_init__(self) -> None:
        if not self.descricao:
            msg = (
                f"Descricao da linha de orcamento nao pode ser vazia "
                f"(recebido: {self.descricao!r})"
            )
            raise ValueError(msg)
        if self.quantidade <= 0:
            msg = f"Quantidade deve ser maior que zero (recebido: {self.quantidade})"
            raise ValueError(msg)
        if self._preco_unitario is None:
            msg = "preco_unitario da linha de orcamento e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if self._subtotal is None:
            msg = "subtotal da linha de orcamento e obrigatorio (recebido: None)"
            raise ValueError(msg)
        esperado = self._preco_unitario * self.quantidade
        if self._subtotal != esperado:
            msg = (
                f"Subtotal inconsistente: recebido {self._subtotal}, "
                f"esperado {esperado} ({self._preco_unitario} * {self.quantidade})"
            )
            raise ValueError(msg)

    @property
    def preco_unitario(self) -> Dinheiro:
        if self._preco_unitario is None:
            msg = "preco_unitario da linha de orcamento nao pode ser nulo"
            raise ValueError(msg)
        return self._preco_unitario

    @property
    def subtotal(self) -> Dinheiro:
        if self._subtotal is None:
            msg = "subtotal da linha de orcamento nao pode ser nulo"
            raise ValueError(msg)
        return self._subtotal


@dataclass(frozen=True, slots=True)
class Orcamento(ValueObject):
    """Orcamento imutavel agregando ``LinhaOrcamento`` e total.

    Construir preferencialmente via ``Orcamento.gerar(itens_da_ordem)``.
    A construcao direta tambem e suportada, mas exige consistencia entre
    ``total`` e a soma dos ``subtotal`` das linhas; valores divergentes
    sao rejeitados em ``__post_init__``.
    """

    itens: tuple[LinhaOrcamento, ...] = ()
    _total: Dinheiro | None = None
    _gerado_em: datetime | None = None
    versao_schema: int = 1

    def __post_init__(self) -> None:
        if not self.itens:
            msg = "Orcamento deve conter pelo menos um item (recebido: vazio)"
            raise ValueError(msg)
        if self._total is None:
            msg = "total do orcamento e obrigatorio (recebido: None)"
            raise ValueError(msg)
        if self._gerado_em is None:
            msg = "gerado_em do orcamento e obrigatorio (recebido: None)"
            raise ValueError(msg)
        esperado = reduce(add, (linha.subtotal for linha in self.itens))
        if self._total != esperado:
            msg = (
                f"Total inconsistente com a soma dos subtotais: "
                f"recebido {self._total}, esperado {esperado}"
            )
            raise ValueError(msg)

    @property
    def total(self) -> Dinheiro:
        if self._total is None:
            msg = "total do orcamento nao pode ser nulo"
            raise ValueError(msg)
        return self._total

    @property
    def gerado_em(self) -> datetime:
        if self._gerado_em is None:
            msg = "gerado_em do orcamento nao pode ser nulo"
            raise ValueError(msg)
        return self._gerado_em

    @staticmethod
    def gerar(itens_da_ordem: Sequence[ItemDaOrdem]) -> Orcamento:
        """Cria um ``Orcamento`` a partir de uma sequencia de itens.

        Levanta ``ValueError`` se a sequencia for vazia, garantindo que
        callers recebam um erro de dominio em vez de ``IndexError``.
        """
        if not itens_da_ordem:
            msg = "Orcamento.gerar exige pelo menos um item (recebido: sequencia vazia)"
            raise ValueError(msg)
        linhas: list[LinhaOrcamento] = []
        for item in itens_da_ordem:
            preco = item.preco_unitario
            qtd = item.quantidade
            subtotal = preco * qtd
            linhas.append(
                LinhaOrcamento(
                    descricao=item.descricao,
                    quantidade=qtd,
                    _preco_unitario=preco,
                    _subtotal=subtotal,
                )
            )
        total = reduce(add, (linha.subtotal for linha in linhas))
        return Orcamento(
            itens=tuple(linhas),
            _total=total,
            _gerado_em=datetime.now(UTC),
        )
