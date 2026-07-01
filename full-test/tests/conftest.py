"""Fixtures compartilhadas pelo harness.

Diferente do conftest.py do ``tests/`` (unit/integracao), este vive isolado em
``full-test/tests/`` — nao importa nem e importado pelas suites principais.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig

# Sinaliza para o resumo final que o harness foi pulado por stack fora do ar.
_pulou_por_stack = False
_base_url_esperada = ""

_AVISO_STACK_LINHAS = (
    "O harness full-test roda contra a STACK compose de pe (app + Postgres) e",
    "ela NAO esta respondendo em {base_url} agora.",
    "",
    "  ->  Os testes do harness foram PULADOS (nao falharam). Para roda-los,",
    "      suba a stack (precisa de um daemon Docker: colima start / Docker",
    "      Desktop) e repita:",
    "        make full-test-up      # sobe o compose + espera health",
    "        make full-test-run     # ou full-test-ci: executa as journeys",
    "",
    "  As suites unit/integracao NAO dependem desta stack.",
)


def _stack_no_ar(base_url: str) -> bool:
    """True se a app responde 200 em ``/api/v1/saude`` (stack compose de pe)."""
    try:
        import httpx

        resposta = httpx.get(f"{base_url}/api/v1/saude", timeout=5)
        return resposta.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def config() -> FullTestConfig:
    from full_test.seeders.config import carregar_config

    return carregar_config()


@pytest.fixture(scope="session")
def seed_recursos(config: FullTestConfig) -> dict[str, Any]:
    """Reseta DB, seeda usuarios + catalogo + estoque; retorna dict consumido pelo orchestrator.

    Escopo de sessao — roda UMA vez por invocacao do pytest. Se varios testes
    da suite precisarem do mesmo seed, compartilham. Se a stack compose nao
    estiver de pe, PULA (skip) com um aviso destacado em vez de estourar um
    erro de conexao — assim quem rodar sabe que precisa subir a stack.
    """  # noqa: E501 - docstring descritiva; quebrar a primeira linha prejudica clareza
    if not _stack_no_ar(config.base_url):
        global _pulou_por_stack, _base_url_esperada
        _pulou_por_stack = True
        _base_url_esperada = config.base_url
        pytest.skip(
            "Stack do full-test indisponivel — harness pulado "
            "(veja o aviso destacado no fim da sessao)."
        )

    from full_test.seeders.orquestrar import seed_completo

    # Permite desabilitar reset em ambiente onde o DB ja esta limpo
    # (ex.: CI com fresh docker).
    resetar = os.environ.get("FULL_TEST_RESET_ANTES_DE_SEED", "1") == "1"
    return seed_completo(resetar=resetar)


def pytest_terminal_summary(terminalreporter: object) -> None:
    """Aviso destacado no fim da sessao se o harness foi pulado por stack fora do ar."""
    if not _pulou_por_stack:
        return
    tr = terminalreporter
    tr.write_sep(  # type: ignore[attr-defined]
        "=", "ACAO NECESSARIA: stack do full-test nao esta de pe", red=True, bold=True
    )
    for linha in _AVISO_STACK_LINHAS:
        tr.write_line(  # type: ignore[attr-defined]
            "  " + linha.format(base_url=_base_url_esperada), yellow=True
        )
    tr.write_sep("=", "", red=True, bold=True)  # type: ignore[attr-defined]
