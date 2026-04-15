from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.estoque.aplicacao.use_cases import (
        AjustarQuantidade,
        AtualizarItemEstoque,
        CriarItemEstoque,
        DesativarItemEstoque,
        ListarItensEstoque,
        ObterItemEstoque,
    )


def obter_criar_item(session: Session) -> CriarItemEstoque:
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.estoque.aplicacao.use_cases import CriarItemEstoque
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return CriarItemEstoque(
        repo=ItemEstoqueSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_listar_itens(session: Session) -> ListarItensEstoque:
    from src.estoque.aplicacao.use_cases import ListarItensEstoque
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return ListarItensEstoque(repo=ItemEstoqueSQLAlchemyRepository(session=session))


def obter_obter_item(session: Session) -> ObterItemEstoque:
    from src.estoque.aplicacao.use_cases import ObterItemEstoque
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return ObterItemEstoque(repo=ItemEstoqueSQLAlchemyRepository(session=session))


def obter_atualizar_item(session: Session) -> AtualizarItemEstoque:
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.estoque.aplicacao.use_cases import AtualizarItemEstoque
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return AtualizarItemEstoque(
        repo=ItemEstoqueSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_ajustar_quantidade(session: Session) -> AjustarQuantidade:
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.estoque.aplicacao.use_cases import AjustarQuantidade
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return AjustarQuantidade(
        repo=ItemEstoqueSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_desativar_item(session: Session) -> DesativarItemEstoque:
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
    from src.estoque.aplicacao.use_cases import DesativarItemEstoque
    from src.estoque.infraestrutura.adapters import (
        OrdemDeServicoSQLAlchemyAdapter,
    )
    from src.estoque.infraestrutura.repository import (
        ItemEstoqueSQLAlchemyRepository,
    )

    return DesativarItemEstoque(
        repo=ItemEstoqueSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
        os_port=OrdemDeServicoSQLAlchemyAdapter(session=session),
    )
