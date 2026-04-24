"""Testes unitarios do ``MetricasFixtureJourney``: logica pura + estrutura.

Nao ha testes com DB/API mocks aqui - a fixture de override de timestamps so
faz sentido contra um Postgres real, e o caminho completo (fabricar ordens +
override + validar agregacao) e exercido pelo entrypoint pytest do harness
(step 14) contra a instancia viva. Estes testes validam apenas:

  1. que a media aritmetica das duracoes alvo e o valor documentado no
     docstring da journey (69.0 minutos)
  2. que nenhuma duracao alvo e zero (impediria o delta observado)
  3. que temos amostras suficientes para a media nao depender de outliers
  4. que o helper ``_tempo_medio_esperado`` lida com historico vazio e
     com historico pre-existente (ponderacao)
"""

from __future__ import annotations

from full_test.journeys.metricas_fixture import (
    _DURACOES_ALVO_MIN,
    MetricasFixtureJourney,
)


def test_duracoes_geram_media_conhecida() -> None:
    """A media aritmetica de ``_DURACOES_ALVO_MIN`` bate com o docstring."""
    esperado = 69.0  # (30+45+60+90+120)/5
    assert abs(sum(_DURACOES_ALVO_MIN) / len(_DURACOES_ALVO_MIN) - esperado) < 0.01


def test_duracoes_nao_tem_zero() -> None:
    """Duracao zero implicaria media degenerada. Garantir contrato util."""
    assert all(d > 0 for d in _DURACOES_ALVO_MIN)


def test_pelo_menos_cinco_amostras() -> None:
    """Menos de 5 amostras tornaria a media muito sensivel a outliers."""
    assert len(_DURACOES_ALVO_MIN) >= 5


def test_tempo_medio_esperado_sem_historico() -> None:
    """Sem ordens finalizadas anteriores, usa a media aritmetica das injetadas."""
    esperado = MetricasFixtureJourney._tempo_medio_esperado(
        tempo_medio_anterior=None,
        total_anterior_finalizadas=0,
        duracoes_injetadas=_DURACOES_ALVO_MIN,
    )
    assert abs(esperado - 69.0) < 0.01


def test_tempo_medio_esperado_com_historico_pondera() -> None:
    """Com historico, a media e ponderada: (hist * N_hist + Σ injetadas) / total."""
    # 10 ordens anteriores com media 20min + 5 ordens com duracoes alvo (soma 345)
    # esperado = (20 * 10 + 345) / (10 + 5) = 545 / 15 ~= 36.333
    esperado = MetricasFixtureJourney._tempo_medio_esperado(
        tempo_medio_anterior=20.0,
        total_anterior_finalizadas=10,
        duracoes_injetadas=_DURACOES_ALVO_MIN,
    )
    assert abs(esperado - (545.0 / 15.0)) < 0.01
