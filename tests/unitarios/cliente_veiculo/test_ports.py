from __future__ import annotations

from typing import TYPE_CHECKING

from src.cliente_veiculo.aplicacao.ports import OrdemDeServicoPort

if TYPE_CHECKING:
    from uuid import UUID


class _FakeOrdemPort:
    def existe_os_ativa_para_cliente(self, cliente_id: UUID) -> bool:
        _ = cliente_id
        return False

    def existe_os_para_veiculo(self, veiculo_id: UUID) -> bool:
        _ = veiculo_id
        return False


def test_ordem_de_servico_port_aceita_implementacao_estrutural() -> None:
    # Structural subtyping: any object exposing both methods satisfies the Protocol.
    port: OrdemDeServicoPort = _FakeOrdemPort()
    from uuid import uuid4

    assert port.existe_os_ativa_para_cliente(uuid4()) is False
    assert port.existe_os_para_veiculo(uuid4()) is False
