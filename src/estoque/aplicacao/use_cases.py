from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException
from src.estoque.aplicacao.dtos import ItemEstoqueDTO
from src.estoque.dominio.exceptions import ItemEstoqueNaoEncontradoException
from src.estoque.dominio.item_estoque import ItemEstoque

if TYPE_CHECKING:
    from uuid import UUID

    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork
    from src.estoque.aplicacao.dtos import (
        AjustarQuantidadeDTO,
        AtualizarItemEstoqueDTO,
        CriarItemEstoqueDTO,
    )
    from src.estoque.aplicacao.ports import OrdemDeServicoPort
    from src.estoque.dominio.repository import ItemEstoqueRepository


def _item_dto(item: ItemEstoque) -> ItemEstoqueDTO:
    return ItemEstoqueDTO(
        id=item.id,
        nome=item.nome,
        descricao=item.descricao,
        quantidade=item.quantidade,
        preco_unitario=item.preco_unitario.valor,
        moeda=item.preco_unitario.moeda,
        ativo=item.ativo,
    )


def _obter_ou_falhar(
    repo: ItemEstoqueRepository, item_id: UUID, *, com_lock: bool = False
) -> ItemEstoque:
    item = repo.obter_por_id(item_id, com_lock=com_lock)
    if item is None:
        raise ItemEstoqueNaoEncontradoException()
    return item


class CriarItemEstoque:
    def __init__(self, repo: ItemEstoqueRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, dto: CriarItemEstoqueDTO) -> ItemEstoqueDTO:
        preco = Dinheiro(valor=dto.preco_unitario)
        item = ItemEstoque.criar(
            nome=dto.nome,
            descricao=dto.descricao,
            quantidade=dto.quantidade,
            preco_unitario=preco,
        )
        with self._uow:
            self._repo.salvar(item)
            self._uow.commit()
        return _item_dto(item)


class ListarItensEstoque:
    def __init__(self, repo: ItemEstoqueRepository) -> None:
        self._repo = repo

    def executar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoqueDTO]:
        itens = self._repo.listar(offset=offset, limit=limit)
        return [_item_dto(i) for i in itens]

    def contar(self) -> int:
        return self._repo.contar()


class ObterItemEstoque:
    def __init__(self, repo: ItemEstoqueRepository) -> None:
        self._repo = repo

    def executar(self, item_id: UUID) -> ItemEstoqueDTO:
        return _item_dto(_obter_ou_falhar(self._repo, item_id))


class AtualizarItemEstoque:
    def __init__(self, repo: ItemEstoqueRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, item_id: UUID, dto: AtualizarItemEstoqueDTO) -> ItemEstoqueDTO:
        preco = Dinheiro(valor=dto.preco_unitario)
        with self._uow:
            item = _obter_ou_falhar(self._repo, item_id)
            item.atualizar(nome=dto.nome, descricao=dto.descricao, preco_unitario=preco)
            self._repo.salvar(item)
            self._uow.commit()
        return _item_dto(item)


class AjustarQuantidade:
    def __init__(self, repo: ItemEstoqueRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, item_id: UUID, dto: AjustarQuantidadeDTO) -> ItemEstoqueDTO:
        with self._uow:
            # ``com_lock=True`` aplica SELECT FOR UPDATE — serializa writes
            # concorrentes e evita lost-update detectado por
            # ``full-test`` ``AdminConcurrencyJourney``.
            item = _obter_ou_falhar(self._repo, item_id, com_lock=True)
            item.ajustar_quantidade(dto.nova_quantidade)
            self._repo.salvar(item)
            self._uow.commit()
        return _item_dto(item)


class DesativarItemEstoque:
    def __init__(
        self,
        repo: ItemEstoqueRepository,
        uow: UnitOfWork,
        os_port: OrdemDeServicoPort,
    ) -> None:
        self._repo = repo
        self._uow = uow
        self._os_port = os_port

    def executar(self, item_id: UUID) -> None:
        with self._uow:
            # ``com_lock=True`` (FOR UPDATE) serializa a desativacao com a
            # reserva: sem o lock, desativar durante uma reserva em andamento
            # deixaria um item inativo com estoque recem-reservado.
            item = _obter_ou_falhar(self._repo, item_id, com_lock=True)
            if not item.ativo:
                return
            if self._os_port.existe_os_ativa_com_item_estoque(item_id):
                raise ViolacaoRegraDeNegocioException(
                    mensagem="Item de estoque possui ordem de servico ativa"
                )
            item.desativar()
            self._repo.salvar(item)
            self._uow.commit()
