from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from src.ordem_servico.infraestrutura.mapping import ordens_de_servico_table

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

_ESTADOS_TERMINAIS = {"entregue", "cancelada"}


class OrdemDeServicoSQLAlchemyAdapter:
    """Adapta consultas SQLAlchemy para o contrato `OrdemDeServicoPort`.

    Verifica se existe uma ordem de servico em estado nao terminal associada
    ao cliente ou veiculo informado, evitando que clientes e veiculos com OS
    ativa sejam desativados ou removidos.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def existe_os_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(ordens_de_servico_table)
            .where(ordens_de_servico_table.c.cliente_id == cliente_id)
            .where(ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS))
        )
        return (self._session.scalar(stmt) or 0) > 0

    def existe_os_ativa_para_veiculo(self, veiculo_id: UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(ordens_de_servico_table)
            .where(ordens_de_servico_table.c.veiculo_id == veiculo_id)
            .where(ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS))
        )
        return (self._session.scalar(stmt) or 0) > 0
