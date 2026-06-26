from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import structlog.testing
from sqlalchemy.exc import OperationalError

import relay.listener as listener_mod
from relay.listener import _config_do_ambiente, executar_relay


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


# --- Resiliencia por ciclo (F6/operacao) ------------------------------------
#
# Um erro transitorio de DB no drain NAO pode derrubar o relay (derrubar
# reinicia o pod e desmonta o LISTEN a cada blip). O loop deve logar
# `outbox_ciclo_falhou` e CONTINUAR; o teste injeta um `processar_ciclo` que
# levanta UMA vez e prova que o ciclo seguinte roda e o loop encerra via
# `parar` (sem propagar a excecao).


class _FakeDriverConn:
    """psycopg2 conn falsa: autocommit setavel, sem notifies, poll no-op."""

    def __init__(self) -> None:
        self.autocommit = False
        self.notifies: list[object] = []

    def poll(self) -> None:  # pragma: no cover — select() abaixo nunca sinaliza
        pass


class _FakeCursor:
    def execute(self, _sql: str) -> None:
        pass


class _FakeRaw:
    """raw_connection falsa: expoe driver_connection, cursor e close."""

    def __init__(self, driver: _FakeDriverConn) -> None:
        self.driver_connection = driver
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor()

    def close(self) -> None:
        self.closed = True


class _FakeEngine:
    def __init__(self, raw: _FakeRaw) -> None:
        self._raw = raw

    def raw_connection(self) -> _FakeRaw:
        return self._raw


def _relogio() -> datetime:
    return datetime.now(UTC)


def test_ciclo_falho_loga_e_continua_sem_derrubar_o_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _FakeDriverConn()
    raw = _FakeRaw(driver)
    engine = _FakeEngine(raw)

    # select() sempre retorna "sem dados" (timeout): o loop nao bloqueia em
    # socket real e cai direto no drain a cada iteracao.
    monkeypatch.setattr(listener_mod.select, "select", lambda *_a, **_k: ([], [], []))
    # Gauge e heartbeat nao tocam banco/filesystem real neste teste unitario.
    monkeypatch.setattr(listener_mod, "emitir_profundidade", lambda _engine: None)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)

    # call #1 = drain inicial (antes do while, FORA do try/except): retorna 0.
    # call #2 = 1o drain DENTRO do while (no try/except): levanta erro
    #   transitorio de DB — em producao propagaria e mataria o processo; o
    #   loop deve logar e CONTINUAR. call #3+ = drains seguintes (retornam 0).
    chamadas = {"n": 0}

    def processar_ciclo_fake(*_args: Any, **_kwargs: Any) -> int:
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise OperationalError("SELECT 1", {}, Exception("conexao perdida"))
        return 0

    monkeypatch.setattr(listener_mod, "processar_ciclo", processar_ciclo_fake)

    # `parar` deixa o while rodar 2 acordes (o que falha + um que sobrevive)
    # e entao encerra deterministicamente.
    paradas = {"n": 0}

    def parar() -> bool:
        paradas["n"] += 1
        return paradas["n"] > 2

    with structlog.testing.capture_logs() as logs:
        # Se a resiliencia falhasse, o OperationalError do drain in-loop
        # propagaria daqui e o teste quebraria.
        executar_relay(
            engine,  # type: ignore[arg-type]  # fake satisfaz a superficie usada
            handlers={},
            nome_handler="email",
            relogio=_relogio,
            parar=parar,
        )

    # O ciclo que falhou foi logado como erro estruturado e o loop continuou.
    assert any(log.get("event") == "outbox_ciclo_falhou" for log in logs)
    # Houve drain DEPOIS do que falhou (a falha NAO encerrou o loop): >=3 calls
    # (inicial + o que levantou + ao menos mais um acorde do while).
    assert chamadas["n"] >= 3
    # Encerrou de forma limpa: autocommit restaurado e conexao raw fechada.
    assert driver.autocommit is False
    assert raw.closed is True
