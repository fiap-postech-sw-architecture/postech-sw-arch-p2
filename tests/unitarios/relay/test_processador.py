from __future__ import annotations

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
        # erros_retry/erros_dead capturam o texto de erro persistido (para
        # asseverar que PII foi redacted antes de gravar no banco).
        self.erros_retry: list[str] = []
        self.erros_dead: list[str] = []
        self._ja_processado = ja_processado

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
_MARCADOR_REDACAO = "@"  # parte do dominio permanece; so o local e redacted


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
