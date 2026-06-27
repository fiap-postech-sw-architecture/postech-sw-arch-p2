from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class OrdemDeServicoPort(Protocol):
    """Porta de consulta ao contexto Ordem de Servico.

    Mantida sob Estoque para que este contexto nao acople diretamente ao
    modulo ``ordem_servico``. Implementacoes concretas vivem em
    ``src/estoque/infraestrutura/``.
    """

    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def existe_os_ativa_com_item_estoque(self, item_estoque_id: UUID) -> bool:
        pass
