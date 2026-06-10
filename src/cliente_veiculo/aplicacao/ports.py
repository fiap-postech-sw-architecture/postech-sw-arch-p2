from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID


class OrdemDeServicoPort(Protocol):
    """Anti-corruption layer entre Cliente+Veiculo e Ordem de Servico.

    O contexto Cliente+Veiculo nao pode importar `ordem_servico` diretamente; em
    vez disso, consome este Protocol, cuja implementacao concreta vive na camada
    de aplicacao/infraestrutura e traduz perguntas sobre vinculos com OS.
    """

    def existe_os_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        """Indica se o cliente possui ordens de servico ainda nao finalizadas."""
        ...

    def existe_os_para_veiculo(self, veiculo_id: UUID) -> bool:
        """Indica se o veiculo possui qualquer ordem de servico (ativa ou encerrada)."""
        ...
