"""Fabricas de use cases do contexto Catalogo de Servicos.

Os imports sao feitos dentro de cada funcao para evitar ciclos entre
``aplicacao``, ``infraestrutura`` e ``interfaces`` durante a montagem
do grafo de dependencias do FastAPI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.catalogo_servicos.aplicacao.use_cases import (
        AtualizarServico,
        CriarServico,
        DesativarServico,
        ListarServicos,
        ObterServico,
    )


def obter_criar_servico(session: Session) -> CriarServico:
    from src.catalogo_servicos.aplicacao.use_cases import CriarServico
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return CriarServico(
        repo=ServicoOferecidoSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_listar_servicos(session: Session) -> ListarServicos:
    from src.catalogo_servicos.aplicacao.use_cases import ListarServicos
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )

    return ListarServicos(repo=ServicoOferecidoSQLAlchemyRepository(session=session))


def obter_obter_servico(session: Session) -> ObterServico:
    from src.catalogo_servicos.aplicacao.use_cases import ObterServico
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )

    return ObterServico(repo=ServicoOferecidoSQLAlchemyRepository(session=session))


def obter_atualizar_servico(session: Session) -> AtualizarServico:
    from src.catalogo_servicos.aplicacao.use_cases import AtualizarServico
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return AtualizarServico(
        repo=ServicoOferecidoSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_desativar_servico(session: Session) -> DesativarServico:
    from src.catalogo_servicos.aplicacao.use_cases import DesativarServico
    from src.catalogo_servicos.infraestrutura.repository import (
        ServicoOferecidoSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return DesativarServico(
        repo=ServicoOferecidoSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )
