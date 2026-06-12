"""Testes unitarios das funcoes auxiliares do entrypoint pytest.

O entrypoint (``test_parallel_usage.py``) contem dois testes principais que
dependem de instancia viva. Estes unit tests exercitam apenas as funcoes
auxiliares privadas (``_registrar_relatorio``, ``_falhar_com_resumo``) sem
disparar as fixtures ``config`` + ``seed_recursos``.

A importacao usa ``importlib.util.spec_from_file_location`` para evitar
qualquer dependencia no layout de pacotes sob ``pytest`` (o modulo vive em
``full-test/tests/``, que nao e um subpacote de ``full_test``).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest
from full_test.journeys.resultado import ResultadoJourney, StatusJourney
from full_test.orchestrator.executar import ResultadoAgregado, ResumoAgregado


def _carregar_modulo_entrypoint() -> ModuleType:
    """Carrega ``test_parallel_usage.py`` como modulo isolado via importlib.

    Pytest ja descobre esse arquivo como teste; aqui precisamos dele tambem
    como modulo normal para chamar ``_registrar_relatorio`` e
    ``_falhar_com_resumo`` diretamente.
    """
    caminho = Path(__file__).resolve().parent / "test_parallel_usage.py"
    nome_modulo = "full_test_entrypoint_sob_teste"
    if nome_modulo in sys.modules:
        return sys.modules[nome_modulo]
    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    if spec is None or spec.loader is None:
        msg = f"nao foi possivel carregar {caminho}"
        raise RuntimeError(msg)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _agregado_fake(falhou: int = 0, timeout: int = 0, ok: int = 1) -> ResultadoAgregado:
    total = falhou + timeout + ok
    resultados: list[ResultadoJourney] = []
    agora = datetime.now(UTC)

    for i in range(ok):
        resultados.append(
            ResultadoJourney(
                journey_name="j",
                instance_id=f"ok-{i}",
                status=StatusJourney.OK,
                inicio=agora,
                fim=agora,
                duracao_ms=100,
                falha=None,
            )
        )
    for i in range(falhou):
        resultados.append(
            ResultadoJourney(
                journey_name="j",
                instance_id=f"fa-{i}",
                status=StatusJourney.FALHOU,
                inicio=agora,
                fim=agora,
                duracao_ms=100,
                falha=f"boom-{i}",
            )
        )
    for i in range(timeout):
        resultados.append(
            ResultadoJourney(
                journey_name="j",
                instance_id=f"to-{i}",
                status=StatusJourney.TIMEOUT,
                inicio=agora,
                fim=agora,
                duracao_ms=100,
                falha="timeout",
            )
        )

    return ResultadoAgregado(
        plano="teste",
        inicio=agora,
        fim=agora,
        resumo=ResumoAgregado(
            total=total,
            ok=ok,
            falhou=falhou,
            timeout=timeout,
            duracao_total_s=0.1,
        ),
        resultados=resultados,
    )


def test_registrar_relatorio_cria_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _carregar_modulo_entrypoint()
    monkeypatch.setattr(mod, "_REPORTS_DIR", tmp_path)
    agregado = _agregado_fake(ok=2)
    destino = mod._registrar_relatorio(agregado, "teste")
    assert destino.exists()
    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert dados["plano"] == "teste"
    assert dados["resumo"]["ok"] == 2


def test_falhar_com_resumo_sucesso_nao_levanta() -> None:
    mod = _carregar_modulo_entrypoint()
    agregado = _agregado_fake(ok=2)
    mod._falhar_com_resumo(agregado)  # nao deve levantar


def test_falhar_com_resumo_com_falhas_levanta() -> None:
    mod = _carregar_modulo_entrypoint()
    agregado = _agregado_fake(ok=1, falhou=2, timeout=1)
    with pytest.raises(AssertionError, match="Plano 'teste' teve 2 falhas"):
        mod._falhar_com_resumo(agregado)
