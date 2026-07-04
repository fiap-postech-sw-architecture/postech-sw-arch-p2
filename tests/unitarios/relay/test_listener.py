from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import structlog.testing
from psycopg2 import Error as Psycopg2Error
from psycopg2 import OperationalError as Psycopg2OperationalError
from sqlalchemy.exc import OperationalError

import relay.listener as listener_mod
from relay.listener import (
    _conectar_listen,
    _config_do_ambiente,
    _drenar,
    _reconectar_listen,
    executar_relay,
)
from src.compartilhado.infraestrutura.outbox_mapping import CANAL_NOTIFY


@pytest.fixture(autouse=True)
def _ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    # Config do relay depende do ambiente: limpa as tres variaveis para que
    # cada teste parta dos defaults (e sobrescreva so o que lhe interessa).
    monkeypatch.delenv("OUTBOX_POLL_SEGUNDOS", raising=False)
    monkeypatch.delenv("OUTBOX_LOTE", raising=False)
    monkeypatch.delenv("OUTBOX_LEASE_SEGUNDOS", raising=False)


def test_config_le_defaults() -> None:
    poll, lote, lease = _config_do_ambiente()
    assert poll == 5.0
    assert lote == 10  # default pequeno (F3): limita a janela de duplicacao
    assert lease == timedelta(seconds=60)


def test_config_le_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTBOX_POLL_SEGUNDOS", "2")
    monkeypatch.setenv("OUTBOX_LOTE", "25")
    monkeypatch.setenv("OUTBOX_LEASE_SEGUNDOS", "90")
    poll, lote, lease = _config_do_ambiente()
    assert poll == 2.0
    assert lote == 25
    assert lease == timedelta(seconds=90)


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("OUTBOX_POLL_SEGUNDOS", "cinco"),
        ("OUTBOX_LOTE", "dez"),
        ("OUTBOX_LEASE_SEGUNDOS", "1m"),
    ],
)
def test_config_nao_numerica_falha_no_boot_com_erro_claro(
    monkeypatch: pytest.MonkeyPatch, variavel: str, valor: str
) -> None:
    # Misconfig deve falhar CLARO no boot (nomeando a variavel e o valor),
    # nao estourar com um ValueError criptico no meio do loop.
    monkeypatch.setenv(variavel, valor)
    with pytest.raises(RuntimeError, match=variavel):
        _config_do_ambiente()


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("OUTBOX_POLL_SEGUNDOS", "0"),
        ("OUTBOX_POLL_SEGUNDOS", "-3"),
        ("OUTBOX_LOTE", "0"),
        ("OUTBOX_LOTE", "-1"),
    ],
)
def test_config_nao_positiva_falha_no_boot(
    monkeypatch: pytest.MonkeyPatch, variavel: str, valor: str
) -> None:
    # poll <= 0 viraria busy-loop (select sem espera) e lote <= 0 nunca
    # drenaria nada: ambos sao misconfig, nao modo de operacao.
    monkeypatch.setenv(variavel, valor)
    with pytest.raises(RuntimeError, match=variavel):
        _config_do_ambiente()


def test_lease_menor_ou_igual_ao_timeout_smtp_falha_no_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Invariante de HA (design §5.5): lease > timeout de entrega SMTP (5s no
    # adapter). Lease menor re-elegibiliza a linha NO MEIO da entrega em voo.
    monkeypatch.setenv("OUTBOX_LEASE_SEGUNDOS", "5")
    with pytest.raises(RuntimeError, match="OUTBOX_LEASE_SEGUNDOS"):
        _config_do_ambiente()


def test_lease_minimo_acima_do_timeout_smtp_passa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTBOX_LEASE_SEGUNDOS", "6")
    *_, lease = _config_do_ambiente()
    assert lease == timedelta(seconds=6)


# --- Fakes da conexao dedicada de LISTEN -------------------------------------
#
# `executar_relay` cria a conexao de LISTEN via
# `engine.dialect.loaded_dbapi.connect(*create_connect_args(url))` (psycopg2
# direto, fora do pool — keepalives sao parametros de conexao). Os fakes
# reproduzem essa superficie: dialect -> dbapi -> conexao -> cursor.


class _FakeCursor:
    def __init__(self, conexao: _FakeConexaoListen) -> None:
        self._conexao = conexao
        self.fechado = False

    def execute(self, sql: str) -> None:
        self._conexao.sql_executado.append(sql)

    def close(self) -> None:
        self.fechado = True


class _FakeConexaoListen:
    """Conexao psycopg2 fake: cursor, poll (com falhas roteirizadas), close."""

    def __init__(self, falhas_poll: int = 0) -> None:
        self.autocommit = False
        self.notifies: list[object] = []
        self.sql_executado: list[str] = []
        self.cursores: list[_FakeCursor] = []
        self.fechada = False
        self._falhas_poll = falhas_poll

    def cursor(self) -> _FakeCursor:
        cursor = _FakeCursor(self)
        self.cursores.append(cursor)
        return cursor

    def poll(self) -> None:
        if self._falhas_poll > 0:
            self._falhas_poll -= 1
            raise Psycopg2OperationalError("conexao de LISTEN perdida")

    def close(self) -> None:
        self.fechada = True


class _FakeDbapi:
    """Modulo psycopg2 fake: entrega conexoes pre-fabricadas, captura kwargs."""

    # `executar_relay` resolve as classes de erro via `dbapi.Error` (evita
    # importar psycopg2 direto no listener); o fake aponta para as reais.
    Error = Psycopg2Error

    def __init__(self, conexoes: list[_FakeConexaoListen]) -> None:
        self._conexoes = list(conexoes)
        self.kwargs_conexoes: list[dict[str, Any]] = []

    def connect(self, *_args: Any, **kwargs: Any) -> _FakeConexaoListen:
        self.kwargs_conexoes.append(kwargs)
        return self._conexoes.pop(0)


class _FakeDialect:
    def __init__(self, dbapi: _FakeDbapi) -> None:
        self.loaded_dbapi = dbapi

    def create_connect_args(self, _url: object) -> tuple[list[str], dict[str, Any]]:
        # Espelha o dialect psycopg2 real: ([], opts derivados da URL).
        return ([], {"host": "db", "port": 5432, "user": "app"})


class _FakeEngine:
    def __init__(self, dbapi: _FakeDbapi) -> None:
        self.dialect = _FakeDialect(dbapi)
        self.url = object()


def _relogio() -> datetime:
    return datetime.now(UTC)


# --- Conexao dedicada de LISTEN: keepalives + setup --------------------------


def test_conectar_listen_aplica_keepalives_e_registra_o_canal() -> None:
    # Keepalives TCP sao parametros de CONEXAO (libpq): precisam entrar no
    # connect() da conexao dedicada de LISTEN — um NAT/LB que dropa o socket
    # em silencio deixaria o relay surdo a NOTIFY sem eles.
    conexao = _FakeConexaoListen()
    dbapi = _FakeDbapi([conexao])
    engine = _FakeEngine(dbapi)

    resultado = _conectar_listen(engine)  # type: ignore[arg-type]

    assert resultado is conexao
    assert conexao.autocommit is True  # LISTEN exige autocommit
    assert conexao.sql_executado == [f"LISTEN {CANAL_NOTIFY}"]
    assert conexao.cursores[0].fechado is True  # cursor fechado no finally
    kwargs = dbapi.kwargs_conexoes[0]
    assert kwargs["keepalives"] == 1
    assert kwargs["keepalives_idle"] == 30
    assert kwargs["keepalives_interval"] == 10
    assert kwargs["keepalives_count"] == 3
    # E preserva os connect args derivados da URL do engine (mesmo banco).
    assert kwargs["host"] == "db"


# --- Heartbeat por ciclo de drain (#163) e SIGTERM dentro do drain -----------


def test_drenar_toca_heartbeat_a_cada_processar_ciclo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #163 (starvation): uma fila profunda encadeia N ciclos num unico acorde;
    # o heartbeat precisa ser tocado a CADA ciclo, senao a livenessProbe (60s)
    # mata um pod saudavel no meio de um drain longo.
    retornos = iter([4, 3, 0])
    chamadas = {"ciclos": 0}

    def processar_ciclo_fake(*_args: Any, **_kwargs: Any) -> int:
        chamadas["ciclos"] += 1
        return next(retornos)

    monkeypatch.setattr(listener_mod, "processar_ciclo", processar_ciclo_fake)
    batidas: list[int] = []

    total = _drenar(
        object(),  # type: ignore[arg-type]  # fake satisfaz a superficie usada
        handlers={},
        nome_handler="email",
        lote=10,
        lease=timedelta(seconds=60),
        relogio=_relogio,
        heartbeat=lambda: batidas.append(1),
        parar=lambda: False,
    )

    # N ciclos => N toques de heartbeat (um ANTES de cada processar_ciclo).
    assert chamadas["ciclos"] == 3
    assert len(batidas) == 3
    assert total == 7


def test_drenar_para_de_reivindicar_ciclos_apos_sinal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SIGTERM no meio de um drain de fila profunda: `parar` e observado no
    # topo do while — o relay NAO reivindica lote novo e encerra dentro do
    # grace period, mesmo com a fila ainda cheia.
    chamadas = {"ciclos": 0}

    def processar_ciclo_fake(*_args: Any, **_kwargs: Any) -> int:
        chamadas["ciclos"] += 1
        return 10  # fila "infinita": sem o parar, drenaria para sempre

    monkeypatch.setattr(listener_mod, "processar_ciclo", processar_ciclo_fake)
    sinais = iter([False, True])  # sinal chega depois do 1o ciclo

    total = _drenar(
        object(),  # type: ignore[arg-type]
        handlers={},
        nome_handler="email",
        lote=10,
        lease=timedelta(seconds=60),
        relogio=_relogio,
        heartbeat=lambda: None,
        parar=lambda: next(sinais),
    )

    assert chamadas["ciclos"] == 1  # nenhum ciclo novo apos o sinal
    assert total == 10


# --- Resiliencia por ciclo (F6/operacao) ------------------------------------
#
# Um erro transitorio de DB no drain NAO pode derrubar o relay (derrubar
# reinicia o pod e desmonta o LISTEN a cada blip). O loop deve logar
# `outbox_ciclo_falhou` e CONTINUAR; o teste injeta um `processar_ciclo` que
# levanta UMA vez e prova que o ciclo seguinte roda e o loop encerra via
# `parar` (sem propagar a excecao). O drain inicial (pre-while) vive DENTRO
# do mesmo guarda-chuva.


def test_ciclo_falho_loga_e_continua_sem_derrubar_o_relay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conexao = _FakeConexaoListen()
    dbapi = _FakeDbapi([conexao])
    engine = _FakeEngine(dbapi)

    # select() sempre retorna "sem dados" (timeout): o loop nao bloqueia em
    # socket real e cai direto no drain a cada iteracao.
    monkeypatch.setattr(listener_mod.select, "select", lambda *_a, **_k: ([], [], []))
    # Gauge e heartbeat nao tocam banco/filesystem real neste teste unitario.
    monkeypatch.setattr(listener_mod, "emitir_profundidade", lambda _engine: None)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)

    # call #1 = drain inicial (antes do while, no MESMO guarda-chuva de
    #   resiliencia): retorna 0.
    # call #2 = 1o drain DENTRO do while: levanta erro transitorio de DB — sem
    #   o guarda-chuva propagaria e mataria o processo; o loop deve logar e
    #   CONTINUAR. call #3 = drain seguinte (retorna 0) prova a sobrevivencia.
    chamadas = {"n": 0}

    def processar_ciclo_fake(*_args: Any, **_kwargs: Any) -> int:
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise OperationalError("SELECT 1", {}, Exception("conexao perdida"))
        return 0

    monkeypatch.setattr(listener_mod, "processar_ciclo", processar_ciclo_fake)

    # `parar` encerra apos o 3o ciclo (inicial + o que falha + um que
    # sobrevive) — deterministico mesmo com o parar sendo consultado tambem
    # dentro de `_drenar`.
    def parar() -> bool:
        return chamadas["n"] >= 3

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
    # Houve drain DEPOIS do que falhou (a falha NAO encerrou o loop).
    assert chamadas["n"] >= 3
    # Encerrou de forma limpa: conexao dedicada de LISTEN fechada (nao ha
    # autocommit a restaurar — a conexao nunca pertenceu ao pool).
    assert conexao.fechada is True


# --- Resiliencia da conexao de LISTEN (#165) ---------------------------------


def test_conexao_listen_perdida_reconstroi_e_o_loop_segue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # OperationalError no poll da conexao de LISTEN (failover, socket morto
    # denunciado pelos keepalives) NAO derruba o processo: fecha a conexao
    # velha, reconstroi (novo LISTEN no mesmo canal) e o loop segue drenando.
    primeira = _FakeConexaoListen(falhas_poll=1)
    segunda = _FakeConexaoListen()
    dbapi = _FakeDbapi([primeira, segunda])
    engine = _FakeEngine(dbapi)

    # 1o select: "pronto" (forca o poll, que levanta); demais: timeout.
    selecoes = {"n": 0}

    def select_fake(
        rlist: list[Any], _w: list[Any], _x: list[Any], _timeout: float
    ) -> tuple[list[Any], list[Any], list[Any]]:
        selecoes["n"] += 1
        return (list(rlist), [], []) if selecoes["n"] == 1 else ([], [], [])

    monkeypatch.setattr(listener_mod.select, "select", select_fake)
    monkeypatch.setattr(listener_mod, "emitir_profundidade", lambda _engine: None)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)
    monkeypatch.setattr(listener_mod, "processar_ciclo", lambda *_a, **_k: 0)

    def parar() -> bool:
        return selecoes["n"] >= 2

    with structlog.testing.capture_logs() as logs:
        executar_relay(
            engine,  # type: ignore[arg-type]
            handlers={},
            nome_handler="email",
            relogio=_relogio,
            parar=parar,
        )

    # A queda foi logada como warning e a reconexao como info.
    assert any(log.get("event") == "listen_conexao_perdida" for log in logs)
    assert any(log.get("event") == "listen_reconectado" for log in logs)
    # A conexao velha foi fechada e uma NOVA foi construida com o mesmo
    # setup (LISTEN no canal) — e tambem fechada no encerramento.
    assert primeira.fechada is True
    assert len(dbapi.kwargs_conexoes) == 2
    assert segunda.sql_executado == [f"LISTEN {CANAL_NOTIFY}"]
    assert segunda.autocommit is True
    assert segunda.fechada is True
    # O loop continuou (houve select apos a reconexao) em vez de derrubar.
    assert selecoes["n"] >= 2


def test_reconectar_listen_faz_backoff_dobrado_com_teto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Enquanto o DB nao volta, a reconexao dorme com atraso dobrado ate o
    # teto de 30s (abaixo da janela de 60s da liveness) e toca o heartbeat a
    # cada tentativa — DB fora nao deve virar restart-storm de pod.
    conexao = _FakeConexaoListen()
    tentativas = {"n": 0}

    def conectar_fake(_engine: object) -> _FakeConexaoListen:
        tentativas["n"] += 1
        if tentativas["n"] <= 6:
            raise Psycopg2OperationalError("db fora")
        return conexao

    batidas = {"n": 0}
    monkeypatch.setattr(listener_mod, "_conectar_listen", conectar_fake)
    monkeypatch.setattr(
        listener_mod, "_heartbeat", lambda: batidas.__setitem__("n", batidas["n"] + 1)
    )
    esperas: list[float] = []

    resultado = _reconectar_listen(
        object(),  # type: ignore[arg-type]
        parar=lambda: False,
        dormir=esperas.append,
    )

    assert resultado is conexao
    assert esperas == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]  # dobra ate o teto
    assert batidas["n"] == 6  # heartbeat vivo durante a espera pelo DB


def test_reconectar_listen_encerra_no_sinal_sem_esperar_o_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SIGTERM durante a reconexao: retorna None (o loop encerra) em vez de
    # insistir ate o DB voltar — o grace period do rollout e curto.
    def conectar_fake(_engine: object) -> _FakeConexaoListen:
        raise Psycopg2OperationalError("db fora")

    monkeypatch.setattr(listener_mod, "_conectar_listen", conectar_fake)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)
    sinais = iter([False, False, True])

    resultado = _reconectar_listen(
        object(),  # type: ignore[arg-type]
        parar=lambda: next(sinais),
        dormir=lambda _s: None,
    )

    assert resultado is None


# --- Throttle do gauge de profundidade (log) ---------------------------------


def test_profundidade_nao_loga_a_cada_acorde_ocioso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fila ociosa nao deve logar profundidade a cada poll de 5s: so a cada
    # _ACORDES_POR_LOG acordes (~1/min). O baseline do boot (drain inicial)
    # conta como a 1a emissao.
    conexao = _FakeConexaoListen()
    engine = _FakeEngine(_FakeDbapi([conexao]))
    selecoes = {"n": 0}

    def select_fake(*_args: Any, **_kwargs: Any) -> tuple[list, list, list]:
        selecoes["n"] += 1
        return ([], [], [])

    monkeypatch.setattr(listener_mod.select, "select", select_fake)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)
    monkeypatch.setattr(listener_mod, "processar_ciclo", lambda *_a, **_k: 0)
    emissoes = {"n": 0}
    monkeypatch.setattr(
        listener_mod,
        "emitir_profundidade",
        lambda _engine: emissoes.__setitem__("n", emissoes["n"] + 1),
    )

    def parar() -> bool:
        # 12 acordes ociosos (= _ACORDES_POR_LOG) e encerra.
        return selecoes["n"] >= listener_mod._ACORDES_POR_LOG

    executar_relay(
        engine,  # type: ignore[arg-type]
        handlers={},
        nome_handler="email",
        relogio=_relogio,
        parar=parar,
    )

    # Baseline do boot + 1 emissao no 12o acorde ocioso; se o throttle
    # quebrasse (emissao por acorde) seriam 13.
    assert listener_mod._ACORDES_POR_LOG == 12
    assert emissoes["n"] == 2


def test_profundidade_loga_imediatamente_quando_o_drain_processa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Acorde que processou >= 1 linha loga a profundidade na hora (visibilidade
    # de burst), sem esperar o throttle de acordes ociosos.
    conexao = _FakeConexaoListen()
    engine = _FakeEngine(_FakeDbapi([conexao]))
    selecoes = {"n": 0}

    def select_fake(*_args: Any, **_kwargs: Any) -> tuple[list, list, list]:
        selecoes["n"] += 1
        return ([], [], [])

    monkeypatch.setattr(listener_mod.select, "select", select_fake)
    monkeypatch.setattr(listener_mod, "_heartbeat", lambda: None)
    # Drain inicial vazio; 1o acorde do while processa 1 linha; depois vazio.
    retornos = [0, 1, 0]

    def processar_ciclo_fake(*_args: Any, **_kwargs: Any) -> int:
        return retornos.pop(0) if retornos else 0

    monkeypatch.setattr(listener_mod, "processar_ciclo", processar_ciclo_fake)
    emissoes = {"n": 0}
    monkeypatch.setattr(
        listener_mod,
        "emitir_profundidade",
        lambda _engine: emissoes.__setitem__("n", emissoes["n"] + 1),
    )

    executar_relay(
        engine,  # type: ignore[arg-type]
        handlers={},
        nome_handler="email",
        relogio=_relogio,
        parar=lambda: selecoes["n"] >= 2,
    )

    # Baseline do boot + emissao imediata do acorde que processou (bem antes
    # de 12 acordes).
    assert emissoes["n"] == 2
