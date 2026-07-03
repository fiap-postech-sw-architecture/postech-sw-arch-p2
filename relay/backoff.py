"""Politica de retry/backoff e DLQ do relay (RF-018).

Backoff exponencial fixo: apos a N-esima falha, a proxima tentativa e
agendada para ``now + DELAYS_SEGUNDOS[N-1]`` (1s, 4s, 16s, 64s, 256s).
Ao atingir ``MAX_TENTATIVAS`` (5) sem sucesso, a linha vai para a DLQ
(``status='dead'``). Modulo puro — sem I/O — para teste deterministico.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

DELAYS_SEGUNDOS: tuple[int, ...] = (1, 4, 16, 64, 256)
MAX_TENTATIVAS: int = 5


def calcular_proxima_tentativa(tentativas: int, agora: datetime) -> datetime:
    """Agenda a proxima tentativa apos ``tentativas`` falhas acumuladas.

    ``tentativas`` e a contagem JA incrementada da falha corrente (1-based):
    a primeira falha (tentativas=1) espera ``DELAYS_SEGUNDOS[0]``. Para
    valores alem da tabela, usa o ultimo delay (256s) — defensivo, embora
    ``deve_ir_para_dlq`` ja desvie esses casos para a DLQ. Piso em 1
    (tambem defensivo): um caller errado com ``tentativas=0`` cai no primeiro
    delay, em vez de o indice -1 devolver silenciosamente o ULTIMO (256s).
    """
    indice = min(max(tentativas, 1), len(DELAYS_SEGUNDOS)) - 1
    return agora + timedelta(seconds=DELAYS_SEGUNDOS[indice])


def deve_ir_para_dlq(tentativas: int) -> bool:
    """Indica se a linha esgotou as tentativas e deve virar ``dead``."""
    return tentativas >= MAX_TENTATIVAS
