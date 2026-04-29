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
from src.ordem_servico.aplicacao.ports import ItemEstoqueDTO, ServicoOferecidoDTO

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

    def obter_item(self, item_estoque_id: UUID) -> ItemEstoqueDTO | None:
        """Retorna ``ItemEstoqueDTO`` ou ``None`` se nao existe.

        Usado pra resolver o preco da peca consumida em ``AdicionarItem``.
        """
        from src.estoque.dominio.item_estoque import ItemEstoque

        item = self._session.get(ItemEstoque, item_estoque_id)
        if item is None:
            return None
        return ItemEstoqueDTO(
            id=item.id,
            nome=item.nome,
            preco_unitario=item.preco_unitario,
        )

    def obter_itens_em_lote(
        self, item_estoque_ids: set[UUID]
    ) -> dict[UUID, ItemEstoqueDTO]:
        """Carrega varios itens em uma unica consulta ``IN (...)``.

        Implementa o contrato batch da ``EstoquePort``: ``set`` vazio
        retorna dict vazio sem tocar a session; ids ausentes ficam de
        fora do dict (caller decide o fallback).
        """
        if not item_estoque_ids:
            return {}

        from sqlalchemy import select

        from src.estoque.dominio.item_estoque import ItemEstoque

        # `type: ignore[attr-defined]`: imperative mapping injeta `.in_()` no
        # atributo `id` em runtime (SQLAlchemy ColumnProperty), mas o mypy ve
        # apenas o tipo `UUID` declarado no AggregateRoot.
        rows = self._session.execute(
            select(ItemEstoque).where(
                ItemEstoque.id.in_(item_estoque_ids)  # type: ignore[attr-defined]
            )
        ).scalars()
        return {
            item.id: ItemEstoqueDTO(
                id=item.id,
                nome=item.nome,
                preco_unitario=item.preco_unitario,
            )
            for item in rows
        }


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

    def obter_servicos_em_lote(
        self, servico_ids: set[UUID]
    ) -> dict[UUID, ServicoOferecidoDTO]:
        """Carrega varios servicos em uma unica consulta ``IN (...)``.

        Implementa o contrato batch da ``CatalogoPort``: ``set`` vazio
        retorna dict vazio sem tocar a session; ids ausentes ficam de
        fora do dict (caller decide o fallback).
        """
        if not servico_ids:
            return {}

        from sqlalchemy import select

        from src.catalogo_servicos.dominio.servico_oferecido import (
            ServicoOferecido,
        )

        # `type: ignore[attr-defined]`: imperative mapping injeta `.in_()` no
        # atributo `id` em runtime (SQLAlchemy ColumnProperty), mas o mypy ve
        # apenas o tipo `UUID` declarado no AggregateRoot.
        rows = self._session.execute(
            select(ServicoOferecido).where(
                ServicoOferecido.id.in_(servico_ids)  # type: ignore[attr-defined]
            )
        ).scalars()
        return {
            servico.id: ServicoOferecidoDTO(
                id=servico.id,
                nome=servico.nome,
                preco=servico.preco,
                ativo=servico.ativo,
            )
            for servico in rows
        }


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
