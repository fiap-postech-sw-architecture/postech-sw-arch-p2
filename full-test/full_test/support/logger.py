"""StepLogger: captura de cada passo executado por uma journey.

Nao usa logging.getLogger — escreve em memoria (lista de PassoExecutado)
e opcionalmente em stderr com prefixo ``[journey_name#instance_id]``. O
orchestrator (step 13) coleta a lista via ``logger.passos()`` ao termino.

Thread-safety: uma instancia de ``StepLogger`` e usada por uma unica journey,
que roda em uma unica thread (ver ``orchestrator-full-e2e-test.md`` — "Run
model"). Nao ha necessidade de lock; escritas no ``_passos`` so acontecem
na thread da propria journey.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from full_test.journeys.resultado import PassoExecutado

if TYPE_CHECKING:
    from collections.abc import Iterator


class StepLogger:
    def __init__(
        self,
        *,
        journey_name: str,
        instance_id: str,
        escrever_stderr: bool = True,
    ) -> None:
        self._journey_name = journey_name
        self._instance_id = instance_id
        self._escrever_stderr = escrever_stderr
        self._passos: list[PassoExecutado] = []

    def passos(self) -> list[PassoExecutado]:
        return list(self._passos)

    @contextmanager
    def passo(self, nome: str, *, correlation_id: str | None = None) -> Iterator[None]:
        inicio = datetime.now(UTC)
        t_inicio = time.perf_counter()
        sucesso = True
        erro: str | None = None
        try:
            yield
        except Exception as exc:
            sucesso = False
            erro = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            fim = datetime.now(UTC)
            duracao_ms = int((time.perf_counter() - t_inicio) * 1000)
            self._passos.append(
                PassoExecutado(
                    nome=nome,
                    inicio=inicio,
                    fim=fim,
                    duracao_ms=duracao_ms,
                    sucesso=sucesso,
                    correlation_id=correlation_id,
                    erro=erro,
                )
            )
            if self._escrever_stderr:
                status = "OK" if sucesso else "FAIL"
                prefixo = f"[{self._journey_name}#{self._instance_id}]"
                linha = f"{prefixo} {nome} {status} ({duracao_ms}ms)"
                if erro:
                    linha += f" - {erro}"
                print(linha, file=sys.stderr, flush=True)
