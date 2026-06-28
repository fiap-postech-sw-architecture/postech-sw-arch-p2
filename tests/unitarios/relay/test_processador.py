from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

import relay.processador as processador_modulo
from relay.processador import LinhaOutbox, processar_linha

if TYPE_CHECKING:
    from collections.abc import Callable


class _ConnFake:
    """Captura os efeitos colaterais de processar_linha (sem banco)."""

    def __init__(self, ja_processado: bool = False, bloquear: bool = True) -> None:
        self.marcado_entregue: list[int] = []
        self.marcado_processed: list[tuple[int, str]] = []
        self.agendado_retry: list[tuple[int, int]] = []
        # marcar_dead grava o valor EXPLICITO de tentativas (F5): captura
        # (outbox_id, tentativas) para asseverar o valor gravado.
        self.marcado_dead: list[tuple[int, int]] = []
        # erros_retry/erros_dead capturam o texto de erro persistido (para
        # asseverar que PII foi redacted antes de gravar no banco).
        self.erros_retry: list[str] = []
        self.erros_dead: list[str] = []
        # bloqueados captura os ids para os quais o fencing foi consultado
        # (TD-021): o re-lock `FOR UPDATE SKIP LOCKED` na tx por-linha.
        self.bloqueados: list[int] = []
        self._ja_processado = ja_processado
        self._bloquear = bloquear

    def bloquear_para_entrega(self, outbox_id: int) -> bool:
        self.bloqueados.append(outbox_id)
        return self._bloquear

    def ja_processado(self, outbox_id: int, handler: str) -> bool:
        return self._ja_processado

    def marcar_entregue(self, outbox_id: int) -> None:
        self.marcado_entregue.append(outbox_id)

    def registrar_processed(self, outbox_id: int, handler: str) -> None:
        self.marcado_processed.append((outbox_id, handler))

    def agendar_retry(self, outbox_id: int, tentativas: int, erro: str) -> None:
        self.agendado_retry.append((outbox_id, tentativas))
        self.erros_retry.append(erro)

    def marcar_dead(self, outbox_id: int, tentativas: int, erro: str) -> None:
        self.marcado_dead.append((outbox_id, tentativas))
        self.erros_dead.append(erro)

    def tem_sucessor_pendente(self, agregado_id: object, outbox_id: int) -> bool:
        # Fake: por padrao sem sucessor (testes de DLQ pura nao se importam
        # com o gap; o alerta de sucessor e coberto no teste de integracao).
        return False


def _linha(tentativas: int = 0) -> LinhaOutbox:
    return LinhaOutbox(
        id=42,
        agregado_id=uuid4(),
        tipo="DiagnosticoIniciadoEvent",
        payload={"agregado_id": str(uuid4())},
        tentativas=tentativas,
    )


def test_sucesso_marca_entregue_e_processed() -> None:
    conn = _ConnFake()
    chamado: list[dict] = []

    def handler(payload: dict) -> None:
        chamado.append(payload)

    processar_linha(
        conn,
        _linha(),
        handlers={"DiagnosticoIniciadoEvent": handler},
        nome_handler="email",
    )

    assert len(chamado) == 1
    assert conn.marcado_entregue == [42]
    assert conn.marcado_processed == [(42, "email")]
    assert conn.agendado_retry == []
    assert conn.marcado_dead == []


def test_idempotencia_pula_handler_ja_processado() -> None:
    conn = _ConnFake(ja_processado=True)
    chamado: list[dict] = []

    processar_linha(
        conn,
        _linha(),
        handlers={"DiagnosticoIniciadoEvent": lambda p: chamado.append(p)},
        nome_handler="email",
    )

    assert chamado == []  # nao invoca o handler
    assert conn.marcado_entregue == [42]  # mas marca entregue (idempotente)
    assert conn.marcado_processed == []


def test_fencing_falho_pula_entrega_sem_chamar_handler() -> None:
    # TD-021: se o re-lock da linha falha (outra replica detem a entrega, ou a
    # linha nao esta mais `pendente`), processar_linha aborta ANTES de tocar no
    # handler ou em qualquer efeito de conclusao — nao duplica a entrega.
    conn = _ConnFake(bloquear=False)
    chamado: list[dict] = []

    processar_linha(
        conn,
        _linha(),
        handlers={"DiagnosticoIniciadoEvent": lambda p: chamado.append(p)},
        nome_handler="email",
    )

    assert conn.bloqueados == [42]  # o fencing foi consultado
    assert chamado == []  # handler NAO invocado
    assert conn.marcado_entregue == []
    assert conn.marcado_processed == []
    assert conn.agendado_retry == []
    assert conn.marcado_dead == []


def test_falha_agenda_retry_com_tentativas_incrementadas() -> None:
    conn = _ConnFake()

    def handler_quebrado(_payload: dict) -> None:
        raise RuntimeError("smtp fora")

    processar_linha(
        conn,
        _linha(tentativas=0),
        handlers={"DiagnosticoIniciadoEvent": handler_quebrado},
        nome_handler="email",
    )

    assert conn.agendado_retry == [(42, 1)]
    assert conn.marcado_dead == []
    assert conn.marcado_entregue == []


def test_falha_na_quinta_tentativa_vai_para_dlq() -> None:
    conn = _ConnFake()

    def handler_quebrado(_payload: dict) -> None:
        raise RuntimeError("smtp fora")

    processar_linha(
        conn,
        _linha(tentativas=4),  # 4 falhas previas; esta e a 5a
        handlers={"DiagnosticoIniciadoEvent": handler_quebrado},
        nome_handler="email",
    )

    # marcar_dead recebe o valor explicito de tentativas (5), igual ao que
    # agendar_retry gravaria — sem incremento extra no UPDATE (F5).
    assert conn.marcado_dead == [(42, 5)]
    assert conn.agendado_retry == []


def test_sem_handler_vai_para_dlq_preservando_tentativas() -> None:
    # Sem handler registrado a linha vai pra DLQ sem incrementar tentativas
    # (nao houve tentativa de entrega); marcar_dead recebe linha.tentativas.
    conn = _ConnFake()

    processar_linha(
        conn,
        _linha(tentativas=2),
        handlers={},  # tipo sem handler
        nome_handler="email",
    )

    assert conn.marcado_dead == [(42, 2)]
    assert conn.agendado_retry == []
    assert conn.marcado_entregue == []


# ---------------------------------------------------------------------------
# Testes de redacao de PII (LGPD): e-mail nao deve aparecer em ultimo_erro
# ---------------------------------------------------------------------------

_EMAIL_RAW = "cliente@example.com"


def test_pii_email_redacted_em_agendar_retry() -> None:
    """Falha de handler com e-mail na mensagem: ultimo_erro nao contem o e-mail bruto.

    Simula uma excecao cujo str() contem um endereco de e-mail (como
    smtplib.SMTPRecipientsRefused faria), verifica que o texto gravado via
    agendar_retry nao contem o e-mail original (LGPD/Finding-1 PR#56).
    """
    conn = _ConnFake()

    def handler_smtp(_payload: dict) -> None:
        raise RuntimeError(
            f"SMTPRecipientsRefused: {{'{_EMAIL_RAW}': (550, b'User unknown')}}"
        )

    processar_linha(
        conn,
        _linha(tentativas=0),
        handlers={"DiagnosticoIniciadoEvent": handler_smtp},
        nome_handler="email",
    )

    assert conn.agendado_retry  # chegou a agendar_retry
    erro_persistido = conn.erros_retry[0]
    assert _EMAIL_RAW not in erro_persistido, (
        f"PII nao redacted: e-mail bruto encontrado em ultimo_erro: {erro_persistido!r}"
    )
    # Garante que o tipo da excecao (util, sem PII) ainda esta presente
    assert "RuntimeError" in erro_persistido


def test_pii_email_redacted_em_marcar_dead() -> None:
    """Falha repetida com e-mail na excecao: ultimo_erro na DLQ nao contem PII.

    Quinta tentativa → marcar_dead; verifica que o e-mail nao foi gravado.
    """
    conn = _ConnFake()

    def handler_smtp(_payload: dict) -> None:
        raise RuntimeError(f"SMTPSenderRefused: (501, b'Bad sender', '{_EMAIL_RAW}')")

    processar_linha(
        conn,
        _linha(tentativas=4),  # 4 falhas previas; esta e a 5a → DLQ
        handlers={"DiagnosticoIniciadoEvent": handler_smtp},
        nome_handler="email",
    )

    assert conn.marcado_dead  # chegou a marcar_dead
    erro_persistido = conn.erros_dead[0]
    assert _EMAIL_RAW not in erro_persistido, (
        "PII nao redacted: e-mail bruto encontrado em ultimo_erro "
        f"(DLQ): {erro_persistido!r}"
    )
    assert "RuntimeError" in erro_persistido


# ---------------------------------------------------------------------------
# Wiring transicao -> contador da fachada de metricas (TD-022)
#
# Trava o mapeamento transicao->contador: cada caminho de `processar_linha`
# (sucesso / falha-com-retry / falha-no-DLQ / config sem handler) deve disparar
# EXATAMENTE os contadores certos da fachada `metricas`. Sem isto, uma fiacao
# trocada (ex.: `metricas.falha()` no caminho de sucesso, ou esquecer
# `metricas.dead()` no DLQ) passaria silenciosa — os contadores OTel/Prometheus
# do ADR-024 mentiriam sem nenhum teste vermelho.
# ---------------------------------------------------------------------------


class _FachadaMetricasFake:
    """Registra, em ordem, qual contador da fachada foi disparado."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def entregue(self) -> None:
        self.chamadas.append("entregue")

    def falha(self) -> None:
        self.chamadas.append("falha")

    def dead(self) -> None:
        self.chamadas.append("dead")

    def retry(self) -> None:
        self.chamadas.append("retry")


@pytest.fixture
def metricas_fake(monkeypatch: pytest.MonkeyPatch) -> _FachadaMetricasFake:
    # processar_linha usa `metricas` via binding de modulo
    # (`from relay.metrics import metricas`): faz patch do nome no modulo do
    # processador para espionar as transicoes -> contadores.
    fake = _FachadaMetricasFake()
    monkeypatch.setattr(processador_modulo, "metricas", fake)
    return fake


def _processar(
    conn: _ConnFake,
    linha: LinhaOutbox,
    handler: Callable[[dict[str, Any]], None],
) -> None:
    processar_linha(
        conn,
        linha,
        handlers={"DiagnosticoIniciadoEvent": handler},
        nome_handler="email",
    )


def test_metrica_sucesso_dispara_so_entregue(
    metricas_fake: _FachadaMetricasFake,
) -> None:
    _processar(_ConnFake(), _linha(), lambda _p: None)

    # Sucesso conta SO entregue — nunca falha/dead/retry.
    assert metricas_fake.chamadas == ["entregue"]


def test_metrica_falha_com_retry_dispara_falha_e_retry(
    metricas_fake: _FachadaMetricasFake,
) -> None:
    def handler_quebrado(_payload: dict) -> None:
        raise RuntimeError("smtp fora")

    # tentativas=0 -> 1a falha, ainda ha retries: falha + retry, nunca dead.
    _processar(_ConnFake(), _linha(tentativas=0), handler_quebrado)

    assert metricas_fake.chamadas == ["falha", "retry"]
    assert "dead" not in metricas_fake.chamadas
    assert "entregue" not in metricas_fake.chamadas


def test_metrica_falha_no_maximo_dispara_falha_e_dead(
    metricas_fake: _FachadaMetricasFake,
) -> None:
    def handler_quebrado(_payload: dict) -> None:
        raise RuntimeError("smtp fora")

    # tentativas=4 -> esta e a 5a (maximo): falha + dead, nunca retry.
    _processar(_ConnFake(), _linha(tentativas=4), handler_quebrado)

    assert metricas_fake.chamadas == ["falha", "dead"]
    assert "retry" not in metricas_fake.chamadas
    assert "entregue" not in metricas_fake.chamadas


def test_metrica_sem_handler_dispara_so_dead(
    metricas_fake: _FachadaMetricasFake,
) -> None:
    # Config invalida (tipo sem handler) -> DLQ direto: so dead, sem falha
    # (nao houve tentativa de entrega) e sem entregue/retry.
    processar_linha(
        _ConnFake(),
        _linha(tentativas=2),
        handlers={},
        nome_handler="email",
    )

    assert metricas_fake.chamadas == ["dead"]


def test_metrica_idempotente_nao_dispara_contador(
    metricas_fake: _FachadaMetricasFake,
) -> None:
    # Linha ja processada (crash apos handler): marca entregue mas NAO
    # reconta — o contador ja subiu no ciclo que executou o handler.
    _processar(_ConnFake(ja_processado=True), _linha(), lambda _p: None)

    assert metricas_fake.chamadas == []
