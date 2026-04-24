"""Planos de execucao: composicao de journeys por modo.

Um ``PlanoDeExecucao`` lista ``DescritorDeJourney``s - cada descritor sabe como
instanciar uma journey (class + quantidade) e qual o timeout esperado. O
orchestrator (``executar.py``) expande descritores em instancias paralelas
atraves de ``construir_instancias`` (``builder.py``).

Dois planos pre-definidos:
  - ``plano_full``: conjunto completo, inclui ``ClienteFluxoCompletoJourney``
    (marcada como slowest no pytest entrypoint).
  - ``plano_ci``: sem ``ClienteFluxoCompletoJourney``; N reduzido. O owner do
    ``tempo_medio_execucao_minutos`` no modo CI e a ``MetricasFixtureJourney``.

Defaults derivados de ``full-e2e-test`` (secao "Run model e escala"):
  - full: 2N clientes (fluxo completo + alternativos) + operadores + admins +
    metricas + rbac; teto de 24 workers no pool.
  - ci: 1 alternativo x 2 cenarios + 1 op atendente + 1 op mecanico + 1 admin +
    metricas + rbac; teto de 8 workers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from full_test.journeys.base import UserJourney


@dataclass(frozen=True, slots=True)
class DescritorDeJourney:
    """Descricao de N instancias de uma journey no plano de execucao.

    ``journey_class`` identifica a subclasse de ``UserJourney`` que o
    ``builder`` sabe instanciar; ``n_instancias`` diz quantas copias paralelas
    criar; ``timeout_s`` e o limite duro aplicado por instancia no
    ``ThreadPoolExecutor`` (ver ``executar.py``).

    ``kwargs_comuns`` e um canal opcional para overrides em tempo de execucao.
    O builder consome-o junto com os recursos do seed - manter o dict vazio
    (default) delega todos os kwargs ao builder.
    """

    journey_class: type[UserJourney]
    n_instancias: int
    timeout_s: float
    kwargs_comuns: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanoDeExecucao:
    """Plano de execucao: nome + lista de descritores + tamanho do pool.

    ``max_workers`` limita o paralelismo real do ``ThreadPoolExecutor``. Pode
    ser menor que ``sum(d.n_instancias for d in descritores)``: nesse caso o
    pool serializa parcialmente, o que e desejavel quando o app nao suporta
    todos os clientes simultaneos.
    """

    nome: str
    descritores: tuple[DescritorDeJourney, ...]
    max_workers: int


def plano_full(n_clientes: int, n_operadores: int, n_admins: int) -> PlanoDeExecucao:
    """Plano completo: inclui ``ClienteFluxoCompletoJourney`` (slowest).

    Escala por ``N`` conforme configuracao; os limites foram derivados da
    tabela "Run model e escala" no orchestrator:
      - 2x n_clientes para o fluxo completo (cobre mais cenarios de cliente)
      - todos os 7 cenarios alternativos
      - n_operadores copias de ``atendente`` e ``mecanico``
      - n_admins copias do stress de concorrencia
      - 1x das journeys deterministicas (``metricas-fixture``, ``rbac-matrix``)
    """
    from full_test.journeys.admin_concurrency import AdminConcurrencyJourney
    from full_test.journeys.atendente import AtendenteJourney
    from full_test.journeys.cliente_fluxo_completo import ClienteFluxoCompletoJourney
    from full_test.journeys.cliente_fluxos_alternativos import (
        TODOS_CENARIOS,
        ClienteFluxosAlternativosJourney,
    )
    from full_test.journeys.mecanico import MecanicoJourney
    from full_test.journeys.metricas_fixture import MetricasFixtureJourney
    from full_test.journeys.rbac_matrix import RbacMatrixJourney

    # NOTA: ``ClienteFluxoCompletoJourney`` chama ``/acompanhamento`` (publico,
    # rate 10/min por IP) 6 vezes por instancia. Com N instancias em paralelo
    # temos N*6 chamadas concorrendo por 10 slots/min. Manter N = n_clientes
    # (antes era 2*n_clientes) mantem a janela de retry dentro do timeout de
    # 300s por journey.
    descritores = (
        DescritorDeJourney(ClienteFluxoCompletoJourney, n_clientes, timeout_s=300.0),
        DescritorDeJourney(
            ClienteFluxosAlternativosJourney, len(TODOS_CENARIOS), timeout_s=180.0
        ),
        DescritorDeJourney(AtendenteJourney, n_operadores, timeout_s=120.0),
        DescritorDeJourney(MecanicoJourney, n_operadores, timeout_s=120.0),
        DescritorDeJourney(AdminConcurrencyJourney, n_admins, timeout_s=180.0),
        DescritorDeJourney(MetricasFixtureJourney, 1, timeout_s=180.0),
        DescritorDeJourney(RbacMatrixJourney, 1, timeout_s=180.0),
    )
    total = sum(d.n_instancias for d in descritores)
    return PlanoDeExecucao(
        nome="full", descritores=descritores, max_workers=min(total, 24)
    )


def plano_ci(n_clientes: int, n_operadores: int, n_admins: int) -> PlanoDeExecucao:
    """Plano de CI: sem journeys com sleep obrigatorio (``slowest``).

    ``n_clientes`` nao e consumido diretamente - mantido na assinatura para
    paridade com ``plano_full`` e permitir troca simples na CLI. A cobertura
    de ``tempo_medio_execucao_minutos`` migra para ``MetricasFixtureJourney``
    que injeta timestamps no DB (trade-off documentado no README do harness).
    """
    del n_clientes  # nao consumido no modo CI; mantido para paridade
    from full_test.journeys.admin_concurrency import AdminConcurrencyJourney
    from full_test.journeys.atendente import AtendenteJourney
    from full_test.journeys.cliente_fluxos_alternativos import (
        TODOS_CENARIOS,
        ClienteFluxosAlternativosJourney,
    )
    from full_test.journeys.mecanico import MecanicoJourney
    from full_test.journeys.metricas_fixture import MetricasFixtureJourney
    from full_test.journeys.rbac_matrix import RbacMatrixJourney

    descritores = (
        # NAO inclui ClienteFluxoCompletoJourney (``slowest`` - sleeps reais).
        DescritorDeJourney(
            ClienteFluxosAlternativosJourney,
            min(len(TODOS_CENARIOS), 2),
            timeout_s=60.0,
        ),
        DescritorDeJourney(AtendenteJourney, min(n_operadores, 1), timeout_s=30.0),
        DescritorDeJourney(MecanicoJourney, min(n_operadores, 1), timeout_s=30.0),
        DescritorDeJourney(AdminConcurrencyJourney, min(n_admins, 1), timeout_s=60.0),
        DescritorDeJourney(MetricasFixtureJourney, 1, timeout_s=60.0),
        # RbacMatrix: 180 celulas + 3 logins descartaveis para /logout (um por
        # papel autenticado). Em rajada, os logins extras podem colidir com o
        # rate limit 5/min em /login — o retry com backoff ate 70s e suficiente,
        # mas o timeout global da journey precisa cobrir a janela inteira.
        DescritorDeJourney(RbacMatrixJourney, 1, timeout_s=180.0),
    )
    total = sum(d.n_instancias for d in descritores)
    return PlanoDeExecucao(
        nome="ci", descritores=descritores, max_workers=min(total, 8)
    )
