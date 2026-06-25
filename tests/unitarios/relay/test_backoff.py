from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from relay.backoff import (
    DELAYS_SEGUNDOS,
    MAX_TENTATIVAS,
    calcular_proxima_tentativa,
    deve_ir_para_dlq,
)


def test_delays_seguem_progressao_exponencial() -> None:
    assert DELAYS_SEGUNDOS == (1, 4, 16, 64, 256)
    assert MAX_TENTATIVAS == 5


@pytest.mark.parametrize(
    ("tentativas_apos_falha", "segundos"),
    [(1, 1), (2, 4), (3, 16), (4, 64), (5, 256)],
)
def test_proxima_tentativa_usa_delay_da_tentativa(
    tentativas_apos_falha: int, segundos: int
) -> None:
    agora = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    proxima = calcular_proxima_tentativa(tentativas_apos_falha, agora)
    assert proxima == agora + timedelta(seconds=segundos)


def test_deve_ir_para_dlq_quando_atinge_o_maximo() -> None:
    assert deve_ir_para_dlq(5) is True
    assert deve_ir_para_dlq(6) is True
    assert deve_ir_para_dlq(4) is False
