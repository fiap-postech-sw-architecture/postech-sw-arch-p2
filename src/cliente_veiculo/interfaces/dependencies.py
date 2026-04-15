"""Factory functions que montam os use cases do Cliente+Veiculo com os adapters
SQLAlchemy concretos e a sessao injetada pelo FastAPI.

Cada `obter_<use_case>(session)` retorna uma instancia do use case pronta para
ser consumida via `Depends()` pelo router. Operacoes de escrita recebem tambem
um `SQLAlchemyUnitOfWork`; `DesativarCliente` e `RemoverVeiculo` recebem o
`OrdemDeServicoSQLAlchemyAdapter` para as checagens de OS ativa.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.cliente_veiculo.aplicacao.use_cases import (
        AdicionarVeiculo,
        AtualizarCliente,
        CriarCliente,
        DesativarCliente,
        ListarClientes,
        ListarVeiculos,
        ObterCliente,
        RemoverVeiculo,
    )

__all__ = ["obter_session"]


def obter_criar_cliente(session: Session) -> CriarCliente:
    from src.cliente_veiculo.aplicacao.use_cases import CriarCliente
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return CriarCliente(
        repo=ClienteSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_listar_clientes(session: Session) -> ListarClientes:
    from src.cliente_veiculo.aplicacao.use_cases import ListarClientes
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    return ListarClientes(repo=ClienteSQLAlchemyRepository(session=session))


def obter_obter_cliente(session: Session) -> ObterCliente:
    from src.cliente_veiculo.aplicacao.use_cases import ObterCliente
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    return ObterCliente(repo=ClienteSQLAlchemyRepository(session=session))


def obter_atualizar_cliente(session: Session) -> AtualizarCliente:
    from src.cliente_veiculo.aplicacao.use_cases import AtualizarCliente
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return AtualizarCliente(
        repo=ClienteSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_desativar_cliente(session: Session) -> DesativarCliente:
    from src.cliente_veiculo.aplicacao.use_cases import DesativarCliente
    from src.cliente_veiculo.infraestrutura.adapters import (
        OrdemDeServicoSQLAlchemyAdapter,
    )
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return DesativarCliente(
        repo=ClienteSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
        os_port=OrdemDeServicoSQLAlchemyAdapter(session=session),
    )


def obter_adicionar_veiculo(session: Session) -> AdicionarVeiculo:
    from src.cliente_veiculo.aplicacao.use_cases import AdicionarVeiculo
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return AdicionarVeiculo(
        repo=ClienteSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_listar_veiculos(session: Session) -> ListarVeiculos:
    from src.cliente_veiculo.aplicacao.use_cases import ListarVeiculos
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )

    return ListarVeiculos(repo=ClienteSQLAlchemyRepository(session=session))


def obter_remover_veiculo(session: Session) -> RemoverVeiculo:
    from src.cliente_veiculo.aplicacao.use_cases import RemoverVeiculo
    from src.cliente_veiculo.infraestrutura.adapters import (
        OrdemDeServicoSQLAlchemyAdapter,
    )
    from src.cliente_veiculo.infraestrutura.repository import (
        ClienteSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return RemoverVeiculo(
        repo=ClienteSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
        os_port=OrdemDeServicoSQLAlchemyAdapter(session=session),
    )
