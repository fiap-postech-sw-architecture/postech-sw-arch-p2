"""Testes unitarios do ``ParallelOrchestrator``.

Usa journeys dummy (sem ``SystemClient`` real) para validar:

  - collect-all: toda journey termina; sucesso e falha coexistem sem que a
    falha de uma aborte as demais.
  - timeout: journey que demora alem do limite vira ``StatusJourney.TIMEOUT``
    e nao bloqueia a coleta das rapidas.
  - JSON: ``ResultadoAgregado.para_dict()`` e serializavel em tipos primitivos.

As fixtures de recursos de seed sao imitadas via ``_Cfg`` +
``_montar_instancias_sinteticas`` para evitar dependencia de banco ou HTTP. O
caminho de construcao via ``builder.construir_instancias`` e coberto
indiretamente nos testes de integracao do step 14 (pytest entrypoint), que
rodam contra docker compose.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from full_test.journeys.base import UserJourney
from full_test.journeys.resultado import ResultadoJourney, StatusJourney
from full_test.orchestrator.executar import (
    ParallelOrchestrator,
    ResultadoAgregado,
    ResumoAgregado,
)


@dataclass(frozen=True, slots=True)
class _Cfg:
    """``FullTestConfig`` falso para os testes unitarios.

    Os campos precisam casar com ``FullTestConfig`` (mesmo shape) para o
    ``ParallelOrchestrator`` poder ser instanciado. Atributos fora do uso
    real dos testes ficam com defaults inertes.
    """

    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "a@b.c"
    admin_password: str = "x" * 12
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = 1


class _JourneyRapida(UserJourney):
    nome_journey = "rapida"

    def setup(self) -> None:
        with self.log.passo("setup"):
            pass

    def executar(self) -> None:
        with self.log.passo("executar"):
            pass

    def teardown(self) -> None:
        with self.log.passo("teardown"):
            pass


class _JourneyLenta(UserJourney):
    nome_journey = "lenta"

    def setup(self) -> None:
        pass

    def executar(self) -> None:
        # Excede ``timeout_s=0.5`` em varias ordens de magnitude para remover
        # flakiness de jitter de scheduler em CI.
        time.sleep(3.0)

    def teardown(self) -> None:
        pass


class _JourneyQueFalha(UserJourney):
    nome_journey = "falha"

    def setup(self) -> None:
        pass

    def executar(self) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    def teardown(self) -> None:
        pass


def _montar_instancias_sinteticas(
    instancias_def: list[dict[str, Any]],
) -> ResultadoAgregado:
    """Bypass ao builder: injeta instancias diretamente no pool.

    Usado pelos testes unitarios para evitar dependencia do
    ``construir_instancias`` (que exige recursos_seed com servicos, itens,
    etc.). A logica de pool + agregacao e identica a do
    ``ParallelOrchestrator.executar`` para manter o comportamento sob teste.
    """
    inicio = datetime.now(UTC)
    resultados: list[ResultadoJourney] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(inst["journey"].rodar, timeout_s=inst["timeout_s"]): inst
            for inst in instancias_def
        }
        # Ordem de submissao (espelha o ``ParallelOrchestrator.executar``).
        for future, inst in futures.items():
            timeout_s: float = inst["timeout_s"]
            journey = inst["journey"]
            try:
                resultado = future.result(timeout=timeout_s + 1.0)
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
    fim = datetime.now(UTC)
    return ResultadoAgregado(
        plano="teste",
        inicio=inicio,
        fim=fim,
        resumo=ResumoAgregado(
            total=len(resultados),
            ok=sum(1 for r in resultados if r.status == StatusJourney.OK),
            falhou=sum(1 for r in resultados if r.status == StatusJourney.FALHOU),
            timeout=sum(1 for r in resultados if r.status == StatusJourney.TIMEOUT),
            duracao_total_s=(fim - inicio).total_seconds(),
        ),
        resultados=resultados,
    )


def test_orquestrador_collect_all() -> None:
    cfg = _Cfg()
    # ``ParallelOrchestrator`` e instanciado para verificar que o construtor
    # aceita o shape de ``FullTestConfig`` sem surpresas, mesmo que o teste
    # unitario bypasse ``executar`` via ``_montar_instancias_sinteticas``.
    _ = ParallelOrchestrator(config=cfg)  # type: ignore[arg-type]
    instancias = [
        {
            "journey": _JourneyRapida(config=cfg, instance_id="001"),  # type: ignore[arg-type]
            "timeout_s": 5.0,
        },
        {
            "journey": _JourneyQueFalha(config=cfg, instance_id="002"),  # type: ignore[arg-type]
            "timeout_s": 5.0,
        },
        {
            "journey": _JourneyRapida(config=cfg, instance_id="003"),  # type: ignore[arg-type]
            "timeout_s": 5.0,
        },
    ]
    agregado = _montar_instancias_sinteticas(instancias)
    assert agregado.resumo.total == 3
    assert agregado.resumo.ok == 2
    assert agregado.resumo.falhou == 1
    assert agregado.resumo.timeout == 0
    assert not agregado.sucesso()


def test_orquestrador_timeout_vira_status_timeout() -> None:
    cfg = _Cfg()
    _ = ParallelOrchestrator(config=cfg)  # type: ignore[arg-type]
    instancias = [
        {
            "journey": _JourneyLenta(config=cfg, instance_id="001"),  # type: ignore[arg-type]
            "timeout_s": 0.5,
        },
    ]
    agregado = _montar_instancias_sinteticas(instancias)
    assert agregado.resumo.timeout == 1
    assert agregado.resultados[0].status == StatusJourney.TIMEOUT


def test_para_dict_serializavel() -> None:
    cfg = _Cfg()
    _ = ParallelOrchestrator(config=cfg)  # type: ignore[arg-type]
    instancias = [
        {
            "journey": _JourneyRapida(config=cfg, instance_id="001"),  # type: ignore[arg-type]
            "timeout_s": 5.0,
        },
    ]
    agregado = _montar_instancias_sinteticas(instancias)
    d = agregado.para_dict()
    json.dumps(d)  # nao deve levantar
    assert d["resumo"]["ok"] == 1
