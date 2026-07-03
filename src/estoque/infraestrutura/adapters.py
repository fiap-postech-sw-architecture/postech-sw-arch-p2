from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import exists, select

from src.ordem_servico.dominio.status import StatusOrdem
from src.ordem_servico.infraestrutura.mapping import (
    itens_da_ordem_table,
    ordens_de_servico_table,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

# OS ativa = qualquer status que nao seja terminal. Valores derivados do enum
# de dominio da OS (fonte unica) em vez de literais que driftariam.
_ESTADOS_TERMINAIS = (StatusOrdem.ENTREGUE.value, StatusOrdem.CANCELADA.value)


class OrdemDeServicoSQLAlchemyAdapter:
    """Implementa ``OrdemDeServicoPort`` consultando as tabelas de OS."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def existe_os_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        stmt = select(
            exists().where(
                ordens_de_servico_table.c.id == itens_da_ordem_table.c.ordem_id,
                itens_da_ordem_table.c.item_estoque_id == item_estoque_id,
                ordens_de_servico_table.c.status.notin_(_ESTADOS_TERMINAIS),
            )
        )
        return bool(self._session.scalar(stmt))
