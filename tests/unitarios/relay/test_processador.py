from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from relay.processador import LinhaOutbox, processar_linha


class _ConnFake:
    """Captura os efeitos colaterais de processar_linha (sem banco)."""

    def __init__(self, ja_processado: bool = False) -> None:
        self.marcado_entregue: list[int] = []
        self.marcado_processed: list[tuple[int, str]] = []
        self.agendado_retry: list[tuple[int, int]] = []
        # marcar_dead grava o valor EXPLICITO de tentativas (F5): captura
        # (outbox_id, tentativas) para asseverar o valor gravado.
        self.marcado_dead: list[tuple[int, int]] = []
        self._ja_processado = ja_processado

    def ja_processado(self, outbox_id: int, handler: str) -> bool:
        return self._ja_processado

    def marcar_entregue(self, outbox_id: int) -> None:
        self.marcado_entregue.append(outbox_id)

    def registrar_processed(self, outbox_id: int, handler: str) -> None:
        self.marcado_processed.append((outbox_id, handler))

    def agendar_retry(self, outbox_id: int, tentativas: int, erro: str) -> None:
        self.agendado_retry.append((outbox_id, tentativas))

    def marcar_dead(self, outbox_id: int, tentativas: int, erro: str) -> None:
        self.marcado_dead.append((outbox_id, tentativas))

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
        agora=datetime.now(UTC),
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
        agora=datetime.now(UTC),
    )

    assert chamado == []  # nao invoca o handler
    assert conn.marcado_entregue == [42]  # mas marca entregue (idempotente)
    assert conn.marcado_processed == []


def test_falha_agenda_retry_com_tentativas_incrementadas() -> None:
    conn = _ConnFake()

    def handler_quebrado(_payload: dict) -> None:
        raise RuntimeError("smtp fora")

    processar_linha(
        conn,
        _linha(tentativas=0),
        handlers={"DiagnosticoIniciadoEvent": handler_quebrado},
        nome_handler="email",
        agora=datetime.now(UTC),
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
        agora=datetime.now(UTC),
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
        agora=datetime.now(UTC),
    )

    assert conn.marcado_dead == [(42, 2)]
    assert conn.agendado_retry == []
    assert conn.marcado_entregue == []
