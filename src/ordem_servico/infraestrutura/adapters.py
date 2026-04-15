"""Adapters SQLAlchemy das portas de saida do contexto Ordem de Servico.

Implementam ``EstoquePort``, ``CatalogoPort`` e ``ClientePort`` (definidos
em ``src.ordem_servico.aplicacao.ports``) consultando os agregados dos
contextos vizinhos via ``Session`` compartilhada. Os entity imports de
outros bounded contexts sao locais (dentro dos metodos) para evitar
acoplamento no grafo de imports no load-time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.dominio.exceptions import EntidadeNaoEncontradaException
from src.ordem_servico.aplicacao.ports import ServicoOferecidoDTO

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session


class EstoqueSQLAlchemyAdapter:
    """Implementa ``EstoquePort`` acessando o agregado ``ItemEstoque`` via Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Reserva ``quantidade`` do item informado; delega a ``ItemEstoque.reservar``.

        Raises:
            EntidadeNaoEncontradaException: item de estoque nao existe.
        """
        from src.estoque.dominio.item_estoque import ItemEstoque

        item = self._session.get(ItemEstoque, item_estoque_id)
        if item is None:
            raise EntidadeNaoEncontradaException(
                mensagem="Item de estoque nao encontrado"
            )
        item.reservar(quantidade)

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Libera ``quantidade`` do item informado; delega a ``ItemEstoque.liberar``.

        Raises:
            EntidadeNaoEncontradaException: item de estoque nao existe.
        """
        from src.estoque.dominio.item_estoque import ItemEstoque

        item = self._session.get(ItemEstoque, item_estoque_id)
        if item is None:
            raise EntidadeNaoEncontradaException(
                mensagem="Item de estoque nao encontrado"
            )
        item.liberar(quantidade)


class CatalogoSQLAlchemyAdapter:
    """Implementa ``CatalogoPort`` lendo ``ServicoOferecido`` do catalogo."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def obter_servico(self, servico_id: UUID) -> ServicoOferecidoDTO | None:
        """Retorna o DTO do servico, ou ``None`` se nao existir no catalogo."""
        from src.catalogo_servicos.dominio.servico_oferecido import (
            ServicoOferecido,
        )

        servico = self._session.get(ServicoOferecido, servico_id)
        if servico is None:
            return None
        return ServicoOferecidoDTO(
            id=servico.id,
            nome=servico.nome,
            preco=servico.preco,
            ativo=servico.ativo,
        )


class ClienteSQLAlchemyAdapter:
    """Implementa ``ClientePort`` checando existencia de ``Cliente`` e ``Veiculo``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def cliente_existe(self, cliente_id: UUID) -> bool:
        """Indica se o cliente existe no contexto Cliente+Veiculo."""
        from src.cliente_veiculo.dominio.cliente import Cliente

        return self._session.get(Cliente, cliente_id) is not None

    def veiculo_existe(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo existe no contexto Cliente+Veiculo."""
        from src.cliente_veiculo.dominio.veiculo import Veiculo

        return self._session.get(Veiculo, veiculo_id) is not None
