from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido


class ServicoOferecidoRepository(Protocol):
    # Corpos `pass` (nao `...`): o CodeQL (py/ineffectual-statement) marca
    # `...` como statement sem efeito; `pass` e o stub equivalente
    # (no-op, zero custo) e nao dispara o alerta.
    def obter_por_id(self, servico_id: UUID) -> ServicoOferecido | None:
        pass

    def salvar(self, servico: ServicoOferecido) -> None:
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[ServicoOferecido]:
        pass

    def contar(self) -> int:
        pass
