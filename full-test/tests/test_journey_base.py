"""Testes unitarios do contrato UserJourney + StepLogger."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from full_test.journeys.base import UserJourney
from full_test.journeys.resultado import StatusJourney

if TYPE_CHECKING:
    from full_test.seeders.config import FullTestConfig


@dataclass(frozen=True, slots=True)
class _CfgFake:
    base_url: str = "http://test"
    database_url: str = "postgresql://test"
    admin_email: str = "a@b.c"
    admin_password: str = "x" * 12
    n_clientes: int = 1
    n_operadores: int = 1
    n_admins: int = 1
    http_timeout: float = 5.0
    seed: int | None = None


class _JourneyDummyOk(UserJourney):
    nome_journey = "dummy-ok"

    def setup(self) -> None:
        with self.log.passo("setup"):
            pass

    def executar(self) -> None:
        with self.log.passo("executar-passo-1"):
            pass
        with self.log.passo("executar-passo-2"):
            pass

    def teardown(self) -> None:
        with self.log.passo("teardown"):
            pass


class _JourneyDummyFalha(UserJourney):
    nome_journey = "dummy-falha"

    def setup(self) -> None:
        pass

    def executar(self) -> None:
        with self.log.passo("vai-explodir"):
            raise ValueError("explodi no meio")

    def teardown(self) -> None:
        pass


class _JourneyDummyFalhaTeardown(UserJourney):
    nome_journey = "dummy-teardown"

    def setup(self) -> None:
        pass

    def executar(self) -> None:
        pass

    def teardown(self) -> None:
        raise RuntimeError("teardown falhou")


@pytest.fixture
def config_fake() -> FullTestConfig:
    return _CfgFake()  # type: ignore[return-value]


def test_journey_ok_retorna_status_ok(config_fake: FullTestConfig) -> None:
    j = _JourneyDummyOk(config=config_fake, instance_id="001")
    resultado = j.rodar(timeout_s=10.0)
    assert resultado.status == StatusJourney.OK
    assert resultado.falha is None
    assert [p.nome for p in resultado.passos] == [
        "setup",
        "executar-passo-1",
        "executar-passo-2",
        "teardown",
    ]
    assert all(p.sucesso for p in resultado.passos)


def test_journey_falha_no_executar_captura_erro(config_fake: FullTestConfig) -> None:
    j = _JourneyDummyFalha(config=config_fake, instance_id="001")
    resultado = j.rodar(timeout_s=10.0)
    assert resultado.status == StatusJourney.FALHOU
    assert resultado.falha is not None
    assert "explodi no meio" in resultado.falha
    passo_que_falhou = next(p for p in resultado.passos if p.nome == "vai-explodir")
    assert not passo_que_falhou.sucesso
    assert passo_que_falhou.erro is not None


def test_journey_falha_no_teardown_marca_falhou_se_executar_ok(
    config_fake: FullTestConfig,
) -> None:
    j = _JourneyDummyFalhaTeardown(config=config_fake, instance_id="001")
    resultado = j.rodar(timeout_s=10.0)
    assert resultado.status == StatusJourney.FALHOU
    assert resultado.falha is not None
    assert "teardown" in resultado.falha


def test_para_dict_serializa_em_tipos_primitivos(
    config_fake: FullTestConfig,
) -> None:
    j = _JourneyDummyOk(config=config_fake, instance_id="001")
    resultado = j.rodar(timeout_s=10.0)
    d = resultado.para_dict()
    # tudo deve ser JSON-serializavel
    json.dumps(d)  # nao deve levantar


def test_step_logger_grava_correlation_id(config_fake: FullTestConfig) -> None:
    class _JourneyCorr(UserJourney):
        nome_journey = "dummy-corr"

        def setup(self) -> None:
            pass

        def executar(self) -> None:
            with self.log.passo("p1", correlation_id="abc-123"):
                pass

        def teardown(self) -> None:
            pass

    j = _JourneyCorr(config=config_fake, instance_id="001")
    resultado = j.rodar(timeout_s=10.0)
    passo = next(p for p in resultado.passos if p.nome == "p1")
    assert passo.correlation_id == "abc-123"
