from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from src.catalogo_servicos.dominio.servico_oferecido import ServicoOferecido


class ServicoOferecidoRepository(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def obter_por_id(self, servico_id: UUID) -> ServicoOferecido | None:
        """Busca o servico pelo id; None se nao existir."""
        pass

    def salvar(self, servico: ServicoOferecido) -> None:
        """Adiciona o servico a sessao e faz flush imediato."""
        pass

    def listar(self, offset: int = 0, limit: int = 20) -> list[ServicoOferecido]:
        """Lista paginada ordenada por nome, com id como desempate deterministico."""
        pass

    def contar(self) -> int:
        """Total de servicos cadastrados (para a paginacao de ``listar``)."""
        pass
