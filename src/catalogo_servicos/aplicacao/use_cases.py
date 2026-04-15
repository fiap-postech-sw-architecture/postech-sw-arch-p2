from __future__ import annotations

from typing import TYPE_CHECKING

from src.catalogo_servicos.aplicacao.dtos import ServicoDTO
from src.catalogo_servicos.dominio.exceptions import ServicoNaoEncontradoException
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
    from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


def _servico_dto(servico: ServicoOferecido) -> ServicoDTO:
    return ServicoDTO(
        id=servico.id,
        nome=servico.nome,
        descricao=servico.descricao,
        preco=servico.preco.valor,
        moeda=servico.preco.moeda,
        ativo=servico.ativo,
    )


class CriarServico:
    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, dto: CriarServicoDTO) -> ServicoDTO:
        # Import local evita ciclo com o modulo de dominio.
        from src.catalogo_servicos.dominio.servico_oferecido import (
            ServicoOferecido,
        )

        preco = Dinheiro(valor=dto.preco)
        servico = ServicoOferecido(
            _nome=dto.nome, _descricao=dto.descricao, _preco=preco
        )
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
        return _servico_dto(servico)


class ListarServicos:
    def __init__(self, repo: ServicoOferecidoRepository) -> None:
        self._repo = repo

    def executar(self, offset: int = 0, limit: int = 20) -> list[ServicoDTO]:
        servicos = self._repo.listar(offset=offset, limit=limit)
        return [_servico_dto(s) for s in servicos]

    def contar(self) -> int:
        return self._repo.contar()


class ObterServico:
    def __init__(self, repo: ServicoOferecidoRepository) -> None:
        self._repo = repo

    def executar(self, servico_id: UUID) -> ServicoDTO:
        servico = self._repo.obter_por_id(servico_id)
        if servico is None:
            raise ServicoNaoEncontradoException()
        return _servico_dto(servico)


class AtualizarServico:
    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, servico_id: UUID, dto: AtualizarServicoDTO) -> ServicoDTO:
        servico = self._repo.obter_por_id(servico_id)
        if servico is None:
            raise ServicoNaoEncontradoException()
        preco = Dinheiro(valor=dto.preco)
        servico.atualizar(nome=dto.nome, descricao=dto.descricao, preco=preco)
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
        return _servico_dto(servico)


class DesativarServico:
    def __init__(self, repo: ServicoOferecidoRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, servico_id: UUID) -> None:
        servico = self._repo.obter_por_id(servico_id)
        if servico is None:
            raise ServicoNaoEncontradoException()
        servico.desativar()
        with self._uow:
            self._repo.salvar(servico)
            self._uow.commit()
