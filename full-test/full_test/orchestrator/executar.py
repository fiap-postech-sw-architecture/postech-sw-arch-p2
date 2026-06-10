"""ParallelOrchestrator: executa um ``PlanoDeExecucao`` com ThreadPoolExecutor.

Contrato:
  - ``executar(plano, recursos_seed)`` monta todas as instancias de journey
    via ``builder.construir_instancias``, submete ao pool, coleta resultados,
    agrega em ``ResultadoAgregado`` (JSON-ready).
  - Cada future tem ``timeout_s`` individual; em timeout, marca a journey
    como ``StatusJourney.TIMEOUT`` e CONTINUA (collect-all, nao fail-fast).
  - Excecoes inesperadas (fora do protocolo ``UserJourney.rodar``) viram
    ``StatusJourney.FALHOU`` com mensagem tecnica; apenas ``KeyboardInterrupt``
    e ``SystemExit`` nao sao capturados.

Semantica de falha:
  - "Collect-all": toda journey roda ate completar ou estourar o timeout
    individual. Cada ``future.result(timeout=...)`` bloqueia ate a journey
    daquele slot terminar (ou bater no ``timeout_s + folga``). Journeys que
    rodam em paralelo ja tem seus resultados prontos enquanto esperamos a
    mais lenta - nenhum resultado e perdido.
  - Escolha de ORDEM DE SUBMISSAO (em vez de ``as_completed``): ambas as
    estrategias suportam timeout-por-future (``as_completed(..., timeout=)``
    tambem funciona); mas ordem de submissao e mais simples de auditar e
    associar cada resultado ao descritor/indice correspondente, porque
    mantemos o mapeamento direto ``futures[i] -> inst[i]``.

Thread-safety:
  - Cada journey tem seu proprio ``StepLogger`` + ``SystemClient``. O
    orchestrator nao compartilha estado mutavel entre threads. Apenas
    ``recursos_seed`` (dict imutavel apos o seed) e lido concorrentemente.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from full_test.journeys.resultado import ResultadoJourney, StatusJourney

if TYPE_CHECKING:
    from full_test.orchestrator.planos import PlanoDeExecucao
    from full_test.seeders.config import FullTestConfig


# Folga aplicada ao ``timeout_s`` de cada journey antes de desistir do future:
# garante que, quando a propria ``rodar()`` ultrapassa o limite, o worker pode
# terminar o ciclo de ``teardown`` antes de o orchestrator marcar TIMEOUT.
_FOLGA_TIMEOUT_S = 5.0


@dataclass(frozen=True, slots=True)
class ResumoAgregado:
    """Estatisticas compactas para relatorio rapido."""

    total: int
    ok: int
    falhou: int
    timeout: int
    duracao_total_s: float


@dataclass(slots=True)
class ResultadoAgregado:
    """Payload final de uma execucao do orchestrator.

    ``para_dict`` gera uma estrutura JSON-serializavel que o pytest
    entrypoint (step 14) escreve em ``full-test/reports/<timestamp>.json``.
    ``sucesso`` e o predicado usado para decidir se o teste pytest agregador
    passa ou falha.
    """

    plano: str
    inicio: datetime
    fim: datetime
    resumo: ResumoAgregado
    resultados: list[ResultadoJourney] = field(default_factory=list)

    def para_dict(self) -> dict[str, Any]:
        return {
            "plano": self.plano,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat(),
            "resumo": {
                "total": self.resumo.total,
                "ok": self.resumo.ok,
                "falhou": self.resumo.falhou,
                "timeout": self.resumo.timeout,
                "duracao_total_s": self.resumo.duracao_total_s,
            },
            "resultados": [r.para_dict() for r in self.resultados],
        }

    def sucesso(self) -> bool:
        return self.resumo.falhou == 0 and self.resumo.timeout == 0


class ParallelOrchestrator:
    """Executa um ``PlanoDeExecucao`` com pool de threads.

    Nao mantem estado entre execucoes: pode ser chamado varias vezes com
    planos diferentes. Cada chamada a ``executar`` abre e fecha seu proprio
    ``ThreadPoolExecutor``.
    """

    def __init__(self, *, config: FullTestConfig) -> None:
        self._config = config

    def executar(
        self,
        plano: PlanoDeExecucao,
        *,
        recursos_seed: dict[str, Any],
    ) -> ResultadoAgregado:
        """Executa o plano com ``ThreadPoolExecutor`` e agrega resultados.

        ``recursos_seed`` e o dict retornado por
        ``seeders.orquestrar.seed_completo()``:
          - ``credenciais``: ``list[CredencialSeed]`` (inclui admin/atendente/mecanico)
          - ``servicos``: ``list[ServicoResponse]``
          - ``itens_estoque``: ``list[ItemEstoqueResponse]``

        O builder consome esse dict para extrair IDs e credenciais reais.
        """
        from full_test.orchestrator.builder import construir_instancias

        instancias = construir_instancias(
            plano=plano, config=self._config, recursos_seed=recursos_seed
        )

        inicio = datetime.now(UTC)
        resultados: list[ResultadoJourney] = []

        with ThreadPoolExecutor(
            max_workers=plano.max_workers,
            thread_name_prefix=f"ft-{plano.nome}",
        ) as pool:
            futures = {
                pool.submit(inst["journey"].rodar, timeout_s=inst["timeout_s"]): inst
                for inst in instancias
            }
            # Iteramos em ordem de submissao com ``result(timeout=...)``
            # individual. Enquanto esperamos a mais lenta, as rapidas ja
            # estao terminadas no pool e ``result()`` retorna imediato
            # quando chegar a vez delas. Trocar por ``as_completed`` faria
            # o orchestrator perder a capacidade de marcar uma journey
            # como TIMEOUT (o iterador so emite futures DEPOIS que terminam).
            for future, inst in futures.items():
                timeout_s: float = inst["timeout_s"]
                journey = inst["journey"]
                try:
                    resultado = future.result(timeout=timeout_s + _FOLGA_TIMEOUT_S)
                    resultados.append(resultado)
                except FuturesTimeout:
                    resultados.append(
                        ResultadoJourney(
                            journey_name=journey.nome_journey,
                            instance_id=journey.instance_id,
                            status=StatusJourney.TIMEOUT,
                            inicio=inicio,
                            fim=datetime.now(UTC),
                            duracao_ms=int(timeout_s * 1000),
                            falha=f"timeout apos {timeout_s}s",
                        )
                    )
                except Exception as exc:
                    # Capturar excecoes inesperadas e converter em FALHOU e
                    # deliberado: se ``rodar()`` tem um bug que vaza excecao
                    # sem traduzir em ``ResultadoJourney``, nao queremos
                    # derrubar a coleta das outras journeys.
                    resultados.append(
                        ResultadoJourney(
                            journey_name=journey.nome_journey,
                            instance_id=journey.instance_id,
                            status=StatusJourney.FALHOU,
                            inicio=inicio,
                            fim=datetime.now(UTC),
                            duracao_ms=0,
                            falha=f"orchestrator: {type(exc).__name__}: {exc}",
                        )
                    )

        fim = datetime.now(UTC)
        resumo = ResumoAgregado(
            total=len(resultados),
            ok=sum(1 for r in resultados if r.status == StatusJourney.OK),
            falhou=sum(1 for r in resultados if r.status == StatusJourney.FALHOU),
            timeout=sum(1 for r in resultados if r.status == StatusJourney.TIMEOUT),
            duracao_total_s=(fim - inicio).total_seconds(),
        )
        return ResultadoAgregado(
            plano=plano.nome,
            inicio=inicio,
            fim=fim,
            resumo=resumo,
            resultados=resultados,
        )
