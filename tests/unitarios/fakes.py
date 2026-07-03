"""Fakes compartilhados dos testes unitarios de casos de uso.

``FakeUnitOfWork`` era copiado em 6 arquivos ``test_use_cases*`` (issue
#173). As copias divergiam apenas no rastreio de ``rolled_back``
(cliente_veiculo); esta versao unificada e o SUPERSET: rastreia ``committed``
E ``rolled_back`` (rollback explicito ou excecao dentro do bloco ``with``,
espelhando o contrato da ``SQLAlchemyUnitOfWork`` real). Quem nao afere
``rolled_back`` simplesmente o ignora — nenhum comportamento divergiu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.rolled_back = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
