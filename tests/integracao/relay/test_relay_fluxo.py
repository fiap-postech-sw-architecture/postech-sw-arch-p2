"""Integracao do relay contra Postgres real (testcontainers postgres:16).

Cobre os cenarios do design §9: fluxo commit->outbox->relay->handler 1x
->entregue; ordem por id; NOTIFY acorda o relay; SKIP LOCKED nao duplica
em concorrencia; crash-redeliver idempotente; falha sempre -> dead.

Insere linhas diretamente na outbox (Core) para isolar o relay da UoW
(a UoW e coberta em test_outbox_uow.py). Handlers sao fakes thread-safe.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from relay.processador import (
    ConexaoOutboxSQL,
    emitir_profundidade,
    processar_ciclo,
    reivindicar_lote,
)
from tests.integracao.outbox_helpers import (
    inserir_dead as _inserir_dead,
)
from tests.integracao.outbox_helpers import (
    inserir_pendente as _inserir_pendente,
)
from tests.integracao.outbox_helpers import (
    inserir_pendente_com_id as _inserir_pendente_com_id,
)
from tests.integracao.outbox_helpers import (
    status_tentativas as _status,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integracao

_LEASE = timedelta(seconds=60)

# A limpeza da outbox e autouse no conftest do pacote (`_outbox_limpa`).


def _agora() -> datetime:
    return datetime.now(UTC)


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
    # F7 (discriminante): atribui ids EXPLICITOS, NAO-monotonicos com a ordem
    # de insercao — insere na ordem [50, 10, 40, 20, 30], cada linha carregando
    # como marcador o proprio id. O relay deve entregar em ordem de ID
    # ([10, 20, 30, 40, 50]), que DIFERE da ordem de insercao. Um relay
    # heap/FIFO (sem ORDER BY id) entregaria na ordem de insercao
    # ([50, 10, 40, 20, 30]) e o assert falharia. Verificado manualmente:
    # remover `ORDER BY o.id` de reivindicar_lote faz este teste quebrar.
    ordem_insercao = [50, 10, 40, 20, 30]
    for outbox_id in ordem_insercao:
        _inserir_pendente_com_id(engine, outbox_id, marcador=str(outbox_id))

    esperado = [str(i) for i in sorted(ordem_insercao)]  # ['10','20','30','40','50']
    assert esperado != [str(i) for i in ordem_insercao], (
        "ordem por id deve diferir da ordem de insercao para discriminar FIFO"
    )

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
    assert all(_status(engine, i) == ("entregue", 0) for i in ordem_insercao)


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

    # Passada final single-thread: SKIP LOCKED permite que um worker PULE uma
    # linha momentaneamente lockada por outro na mesma passada — o relay real
    # drena em loop. A propriedade sob teste e a NAO-duplicacao na corrida;
    # sem esta drenagem o teste flakava em runner lento (issue #160, 19/20).
    worker()

    # SKIP LOCKED garante que cada linha foi entregue no maximo 1x.
    assert len(entregues) == len(set(entregues)) == 20


def test_fencing_serializa_duas_replicas_na_entrega(engine: Engine) -> None:
    # TD-021 (deterministico, sem timing): o fencing `bloquear_para_entrega`
    # (re-lock `FOR UPDATE SKIP LOCKED` na tx por-linha) serializa duas
    # replicas competindo pela MESMA linha. Prova as duas pontas:
    #   1. enquanto A detem o lock, B falha o re-lock (SKIP LOCKED) -> so A
    #      entrega -> sem e-mail duplicado mesmo com o lease vencido;
    #   2. apos A marcar `entregue` e comitar, um novo re-lock falha (status
    #      != pendente) -> sem re-entrega da linha ja concluida.
    outbox_id = _inserir_pendente(engine)

    # Conexao A: re-locka a linha e MANTEM a tx aberta (simula a replica que
    # esta entregando agora). Conexao B: tenta re-lockar em paralelo.
    conn_a = engine.connect()
    conn_b = engine.connect()
    try:
        conn_a.begin()
        fachada_a = ConexaoOutboxSQL(conn_a, _agora())
        # A trava a linha (e dona da entrega nesta tx).
        assert fachada_a.bloquear_para_entrega(outbox_id) is True

        conn_b.begin()
        fachada_b = ConexaoOutboxSQL(conn_b, _agora())
        # B nao consegue: SKIP LOCKED pula a linha travada por A -> nao
        # entrega em paralelo (sem duplicacao).
        assert fachada_b.bloquear_para_entrega(outbox_id) is False
        conn_b.rollback()

        # A conclui a entrega e comita -> libera o lock e muda o status.
        fachada_a.marcar_entregue(outbox_id)
        conn_a.commit()
    finally:
        conn_a.close()
        conn_b.close()

    assert _status(engine, outbox_id) == ("entregue", 0)

    # Numa conexao nova, o re-lock falha agora pelo status (nao mais
    # `pendente`): nenhuma replica re-entrega a linha ja concluida.
    conn_c = engine.connect()
    try:
        conn_c.begin()
        fachada_c = ConexaoOutboxSQL(conn_c, _agora())
        assert fachada_c.bloquear_para_entrega(outbox_id) is False
        conn_c.rollback()
    finally:
        conn_c.close()


def test_duas_replicas_concorrentes_entregam_linha_exatamente_uma_vez(
    engine: Engine,
) -> None:
    # Smoke de exactly-once sob dois workers `processar_ciclo` concorrentes
    # sobre UMA linha (handler lento, ~0,3s, segura a tx por-linha). O que
    # impede a duplicacao AQUI e o CLAIM: `reivindicar_lote` reivindica a linha
    # com `FOR UPDATE OF o SKIP LOCKED` e crava o lease de 60s numa tx
    # COMITADA, ANTES da entrega. So um worker reivindica; quando o handler
    # lento roda (fase DELIVER), a linha ja foi serializada no claim e o lease
    # esta longe de vencer. O fencing de entrega (`bloquear_para_entrega`) NAO
    # e exercitado aqui — sua prova determinista, sem timing, esta em
    # `test_fencing_serializa_duas_replicas_na_entrega` (segura o lock da
    # replica A e mostra que o re-lock de B retorna vazio + status != pendente
    # apos o commit). Este teste vale como smoke de exactly-once concorrente
    # via claim; NAO cobre a corrida de lease-vencido-no-meio-da-entrega.
    import time

    outbox_id = _inserir_pendente(engine)
    entregues: list[str] = []
    lock = threading.Lock()

    def handler(payload: dict[str, Any]) -> None:
        # Segura a tx por-linha aberta tempo suficiente para a outra replica
        # tentar (e falhar) o re-lock concorrentemente.
        time.sleep(0.3)
        with lock:
            entregues.append(payload["agregado_id"])

    def worker() -> None:
        processar_ciclo(
            engine,
            handlers={"DiagnosticoIniciadoEvent": handler},
            nome_handler="email",
            limite=10,
            lease=_LEASE,
            relogio=_agora,
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly-once: a linha foi entregue por exatamente uma replica (o claim
    # com SKIP LOCKED + lease serializou; o fencing de entrega nao entra aqui).
    assert entregues == [entregues[0]]
    assert len(entregues) == 1
    assert _status(engine, outbox_id) == ("entregue", 0)


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


def test_lease_vencido_apos_crash_de_claim_reentrega_exatamente_uma_vez(
    engine: Engine,
) -> None:
    # F3 (crash-recovery pelo lease): o worker REIVINDICA a linha (claim
    # comitado aplica o lease = visibility timeout) e morre ANTES de entregar
    # — simulado executando so a fase de claim (`reivindicar_lote` numa tx
    # curta identica a de `processar_ciclo`) e nunca a de deliver. O relogio
    # e injetavel, entao o teste avanca o tempo em vez de dormir. Pina o
    # comportamento ATUAL de re-claim pos-lease (o fencing de entrega em si
    # e coberto em `test_fencing_serializa_duas_replicas_na_entrega`; a
    # discussao de mudanca e a issue #166).
    outbox_id = _inserir_pendente(engine)
    base = _agora()

    with engine.begin() as conn:
        reivindicadas = reivindicar_lote(conn, base, 10, _LEASE)
    assert [linha.id for linha in reivindicadas] == [outbox_id]
    # "Crash": nenhuma entrega acontece; o commit acima persistiu o lease.

    chamadas: list[dict[str, Any]] = []
    handlers: dict[str, Any] = {
        "DiagnosticoIniciadoEvent": lambda p: chamadas.append(p)
    }

    # Antes do lease vencer, a linha NAO e re-elegivel (visibility timeout):
    # um segundo worker nao a reivindica nem entrega.
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=lambda: base + _LEASE - timedelta(seconds=1),
    )
    assert chamadas == []
    assert _status(engine, outbox_id) == ("pendente", 0)

    # Relogio avancado ALEM do lease: o segundo worker re-reivindica e
    # entrega exatamente 1x (at-least-once pos-crash), sem tentativa extra.
    processar_ciclo(
        engine,
        handlers=handlers,
        nome_handler="email",
        limite=10,
        lease=_LEASE,
        relogio=lambda: base + _LEASE + timedelta(seconds=1),
    )
    assert len(chamadas) == 1
    assert _status(engine, outbox_id) == ("entregue", 0)
    with engine.begin() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM processed_events WHERE outbox_id = :id"),
            {"id": outbox_id},
        ).scalar()
    assert n == 1


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


def _esperar_listen_registrado(engine: Engine, prazo_s: float = 5.0) -> None:
    """Espera (por condicao observada, nao sleep fixo) o LISTEN estar ativo.

    O relay abre uma conexao psycopg2 DEDICADA (com keepalives, fora do pool)
    e executa ``LISTEN outbox_novo`` — esse backend fica visivel em
    ``pg_stat_activity`` com a query ``LISTEN ...`` como ultima executada.
    Poll ate ~5s (mesmo padrao dos helpers ``_esperar_*`` do repo): substitui
    o ``time.sleep(0.5)`` fixo, que era lento no melhor caso e flaky num
    runner carregado. Filtra por ``datname = current_database()`` para nao
    casar com um LISTEN de outro banco no mesmo servidor.
    """
    import time

    prazo = time.time() + prazo_s
    while time.time() < prazo:
        with engine.connect() as conn:
            ouvindo = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND query ILIKE 'LISTEN%'"
                )
            ).scalar()
        if ouvindo and int(ouvindo) >= 1:
            return
        time.sleep(0.05)
    pytest.fail("backend de LISTEN nao apareceu em pg_stat_activity no prazo")


def test_notify_acorda_o_relay_e_entrega_rapido(
    engine_dedicado: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    from relay.listener import executar_relay

    # Engine function-scoped (pool isolado): o relay abre uma conexao raw de
    # LISTEN em autocommit; com o engine compartilhado da sessao essa conexao,
    # ao ser reciclada, contaminaria fixtures de SAVEPOINT subsequentes. Mesma
    # URL/banco do engine da sessao — so o pool e dedicado.
    engine = engine_dedicado
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
    # Espera por CONDICAO (backend de LISTEN visivel no proprio Postgres),
    # nao por duracao fixa: garante que o INSERT+NOTIFY abaixo so acontece
    # com o relay de fato ouvindo.
    _esperar_listen_registrado(engine)

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
    # Encerra o relay de forma DETERMINISTICA antes do teardown: o thread pode
    # estar parado em select(poll=30s); um NOTIFY o acorda, ele reavalia
    # `parar()` (agora True) e fecha a conexao dedicada de LISTEN.
    # Sem o join, `engine_dedicado.dispose()` poderia derrubar o pool com o
    # thread ainda drenando (OperationalError espuria no teardown).
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_notify('outbox_novo', '')"))
    relay_thread.join(timeout=5)
    assert not relay_thread.is_alive(), "relay nao encerrou apos parar.set() + NOTIFY"
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


def test_gauge_profundidade_loga_contagens(engine: Engine) -> None:
    # §7: o gauge emite `outbox_profundidade` com pendentes, idade do mais
    # antigo (segundos) e tamanho da DLQ. Semeia 2 pendentes (um antigo, um
    # recente) + 1 dead e afere as contagens no log estruturado.
    import structlog.testing

    # Pendente "antigo": criado_em empurrado 120s para o passado -> idade > 0.
    antigo = _inserir_pendente(engine)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE outbox SET criado_em = :p WHERE id = :id"),
            {"id": antigo, "p": _agora() - timedelta(seconds=120)},
        )
    _inserir_pendente(engine)  # segundo pendente (recente)
    _inserir_dead(engine)  # uma linha na DLQ

    with structlog.testing.capture_logs() as logs:
        emitir_profundidade(engine)

    eventos = [log for log in logs if log.get("event") == "outbox_profundidade"]
    assert len(eventos) == 1, logs
    gauge = eventos[0]
    assert gauge["pendentes"] == 2
    assert gauge["dead"] == 1
    # idade do mais antigo: ao menos ~120s (o pendente que empurramos).
    assert gauge["idade_mais_antigo_s"] is not None
    assert gauge["idade_mais_antigo_s"] >= 100.0


def test_gauge_profundidade_outbox_vazia_idade_none(engine: Engine) -> None:
    # Sem pendentes: contagens 0 e idade None (min(...) FILTER -> NULL).
    import structlog.testing

    with structlog.testing.capture_logs() as logs:
        emitir_profundidade(engine)

    gauge = next(log for log in logs if log.get("event") == "outbox_profundidade")
    assert gauge["pendentes"] == 0
    assert gauge["dead"] == 0
    assert gauge["idade_mais_antigo_s"] is None
