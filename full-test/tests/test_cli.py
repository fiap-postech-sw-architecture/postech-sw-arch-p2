"""Testes unitarios da CLI full_test."""

from __future__ import annotations

import pytest
from full_test.__main__ import _parser, main


def test_parser_healthwait_default_timeout() -> None:
    ns = _parser().parse_args(["healthwait"])
    assert ns.subcomando == "healthwait"
    assert ns.timeout == 60.0


def test_parser_healthwait_custom_timeout() -> None:
    ns = _parser().parse_args(["healthwait", "--timeout", "120"])
    assert ns.timeout == 120.0


def test_parser_run_plano_ci() -> None:
    ns = _parser().parse_args(["run", "--plano", "ci"])
    assert ns.plano == "ci"


def test_parser_run_plano_default_full() -> None:
    ns = _parser().parse_args(["run"])
    assert ns.plano == "full"


def test_parser_seed_reset_default_true() -> None:
    ns = _parser().parse_args(["seed"])
    assert ns.reset is True


def test_parser_seed_no_reset() -> None:
    ns = _parser().parse_args(["seed", "--no-reset"])
    assert ns.reset is False


def test_main_com_subcomando_invalido_sai_com_erro() -> None:
    with pytest.raises(SystemExit):
        main(["xyz"])
