from __future__ import annotations

from datetime import timedelta

from relay.listener import _config_do_ambiente


def test_config_le_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OUTBOX_POLL_SEGUNDOS", raising=False)
    monkeypatch.delenv("OUTBOX_LOTE", raising=False)
    monkeypatch.delenv("OUTBOX_LEASE_SEGUNDOS", raising=False)
    poll, lote, lease = _config_do_ambiente()
    assert poll == 5.0
    assert lote == 10  # default pequeno (F3): limita a janela de duplicacao
    assert lease == timedelta(seconds=60)


def test_config_le_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OUTBOX_POLL_SEGUNDOS", "2")
    monkeypatch.setenv("OUTBOX_LOTE", "25")
    monkeypatch.setenv("OUTBOX_LEASE_SEGUNDOS", "90")
    poll, lote, lease = _config_do_ambiente()
    assert poll == 2.0
    assert lote == 25
    assert lease == timedelta(seconds=90)
