"""Health-wait: aguarda ``GET /api/v1/saude`` responder 200 antes de seed/run.

Uso:
    wait_for_saude(base_url="http://localhost:8000", timeout_s=60)

Sobe docker compose e imediatamente pular para seeding e' uma das fontes mais
comuns de flakiness — este helper garante que o app esta pronto.
"""

from __future__ import annotations

import time

import httpx


def wait_for_saude(
    *,
    base_url: str,
    timeout_s: float = 60.0,
    poll_interval_s: float = 1.0,
) -> None:
    """Blocking: pesquisa ``/api/v1/saude`` ate 200 ou timeout.

    Raises:
        TimeoutError: se nao ficou OK em ``timeout_s`` segundos.
    """
    deadline = time.monotonic() + timeout_s
    ultimo_erro: Exception | None = None
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get("/api/v1/saude")
                if response.status_code == 200:
                    return
                ultimo_erro = RuntimeError(
                    f"status {response.status_code}: {response.text[:200]}"
                )
            except httpx.HTTPError as exc:
                ultimo_erro = exc
            time.sleep(poll_interval_s)
    raise TimeoutError(
        f"/api/v1/saude nao ficou OK em {timeout_s}s. Ultimo erro: {ultimo_erro!r}"
    )
