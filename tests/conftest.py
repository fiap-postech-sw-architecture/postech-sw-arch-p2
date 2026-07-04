from __future__ import annotations

from importlib.util import find_spec

import pytest

# Carrega o plugin Screen do NiceGUI apenas quando selenium + pytest-selenium
# estao disponiveis. Permite rodar `pytest -m "not lento"` sem instalar browser
# drivers. Para rodar testes marcados `lento` que usam `screen`, use
# `make test-lento` ou `uv run --extra test --extra ui pytest -m lento`.
if find_spec("selenium") is not None and find_spec("pytest_selenium") is not None:
    # codeql[py/unused-global-variable] -- pytest_plugins lido por reflexao
    pytest_plugins = ["nicegui.testing.plugin"]


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    from src.compartilhado.interfaces.middleware import limiter

    limiter.reset()


@pytest.fixture(autouse=True)
def _reset_encryption_singleton() -> None:
    # Sem o reset, o primeiro teste da sessao que tocar o servico congela a
    # ENCRYPTION_KEY vigente para todos os seguintes (order-dependence latente,
    # TD-032/issue #127 -- mesma classe do gotcha cache_logger_on_first_use).
    from src.compartilhado.infraestrutura.encryption import EncryptionService

    EncryptionService._instance = None


# Nota: os pre-checks de lint (`pytest_sessionstart` + flag `--no-lint`)
# foram REMOVIDOS: todos os entry points sancionados (Makefile e CI) pulavam
# os checks com `--no-lint`, entao o codigo era peso morto — o gate real de
# lint/type/security e `make check` (e os jobs dedicados do CI).
