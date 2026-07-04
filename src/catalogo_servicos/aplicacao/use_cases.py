from __future__ import annotations

from typing import TYPE_CHECKING

from src.catalogo_servicos.aplicacao.dtos import ServicoDTO
from src.catalogo_servicos.dominio.exceptions import ServicoNaoEncontradoException
from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
from src.compartilhado.dominio.dinheiro import Dinheiro

if TYPE_CHECKING:
    from uuid import UUID

    from src.catalogo_servicos.aplicacao.dtos import (
        AtualizarServicoDTO,
        CriarServicoDTO,
    )
    from src.catalogo_servicos.dominio.repository import (
        ServicoOferecidoRepository,
    )
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


def _servico_dto(servico: ServicoOferecido) -> ServicoDTO:
    """Converte o agregado ServicoOferecido em `ServicoDTO` para o chamador."""
    return ServicoDTO(
        id=servico.id,
        nome=servico.nome,
        descricao=servico.descricao,
        preco=servico.preco.valor,
        moeda=servico.preco.moeda,
        ativo=servico.ativo,
    )


def _obter_servico_ou_falhar(
    repo: ServicoOferecidoRepository, servico_id: UUID
) -> ServicoOferecido:
    """Busca servico pelo id; levanta `ServicoNaoEncontradoException` se None."""
    servico = repo.obter_por_id(servico_id)
    if servico is None:
        raise ServicoNaoEncontradoException()
    return servico


class CriarServico:
    """Cadastra um novo servico no catalogo e o persiste via UnitOfWork."""

    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, dto: CriarServicoDTO) -> ServicoDTO:
        preco = Dinheiro(valor=dto.preco)
        servico = ServicoOferecido.criar(
            nome=dto.nome, descricao=dto.descricao, preco=preco
        )
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
        return _servico_dto(servico)


class ListarServicos:
    """Lista servicos paginados (padrao: 20 por pagina) e conta o total."""

    def __init__(self, repo: ServicoOferecidoRepository) -> None:
        self._repo = repo

    def executar(self, offset: int = 0, limit: int = 20) -> list[ServicoDTO]:
        servicos = self._repo.listar(offset=offset, limit=limit)
        return [_servico_dto(s) for s in servicos]

    def contar(self) -> int:
        return self._repo.contar()


class ObterServico:
    """Busca um servico pelo id; 404 (`ServicoNaoEncontrado`) se ausente."""

    def __init__(self, repo: ServicoOferecidoRepository) -> None:
        self._repo = repo

    def executar(self, servico_id: UUID) -> ServicoDTO:
        servico = _obter_servico_ou_falhar(self._repo, servico_id)
        return _servico_dto(servico)


class AtualizarServico:
    """Atualiza nome/descricao/preco de um servico existente."""

    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, servico_id: UUID, dto: AtualizarServicoDTO) -> ServicoDTO:
        servico = _obter_servico_ou_falhar(self._repo, servico_id)
        preco = Dinheiro(valor=dto.preco)
        servico.atualizar(nome=dto.nome, descricao=dto.descricao, preco=preco)
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
        return _servico_dto(servico)


class DesativarServico:
    """Desativa (soft-delete) um servico do catalogo. Idempotente."""

    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, servico_id: UUID) -> None:
        servico = _obter_servico_ou_falhar(self._repo, servico_id)
        servico.desativar()
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
