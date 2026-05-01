from __future__ import annotations

import subprocess
import sys
from importlib.util import find_spec

import pytest

# Carrega o plugin Screen do NiceGUI apenas quando selenium + pytest-selenium
# estao disponiveis. Permite rodar `pytest -m "not lento"` sem instalar browser
# drivers. Para rodar testes marcados `lento` que usam `screen`, use
# `make test-lento` ou `uv run --extra test --extra ui pytest -m lento`.
if find_spec("selenium") is not None and find_spec("pytest_selenium") is not None:
    pytest_plugins = ["nicegui.testing.plugin"]


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    from src.compartilhado.interfaces.middleware import limiter

    limiter.reset()


def pytest_sessionstart(session: pytest.Session) -> None:
    if getattr(session.config.option, "collectonly", False):
        return
    if not session.config.getoption("--no-lint", default=False):
        _run_pre_checks()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-lint",
        action="store_true",
        default=False,
        help="Skip ruff/mypy/bandit pre-checks before tests",
    )


def _run_pre_checks() -> None:
    py = sys.executable
    checks = [
        ("ruff check", [py, "-m", "ruff", "check", "src/", "tests/"]),
        (
            "ruff format",
            [py, "-m", "ruff", "format", "--check", "src/", "tests/"],
        ),
        ("mypy", [py, "-m", "mypy", "src/"]),
        (
            "bandit",
            [
                py,
                "-m",
                "bandit",
                "-r",
                "src/",
                "-c",
                "pyproject.toml",
                "--severity-level",
                "high",
                "-q",
            ],
        ),
    ]
    for name, cmd in checks:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"\n{'=' * 60}")
            print(f"PRE-CHECK FAILED: {name}")
            print(f"{'=' * 60}")
            if result.stdout:
                print(result.stdout[:2000])
            if result.stderr:
                print(result.stderr[:500])
            msg = f"{name} failed (use --no-lint to skip)"
            pytest.exit(msg, returncode=1)
