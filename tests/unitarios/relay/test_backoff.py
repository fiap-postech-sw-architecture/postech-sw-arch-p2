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


def test_tentativas_zero_usa_o_primeiro_delay_e_nao_o_ultimo() -> None:
    # Defensivo: `tentativas` e 1-based (a falha corrente ja incrementou), mas
    # um caller errado com 0 nao pode cair no indice -1 — que devolveria
    # silenciosamente o ULTIMO delay (256s) em vez do primeiro (1s).
    agora = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
    assert calcular_proxima_tentativa(0, agora) == agora + timedelta(seconds=1)


def test_deve_ir_para_dlq_quando_atinge_o_maximo() -> None:
    assert deve_ir_para_dlq(5) is True
    assert deve_ir_para_dlq(6) is True
    assert deve_ir_para_dlq(4) is False
