from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.catalogo_servicos.aplicacao.dtos import (
    AtualizarServicoDTO,
    CriarServicoDTO,
)
from src.catalogo_servicos.aplicacao.use_cases import (
    AtualizarServico,
    CriarServico,
    DesativarServico,
    ListarServicos,
    ObterServico,
)
from src.catalogo_servicos.dominio.exceptions import (
    ServicoNaoEncontradoException,
)
from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.compartilhado.dominio.dinheiro import Dinheiro


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeServicoOferecidoRepository:
    def __init__(self) -> None:
        self._servicos: dict[UUID, ServicoOferecido] = {}

    def obter_por_id(self, servico_id: UUID) -> ServicoOferecido | None:
        return self._servicos.get(servico_id)

    def salvar(self, servico: ServicoOferecido) -> None:
        self._servicos[servico.id] = servico

    def listar(self, offset: int = 0, limit: int = 20) -> list[ServicoOferecido]:
        todos = list(self._servicos.values())
        return todos[offset : offset + limit]

    def contar(self) -> int:
        return len(self._servicos)


class TestCriarServico:
    def test_sucesso(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uow = FakeUnitOfWork()
        uc = CriarServico(repo=repo, uow=uow)
        dto = CriarServicoDTO(
            nome="Troca de oleo",
            descricao="Troca completa",
            preco=Decimal("100.00"),
        )
        result = uc.executar(dto)
        assert result.nome == "Troca de oleo"
        assert result.preco == Decimal("100.00")
        assert uow.committed


class TestListarServicos:
    def test_vazio(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uc = ListarServicos(repo=repo)
        assert uc.executar() == []

    def test_com_dados(self) -> None:
        repo = FakeServicoOferecidoRepository()
        preco = Dinheiro(valor=Decimal("100.00"))
        servico = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Desc", _preco=preco
        )
        repo.salvar(servico)
        uc = ListarServicos(repo=repo)
        result = uc.executar()
        assert len(result) == 1
        assert result[0].nome == "Troca de oleo"
        assert result[0].preco == Decimal("100.00")
        assert result[0].moeda == "BRL"
        assert result[0].ativo is True

    def test_contar(self) -> None:
        repo = FakeServicoOferecidoRepository()
        preco = Dinheiro(valor=Decimal("100.00"))
        repo.salvar(ServicoOferecido(_nome="A", _descricao="desc", _preco=preco))
        repo.salvar(ServicoOferecido(_nome="B", _descricao="desc", _preco=preco))
        assert ListarServicos(repo=repo).contar() == 2


class TestObterServico:
    def test_encontrado(self) -> None:
        repo = FakeServicoOferecidoRepository()
        preco = Dinheiro(valor=Decimal("100.00"))
        servico = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Desc", _preco=preco
        )
        repo.salvar(servico)
        uc = ObterServico(repo=repo)
        result = uc.executar(servico.id)
        assert result.nome == "Troca de oleo"

    def test_nao_encontrado(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uc = ObterServico(repo=repo)
        with pytest.raises(ServicoNaoEncontradoException):
            uc.executar(uuid4())


class TestAtualizarServico:
    def test_sucesso(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uow = FakeUnitOfWork()
        preco = Dinheiro(valor=Decimal("100.00"))
        servico = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Desc", _preco=preco
        )
        repo.salvar(servico)
        uc = AtualizarServico(repo=repo, uow=uow)
        dto = AtualizarServicoDTO(
            nome="Revisao", descricao="Revisao geral", preco=Decimal("150.00")
        )
        result = uc.executar(servico.id, dto)
        assert result.nome == "Revisao"

    def test_nao_encontrado(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uow = FakeUnitOfWork()
        uc = AtualizarServico(repo=repo, uow=uow)
        dto = AtualizarServicoDTO(nome="X", descricao="Y", preco=Decimal("10.00"))
        with pytest.raises(ServicoNaoEncontradoException):
            uc.executar(uuid4(), dto)


class TestDesativarServico:
    def test_sucesso(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uow = FakeUnitOfWork()
        preco = Dinheiro(valor=Decimal("100.00"))
        servico = ServicoOferecido(
            _nome="Troca de oleo", _descricao="Desc", _preco=preco
        )
        repo.salvar(servico)
        uc = DesativarServico(repo=repo, uow=uow)
        uc.executar(servico.id)
        servico_atualizado = repo.obter_por_id(servico.id)
        assert servico_atualizado is not None
        assert not servico_atualizado.ativo

    def test_nao_encontrado(self) -> None:
        repo = FakeServicoOferecidoRepository()
        uow = FakeUnitOfWork()
        uc = DesativarServico(repo=repo, uow=uow)
        with pytest.raises(ServicoNaoEncontradoException):
            uc.executar(uuid4())
