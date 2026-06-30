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
from src.ordem_servico.aplicacao.ports import (
    ClienteContatoDTO,
    ClienteResumoDTO,
    ItemEstoqueDTO,
    ServicoOferecidoDTO,
    VeiculoResumoDTO,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    # Import sob TYPE_CHECKING (nao em load-time): a anotacao de retorno de
    # ``_obter_item_com_lock`` e uma string (``from __future__ import
    # annotations``), entao nao acopla o grafo de imports do vizinho em
    # runtime — coerente com os imports locais dentro dos metodos.
    from src.estoque.dominio.item_estoque import ItemEstoque


class EstoqueSQLAlchemyAdapter:
    """Implementa ``EstoquePort`` acessando o agregado ``ItemEstoque`` via Session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reservar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Reserva ``quantidade`` do item informado; delega a ``ItemEstoque.reservar``.

        Carrega o item com ``com_lock=True`` (``SELECT ... FOR UPDATE``) via
        o repositorio de Estoque para serializar reservas/ajustes
        concorrentes do MESMO item (issue #83): sem o lock, duas aprovacoes
        simultaneas leem o saldo stale e gravam por cima uma da outra
        (lost-update -> sobre-venda). O lock e retido ate o commit da UoW
        compartilhada. Mesma protecao que ``AjustarQuantidade`` ja aplica.

        Raises:
            EntidadeNaoEncontradaException: item de estoque nao existe.
        """
        item = self._obter_item_com_lock(item_estoque_id)
        item.reservar(quantidade)

    def liberar(self, item_estoque_id: UUID, quantidade: int) -> None:
        """Libera ``quantidade`` do item informado; delega a ``ItemEstoque.liberar``.

        Carrega o item ``com_lock=True`` (``SELECT ... FOR UPDATE``) pelo
        mesmo motivo de ``reservar`` (issue #83): serializa a leitura-
        modificacao-escrita do saldo para nao perder atualizacoes
        concorrentes. Lock retido ate o commit da UoW.

        Raises:
            EntidadeNaoEncontradaException: item de estoque nao existe.
        """
        item = self._obter_item_com_lock(item_estoque_id)
        item.liberar(quantidade)

    def _obter_item_com_lock(self, item_estoque_id: UUID) -> ItemEstoque:
        """Carrega o ``ItemEstoque`` com ``FOR UPDATE`` ou levanta se ausente.

        Reusa ``ItemEstoqueSQLAlchemyRepository.obter_por_id(com_lock=True)``
        — a UNICA fonte da query de lock pessimista do contexto Estoque
        (``with_for_update``), em vez de duplicar o SELECT aqui. Mantem o
        adapter como ACL: nao reimplementa a regra de lock do vizinho.
        """
        from src.estoque.infraestrutura.repository import (
            ItemEstoqueSQLAlchemyRepository,
        )

        repo = ItemEstoqueSQLAlchemyRepository(session=self._session)
        item = repo.obter_por_id(item_estoque_id, com_lock=True)
        if item is None:
            raise EntidadeNaoEncontradaException(
                mensagem="Item de estoque nao encontrado"
            )
        return item

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
    """Implementa ``ClientePort`` consultando Cliente+Veiculo."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def cliente_existe(self, cliente_id: UUID) -> bool:
        """Indica se o cliente existe no contexto Cliente+Veiculo."""
        from src.cliente_veiculo.dominio.cliente import Cliente

        return self._session.get(Cliente, cliente_id) is not None

    def veiculo_pertence_ao_cliente(self, cliente_id: UUID, veiculo_id: UUID) -> bool:
        """Indica se o veiculo existe e pertence ao cliente informado."""
        from sqlalchemy import exists, select

        from src.cliente_veiculo.infraestrutura.mapping import veiculos_table

        stmt = select(
            exists().where(
                veiculos_table.c.id == veiculo_id,
                veiculos_table.c.cliente_id == cliente_id,
            )
        )
        return bool(self._session.scalar(stmt))

    def obter_clientes_em_lote(
        self, cliente_ids: set[UUID]
    ) -> dict[UUID, ClienteResumoDTO]:
        """Carrega varios clientes em uma unica consulta ``IN (...)``.

        Le direto da tabela (``id``, ``nome``) em vez de hidratar o
        agregado ``Cliente`` — a projecao de leitura nao precisa dos
        listeners de VO (documento, contato) e evita o custo do load
        completo so pra mostrar o nome na UI.
        """
        if not cliente_ids:
            return {}

        from sqlalchemy import select

        from src.cliente_veiculo.infraestrutura.mapping import clientes_table

        rows = self._session.execute(
            select(clientes_table.c.id, clientes_table.c.nome).where(
                clientes_table.c.id.in_(cliente_ids)
            )
        ).all()
        return {row.id: ClienteResumoDTO(id=row.id, nome=row.nome) for row in rows}

    def obter_veiculos_em_lote(
        self, veiculo_ids: set[UUID]
    ) -> dict[UUID, VeiculoResumoDTO]:
        """Carrega varios veiculos em uma unica consulta ``IN (...)``.

        Le ``id`` + ``placa`` direto da tabela (sem reidratar o agregado). Um
        veiculo anonimizado (#72) guarda na coluna ``placa`` o tombstone
        ``ANONIMIZADO:{veiculo_id}``; mascaramos para o sentinela limpo
        ``"ANONIMIZADO"`` aqui para a projecao de OS bater com o read-path do
        agregado (``PlacaAnonimizada.valor``) e nao vazar o formato do tombstone.
        """
        if not veiculo_ids:
            return {}

        from sqlalchemy import select

        from src.cliente_veiculo.infraestrutura.mapping import veiculos_table

        rows = self._session.execute(
            select(veiculos_table.c.id, veiculos_table.c.placa).where(
                veiculos_table.c.id.in_(veiculo_ids)
            )
        ).all()
        return {
            row.id: VeiculoResumoDTO(
                id=row.id,
                placa=(
                    "ANONIMIZADO"
                    if row.placa.startswith("ANONIMIZADO")
                    else row.placa
                ),
            )
            for row in rows
        }

    def obter_contato(self, cliente_id: UUID) -> ClienteContatoDTO | None:
        """Le ``nome`` + ``contato`` direto da tabela (RF-024).

        Mesmo racional de ``obter_clientes_em_lote``: a projecao de
        leitura nao precisa hidratar o agregado ``Cliente`` (listeners de
        VO, decrypt de documento) so para resolver o destinatario do
        e-mail — ``contato`` e armazenado em texto plano.
        """
        from sqlalchemy import select

        from src.cliente_veiculo.infraestrutura.mapping import clientes_table

        row = self._session.execute(
            select(
                clientes_table.c.id, clientes_table.c.nome, clientes_table.c.contato
            ).where(clientes_table.c.id == cliente_id)
        ).first()
        if row is None:
            return None
        return ClienteContatoDTO(id=row.id, nome=row.nome, contato=row.contato)
