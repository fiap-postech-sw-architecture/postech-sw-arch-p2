from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.compartilhado.dominio.dinheiro import Dinheiro
from src.compartilhado.dominio.exceptions import ViolacaoRegraDeNegocioException
from src.estoque.aplicacao.dtos import (
    AjustarQuantidadeDTO,
    AtualizarItemEstoqueDTO,
    CriarItemEstoqueDTO,
)
from src.estoque.aplicacao.use_cases import (
    AjustarQuantidade,
    AtualizarItemEstoque,
    CriarItemEstoque,
    DesativarItemEstoque,
    ListarItensEstoque,
    ObterItemEstoque,
)
from src.estoque.dominio.exceptions import ItemEstoqueNaoEncontradoException
from src.estoque.dominio.item_estoque import ItemEstoque


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeItemEstoqueRepository:
    def __init__(self) -> None:
        self._itens: dict[UUID, ItemEstoque] = {}

    def obter_por_id(
        self, item_id: UUID, *, com_lock: bool = False
    ) -> ItemEstoque | None:
        del com_lock  # fake in-memory: SELECT FOR UPDATE e no-op
        return self._itens.get(item_id)

    def obter_por_ids(self, ids: list[UUID]) -> list[ItemEstoque]:
        return [self._itens[i] for i in sorted(ids) if i in self._itens]

    def salvar(self, item: ItemEstoque) -> None:
        self._itens[item.id] = item

    def listar(self, offset: int = 0, limit: int = 20) -> list[ItemEstoque]:
        todos = list(self._itens.values())
        return todos[offset : offset + limit]

    def contar(self) -> int:
        return len(self._itens)


class StubOrdemDeServicoPort:
    def __init__(self, os_ativa: bool = False) -> None:
        self._os_ativa = os_ativa

    def existe_os_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        return self._os_ativa


class TestCriarItemEstoque:
    def test_sucesso(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        uc = CriarItemEstoque(repo=repo, uow=uow)
        dto = CriarItemEstoqueDTO(
            nome="Filtro",
            descricao="Filtro de oleo",
            quantidade=10,
            preco_unitario=Decimal("50.00"),
        )
        result = uc.executar(dto)
        assert result.nome == "Filtro"
        assert result.quantidade == 10
        assert uow.committed


class TestListarItensEstoque:
    def test_vazio(self) -> None:
        repo = FakeItemEstoqueRepository()
        uc = ListarItensEstoque(repo=repo)
        assert uc.executar() == []

    def test_com_dados(self) -> None:
        repo = FakeItemEstoqueRepository()
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = ListarItensEstoque(repo=repo)
        result = uc.executar()
        assert len(result) == 1
        assert result[0].nome == "Filtro"
        assert result[0].preco_unitario == Decimal("50.00")
        assert result[0].moeda == "BRL"

    def test_contar(self) -> None:
        repo = FakeItemEstoqueRepository()
        preco = Dinheiro(valor=Decimal("50.00"))
        repo.salvar(
            ItemEstoque(_nome="A", _descricao="A", _quantidade=1, _preco_unitario=preco)
        )
        repo.salvar(
            ItemEstoque(_nome="B", _descricao="B", _quantidade=2, _preco_unitario=preco)
        )
        assert ListarItensEstoque(repo=repo).contar() == 2

    def test_executar_respeita_offset_e_limit(self) -> None:
        repo = FakeItemEstoqueRepository()
        preco = Dinheiro(valor=Decimal("10.00"))
        for nome in ("A", "B", "C"):
            repo.salvar(
                ItemEstoque(
                    _nome=nome, _descricao=nome, _quantidade=1, _preco_unitario=preco
                )
            )
        uc = ListarItensEstoque(repo=repo)
        primeira_pagina = uc.executar(offset=0, limit=2)
        segunda_pagina = uc.executar(offset=2, limit=2)
        assert len(primeira_pagina) == 2
        assert len(segunda_pagina) == 1


class TestObterItemEstoque:
    def test_encontrado(self) -> None:
        repo = FakeItemEstoqueRepository()
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = ObterItemEstoque(repo=repo)
        assert uc.executar(item.id).nome == "Filtro"

    def test_nao_encontrado(self) -> None:
        repo = FakeItemEstoqueRepository()
        uc = ObterItemEstoque(repo=repo)
        with pytest.raises(ItemEstoqueNaoEncontradoException):
            uc.executar(uuid4())


class TestAtualizarItemEstoque:
    def test_sucesso(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = AtualizarItemEstoque(repo=repo, uow=uow)
        dto = AtualizarItemEstoqueDTO(
            nome="Filtro Premium",
            descricao="Premium",
            preco_unitario=Decimal("75.00"),
        )
        result = uc.executar(item.id, dto)
        assert result.nome == "Filtro Premium"

    def test_nao_encontrado(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        uc = AtualizarItemEstoque(repo=repo, uow=uow)
        dto = AtualizarItemEstoqueDTO(
            nome="X", descricao="Y", preco_unitario=Decimal("10.00")
        )
        with pytest.raises(ItemEstoqueNaoEncontradoException):
            uc.executar(uuid4(), dto)


class TestAjustarQuantidade:
    def test_sucesso(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = AjustarQuantidade(repo=repo, uow=uow)
        dto = AjustarQuantidadeDTO(nova_quantidade=20)
        result = uc.executar(item.id, dto)
        assert result.quantidade == 20

    def test_nao_encontrado(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        uc = AjustarQuantidade(repo=repo, uow=uow)
        dto = AjustarQuantidadeDTO(nova_quantidade=5)
        with pytest.raises(ItemEstoqueNaoEncontradoException):
            uc.executar(uuid4(), dto)


class TestDesativarItemEstoque:
    def test_sucesso(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa=False)
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = DesativarItemEstoque(repo=repo, uow=uow, os_port=os_port)
        uc.executar(item.id)
        recarregado = repo.obter_por_id(item.id)
        assert recarregado is not None
        assert recarregado.ativo is False

    def test_bloqueado_por_os_ativa_nao_desativa(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa=True)
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        repo.salvar(item)
        uc = DesativarItemEstoque(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ViolacaoRegraDeNegocioException):
            uc.executar(item.id)
        recarregado = repo.obter_por_id(item.id)
        assert recarregado is not None
        assert recarregado.ativo is True

    def test_idempotente_em_item_ja_inativo(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort(os_ativa=True)
        preco = Dinheiro(valor=Decimal("50.00"))
        item = ItemEstoque(
            _nome="Filtro", _descricao="Desc", _quantidade=10, _preco_unitario=preco
        )
        item.desativar()
        repo.salvar(item)
        uc = DesativarItemEstoque(repo=repo, uow=uow, os_port=os_port)
        uc.executar(item.id)  # nao deve levantar

    def test_nao_encontrado(self) -> None:
        repo = FakeItemEstoqueRepository()
        uow = FakeUnitOfWork()
        os_port = StubOrdemDeServicoPort()
        uc = DesativarItemEstoque(repo=repo, uow=uow, os_port=os_port)
        with pytest.raises(ItemEstoqueNaoEncontradoException):
            uc.executar(uuid4())
