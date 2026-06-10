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


@pytest.fixture(scope="session")
def seed_recursos() -> dict[str, Any]:
    """Reseta DB, seeda usuarios + catalogo + estoque; retorna dict consumido pelo orchestrator.

    Escopo de sessao — roda UMA vez por invocacao do pytest. Se varios testes
    da suite precisarem do mesmo seed, compartilham.
    """  # noqa: E501 - docstring descritiva; quebrar a primeira linha prejudica clareza
    from full_test.seeders.orquestrar import seed_completo

    # Permite desabilitar reset em ambiente onde o DB ja esta limpo
    # (ex.: CI com fresh docker).
    resetar = os.environ.get("FULL_TEST_RESET_ANTES_DE_SEED", "1") == "1"
    return seed_completo(resetar=resetar)


@pytest.fixture(scope="session")
def config() -> FullTestConfig:
    from full_test.seeders.config import carregar_config

    return carregar_config()
