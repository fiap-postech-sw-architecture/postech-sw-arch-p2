from __future__ import annotations

from src.cliente_veiculo.infraestrutura.adapters import (
    OrdemDeServicoSQLAlchemyAdapter,
)
from src.cliente_veiculo.infraestrutura.mapping import (
    clientes_table,
    iniciar_mapeamentos,
    veiculos_table,
)
from src.cliente_veiculo.infraestrutura.repository import (
    ClienteSQLAlchemyRepository,
)

__all__ = [
    "ClienteSQLAlchemyRepository",
    "OrdemDeServicoSQLAlchemyAdapter",
    "clientes_table",
    "iniciar_mapeamentos",
    "veiculos_table",
]
