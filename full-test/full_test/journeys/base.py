"""UserJourney: ABC para todos os cenarios executados pelo orchestrator.

Contrato:
  - ``setup(self)``: preparar recursos (login, cliente+veiculo proprios, etc.)
  - ``executar(self)``: rodar o cenario principal. Pode levantar excecoes.
  - ``teardown(self)``: liberar recursos (fechar httpx client, limpar tokens).

O ``StepLogger`` e injetado e usado pelas subclasses via ``self.log.passo(...)``
para cada acao discreta. Falhas dentro de um passo sao capturadas pelo logger
e re-levantadas; o orchestrator (step 13) converte a excecao em
``StatusJourney.FALHOU`` com ``falha=str(exc)``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from full_test.journeys.resultado import ResultadoJourney, StatusJourney
from full_test.support.logger import StepLogger

if TYPE_CHECKING:
    from collections.abc import Callable

    from full_test.client.system_client import SystemClient
    from full_test.seeders.config import FullTestConfig


class UserJourney(ABC):
    """Contrato basico que todas as journeys implementam.

    Subclasses devem:
      - Definir ``nome_journey`` (classvar) usado em logs e no resultado
      - Implementar ``setup``, ``executar``, ``teardown``
      - Usar ``self.log.passo(nome)`` para delimitar cada acao observavel
    """

    nome_journey: str = "UserJourney"

    def __init__(
        self,
        *,
        config: FullTestConfig,
        instance_id: str,
        system_client_factory: Callable[..., SystemClient] | None = None,
    ) -> None:
        self._config = config
        self._instance_id = instance_id
        self._system_client_factory: Callable[..., Any] | None = system_client_factory
        self.log = StepLogger(journey_name=self.nome_journey, instance_id=instance_id)

    @property
    def config(self) -> FullTestConfig:
        return self._config

    @property
    def instance_id(self) -> str:
        return self._instance_id

    @abstractmethod
    def setup(self) -> None:
        """Preparar o estado antes de executar.

        Ex.: login, cadastro de cliente proprio, registro de veiculo.
        """

    @abstractmethod
    def executar(self) -> None:
        """Executar o cenario principal."""

    @abstractmethod
    def teardown(self) -> None:
        """Liberar recursos (fechar httpx clients, revogar tokens)."""

    def rodar(self, *, timeout_s: float) -> ResultadoJourney:
        """Executa ``setup -> executar -> teardown`` com captura de falha.

        O parametro ``timeout_s`` nao e aplicado aqui: o orchestrator (step 13)
        roda ``rodar()`` dentro de
        ``ThreadPoolExecutor.submit(...).result(timeout=timeout_s)`` e, em
        timeout, retorna ``StatusJourney.TIMEOUT`` com a informacao
        disponivel. O valor fica exposto na assinatura para documentar a
        expectativa contratual com o chamador.

        A implementacao aqui so protege ``teardown`` de nao rodar em caso de
        falha: ``teardown`` e chamado mesmo quando ``setup``/``executar``
        levantam, e excecoes do teardown nao mascaram a falha original.
        """
        del timeout_s  # consumido pelo orchestrator, nao aqui
        inicio = datetime.now(UTC)
        status = StatusJourney.OK
        falha: str | None = None
        try:
            self.setup()
            self.executar()
        except Exception as exc:
            status = StatusJourney.FALHOU
            falha = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                self.teardown()
            except Exception as teardown_exc:
                if status == StatusJourney.OK:
                    status = StatusJourney.FALHOU
                    falha = f"teardown: {type(teardown_exc).__name__}: {teardown_exc}"

        fim = datetime.now(UTC)
        duracao_ms = int((fim - inicio).total_seconds() * 1000)
        return ResultadoJourney(
            journey_name=self.nome_journey,
            instance_id=self._instance_id,
            status=status,
            inicio=inicio,
            fim=fim,
            duracao_ms=duracao_ms,
            falha=falha,
            passos=self.log.passos(),
        )
