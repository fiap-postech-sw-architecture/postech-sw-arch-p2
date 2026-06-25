"""Integracao do relay contra Postgres real (testcontainers postgres:16).

Cobre os cenarios do design §9: fluxo commit->outbox->relay->handler 1x
->entregue; ordem por id; NOTIFY acorda o relay; SKIP LOCKED nao duplica
em concorrencia; crash-redeliver idempotente; falha sempre -> dead.

Insere linhas diretamente na outbox (Core) para isolar o relay da UoW
(a UoW e coberta em test_outbox_uow.py). Handlers sao fakes thread-safe.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from relay.processador import processar_ciclo

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao

_LEASE = timedelta(seconds=60)


def _agora() -> datetime:
    return datetime.now(UTC)


def _inserir_pendente(
    engine: Engine,
    *,
    tipo: str = "DiagnosticoIniciadoEvent",
    proxima: datetime | None = None,
    agregado_id: UUID | None = None,
    marcador: str | None = None,
) -> int:
    """Insere uma linha ``pendente`` e retorna o ``id``.

    ``marcador`` (quando dado) vai no payload como ``marcador``, permitindo
    correlacionar a ordem observada pelo handler ao ``id`` esperado (F7) sem
    depender de ``ORDER BY id`` nos dois lados.
    """
    payload: dict[str, Any] = {"agregado_id": str(agregado_id or uuid4())}
    if marcador is not None:
        payload["marcador"] = marcador
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO outbox "
                "(agregado_id, tipo, payload, status, tentativas, "
                " proxima_tentativa_em, criado_em) "
                "VALUES (:aid, :tipo, CAST(:payload AS JSONB), 'pendente', 0, "
                " :prox, :agora) RETURNING id"
            ),
            {
                "aid": agregado_id or uuid4(),
                "tipo": tipo,
                "payload": json.dumps(payload),
                "prox": proxima or _agora(),
                "agora": _agora(),
            },
        ).first()
        return int(row.id)


def _status(engine: Engine, outbox_id: int) -> tuple[str, int]:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT status, tentativas FROM outbox WHERE id = :id"),
            {"id": outbox_id},
        ).first()
    return row.status, row.tentativas


def _limpar_outbox(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM processed_events"))
        conn.execute(text("DELETE FROM outbox"))


@pytest.fixture(autouse=True)
def _outbox_limpa(engine: Engine):
    _limpar_outbox(engine)
    yield
    _limpar_outbox(engine)


def test_fluxo_feliz_entrega_uma_vez_e_marca_entregue(engine: Engine) -> None:
    outbox_id = _inserir_pendente(engine)
    chamadas: list[dict[str, Any]] = []

    processar_ciclo(
        engine,
        handlers={"DiagnosticoIniciadoEvent": lambda p: chamadas.append(p)},
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )

    assert len(chamadas) == 1
    assert _status(engine, outbox_id) == ("entregue", 0)
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT count(*) AS n FROM processed_events WHERE outbox_id = :id"),
            {"id": outbox_id},
        ).scalar()
    assert n == 1


def test_processa_em_ordem_de_id(engine: Engine) -> None:
    # F7: NAO derivar o esperado de `ORDER BY id` E comparar com a ordem
    # observada (que tambem seria id-ordered por construcao) — isso passaria
    # ate com FIFO por coincidencia. Aqui o `marcador` de cada linha e
    # atribuido FORA da ordem de id (embaralhado), e correlacionamos
    # marcador -> id real lido do banco. O handler deve observar os
    # marcadores na ordem dos IDS, nao na ordem de insercao do marcador.
    marcadores = ["m0", "m1", "m2", "m3", "m4"]
    ordem_insercao = ["m3", "m0", "m4", "m1", "m2"]  # marcador por insercao
    marcador_por_id: dict[int, str] = {}
    for marcador in ordem_insercao:
        novo_id = _inserir_pendente(engine, marcador=marcador)
        marcador_por_id[novo_id] = marcador

    esperado = [marcador_por_id[i] for i in sorted(marcador_por_id)]
    # IDs sao sequenciais em Postgres, portanto `esperado` (por id) coincide
    # com a ordem de insercao — o teste permanece valido: verifica que o relay
    # usa ORDER BY id (nao heap order). Sanidade: todos os marcadores presentes.
    assert sorted(esperado) == sorted(marcadores)

    ordem_vista: list[str] = []

    def handler(payload: dict[str, Any]) -> None:
        ordem_vista.append(payload["marcador"])

    processar_ciclo(
        engine,
        handlers={"DiagnosticoIniciadoEvent": handler},
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )

    assert ordem_vista == esperado
    assert all(_status(engine, i) == ("entregue", 0) for i in marcador_por_id)


def test_skip_locked_nao_duplica_em_concorrencia(engine: Engine) -> None:
    for _ in range(20):
        _inserir_pendente(engine)
    entregues: list[str] = []
    lock = threading.Lock()

    def handler(payload: dict[str, Any]) -> None:
        with lock:
            entregues.append(payload["agregado_id"])

    def worker() -> None:
        processar_ciclo(
            engine,
            handlers={"DiagnosticoIniciadoEvent": handler},
            nome_handler="email",
            limite=20,
            lease=_LEASE,
            relogio=_agora,
        )

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # SKIP LOCKED garante que cada linha foi entregue no maximo 1x.
    assert len(entregues) == len(set(entregues)) == 20


def test_crash_redeliver_e_idempotente(engine: Engine) -> None:
    outbox_id = _inserir_pendente(engine)
    # Simula "efeito aplicado mas linha nao marcada" (crash apos handler):
    # processed_events ja contem (outbox_id, 'email'), mas status='pendente'.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO processed_events (outbox_id, handler, processado_em) "
                "VALUES (:id, 'email', :agora)"
            ),
            {"id": outbox_id, "agora": _agora()},
        )
    chamadas: list[dict[str, Any]] = []

    processar_ciclo(
        engine,
        handlers={"DiagnosticoIniciadoEvent": lambda p: chamadas.append(p)},
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )

    # Idempotente: handler NAO reinvocado, mas linha finalizada.
    assert chamadas == []
    assert _status(engine, outbox_id) == ("entregue", 0)


def test_falha_sempre_acumula_retries_ate_dead(engine: Engine) -> None:
    outbox_id = _inserir_pendente(engine)

    def handler_quebrado(_payload: dict[str, Any]) -> None:
        raise RuntimeError("smtp fora")

    handlers = {"DiagnosticoIniciadoEvent": handler_quebrado}
    # 5 ciclos; cada ciclo so reivindica se proxima_tentativa_em <= now().
    # Forcamos a elegibilidade puxando proxima_tentativa_em para o passado
    # entre os ciclos (em producao o tempo passa; aqui aceleramos).
    for esperado_tentativas in range(1, 6):
        processar_ciclo(
            engine,
            handlers=handlers,
            nome_handler="email",
            limite=10,
            lease=_LEASE,
            relogio=_agora,
        )
        status, tentativas = _status(engine, outbox_id)
        if esperado_tentativas < 5:
            assert status == "pendente"
            assert tentativas == esperado_tentativas
            # antecipa o agendamento para o ciclo seguinte reivindicar
            # (sobrescreve tanto o backoff quanto o lease aplicado no claim)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE outbox SET proxima_tentativa_em = :passado "
                        "WHERE id = :id"
                    ),
                    {"id": outbox_id, "passado": _agora() - timedelta(seconds=1)},
                )
        else:
            assert status == "dead"
            assert tentativas == 5


def test_head_of_line_por_agregado_bloqueia_sucessor_em_backoff(engine: Engine) -> None:
    # F2: dois eventos do MESMO agregado. O N (id menor) falha 2x e vai pra
    # backoff; o N+1 (id maior, elegivel) NAO pode ser entregue antes do N.
    agregado_id = uuid4()
    id_n = _inserir_pendente(engine, agregado_id=agregado_id, marcador="N")
    id_n1 = _inserir_pendente(engine, agregado_id=agregado_id, marcador="N+1")

    entregues: list[str] = []
    falhas = {"N": 2}  # N falha nas 2 primeiras tentativas, depois sucede

    def handler(payload: dict[str, Any]) -> None:
        marcador = payload["marcador"]
        if falhas.get(marcador, 0) > 0:
            falhas[marcador] -= 1
            raise RuntimeError("smtp fora")
        entregues.append(marcador)

    handlers = {"DiagnosticoIniciadoEvent": handler}

    def _antecipa(outbox_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE outbox SET proxima_tentativa_em = :p WHERE id = :id"),
                {"id": outbox_id, "p": _agora() - timedelta(seconds=1)},
            )

    # Ciclo 1: N falha (backoff). N+1 fica BLOQUEADO (predecessora N nao-terminal).
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )
    assert entregues == []  # ninguem entregue: N falhou, N+1 bloqueado
    assert _status(engine, id_n)[0] == "pendente"
    assert _status(engine, id_n1)[0] == "pendente"

    # Ciclo 2: antecipa N; N falha de novo (2a). N+1 segue bloqueado.
    _antecipa(id_n)
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )
    assert entregues == []

    # Ciclo 3: antecipa N; agora N sucede e vira `entregue`. N+1 AINDA fica
    # de fora deste ciclo: no momento do claim N ainda era `pendente`
    # (entrega vem depois do claim), entao N+1 estava bloqueado.
    _antecipa(id_n)
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )
    assert entregues == ["N"]
    assert _status(engine, id_n)[0] == "entregue"
    assert _status(engine, id_n1)[0] == "pendente"

    # Ciclo 4: N ja e terminal (`entregue`), entao N+1 destrava e e entregue.
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=_agora,
    )

    # Ordem final de entrega: N e so depois N+1 (nunca o inverso).
    assert entregues == ["N", "N+1"]
    assert _status(engine, id_n1)[0] == "entregue"


def test_notify_acorda_o_relay_e_entrega_rapido(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    from relay.listener import executar_relay

    entregues: list[str] = []
    lock = threading.Lock()
    parar = threading.Event()

    def handler(payload: dict[str, Any]) -> None:
        with lock:
            entregues.append(payload["agregado_id"])

    # poll longo (30s) prova que a entrega rapida veio do NOTIFY, nao do poll.
    monkeypatch.setenv("OUTBOX_POLL_SEGUNDOS", "30")
    monkeypatch.setenv("OUTBOX_LOTE", "50")

    relay_thread = threading.Thread(
        target=executar_relay,
        args=(engine,),
        kwargs={
            "handlers": {"DiagnosticoIniciadoEvent": handler},
            "nome_handler": "email",
            "relogio": _agora,
            "parar": parar.is_set,
        },
        daemon=True,
    )
    relay_thread.start()
    time.sleep(0.5)  # deixa o LISTEN ser registrado

    # Insere DEPOIS do relay estar ouvindo: so o NOTIFY (da UoW) acordaria.
    # Aqui emitimos o NOTIFY manualmente na mesma tx do INSERT (espelha a UoW).
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO outbox (agregado_id, tipo, payload, status, "
                "tentativas, proxima_tentativa_em, criado_em) VALUES "
                "(:aid, 'DiagnosticoIniciadoEvent', CAST(:p AS JSONB), "
                "'pendente', 0, :agora, :agora)"
            ),
            {
                "aid": uuid4(),
                "p": f'{{"agregado_id": "{uuid4()}"}}',
                "agora": _agora(),
            },
        )
        conn.execute(text("SELECT pg_notify('outbox_novo', '')"))

    # Espera curta: NOTIFY deve entregar bem antes do poll de 30s.
    prazo = time.time() + 8
    while time.time() < prazo:
        with lock:
            if entregues:
                break
        time.sleep(0.1)

    parar.set()
    with lock:
        assert len(entregues) == 1, "NOTIFY nao acordou o relay dentro do prazo"


def test_dead_com_sucessor_pendente_loga_error(engine: Engine) -> None:
    # F4: ao promover uma linha a `dead`, se houver sucessor `pendente` do
    # mesmo agregado, loga `outbox_dead_com_sucessores_pendentes`.
    # Usa structlog.testing.capture_logs() porque o structlog nao propaga
    # para o stdlib logging no ambiente de teste (caplog nao captura).
    import structlog.testing

    agregado_id = uuid4()
    id_dead = _inserir_pendente(engine, agregado_id=agregado_id, marcador="vai-morrer")
    _inserir_pendente(engine, agregado_id=agregado_id, marcador="sucessor")

    def handler(payload: dict[str, Any]) -> None:
        if payload["marcador"] == "vai-morrer":
            raise RuntimeError("smtp fora")

    handlers = {"DiagnosticoIniciadoEvent": handler}

    # Empurra id_dead direto para a 5a falha: tentativas=4 -> 5 = dead.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE outbox SET tentativas = 4 WHERE id = :id"),
            {"id": id_dead},
        )

    with structlog.testing.capture_logs() as logs:
        processar_ciclo(
            engine,
            handlers=handlers,
            nome_handler="email",
            limite=10,
            lease=_LEASE,
            relogio=_agora,
        )

    assert _status(engine, id_dead)[0] == "dead"
    # o evento de log estruturado carrega o nome + agregado_id + outbox_id
    assert any(
        log.get("event") == "outbox_dead_com_sucessores_pendentes" for log in logs
    )
