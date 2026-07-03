from __future__ import annotations

from typing import TYPE_CHECKING, Final

from sqlalchemy import exists, select

from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import ordens_de_servico_table

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

# Derivado de StatusOrdem (fonte unica) em vez de strings soltas — espelha
# _ESTADOS_TERMINAIS de ordem_servico/infraestrutura/repository.py.
_ESTADOS_TERMINAIS: Final[frozenset[str]] = frozenset(
    {StatusOrdem.ENTREGUE.value, StatusOrdem.CANCELADA.value}
)


class OrdemDeServicoSQLAlchemyAdapter:
    """Adapta consultas SQLAlchemy para o contrato `OrdemDeServicoPort`.

    Verifica OS ativas para clientes e qualquer OS vinculada a veiculos,
    evitando desativacoes/remocoes que quebrariam regras de negocio ou FKs.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def existe_os_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        stmt = select(
            exists().where(
                ordens_de_servico_table.c.cliente_id == cliente_id,
                ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS),
            )
        )
        return bool(self._session.scalar(stmt))

    def existe_os_para_veiculo(self, veiculo_id: UUID) -> bool:
        """Verifica se existe QUALQUER OS para o veiculo (ativa ou encerrada).

        Usado antes de remover o veiculo do banco para evitar IntegrityError:
        a tabela ordens_de_servico tem FK para veiculos.id sem ON DELETE CASCADE.
        """
        stmt = select(
            exists().where(ordens_de_servico_table.c.veiculo_id == veiculo_id)
        )
        return bool(self._session.scalar(stmt))
