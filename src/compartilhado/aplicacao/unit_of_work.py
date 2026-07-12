from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWork(Protocol):
    # corpos `pass` (nao `...`) evitam o FP CodeQL py/ineffectual-statement
    def __enter__(self) -> Self:
        """Abre a unidade de trabalho (nova sessao) e devolve a si mesma."""
        pass

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Faz rollback se a transacao terminou em excecao e fecha a sessao."""
        pass

    def commit(self) -> None:
        """Comita a transacao; IntegrationEvents vao para a outbox no mesmo commit."""
        pass

    def rollback(self) -> None:
        """Desfaz as alteracoes pendentes da transacao atual."""
        pass
