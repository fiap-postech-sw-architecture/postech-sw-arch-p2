"""Unitarios do ``SmtpEmailAdapter`` (RF-024 / ADR-018).

``smtplib.SMTP`` e substituido por um fake via monkeypatch: o alvo aqui
e o contrato do adapter (configuracao 12-factor por env, ``EmailMessage``
com From/To/Subject corretos, uso de context manager), nao a pilha SMTP.
"""

from __future__ import annotations

import smtplib
from typing import ClassVar

import pytest

from src.ordem_servico.infraestrutura.email_adapter import SmtpEmailAdapter


class _FakeSMTP:
    instancias: ClassVar[list[_FakeSMTP]] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.mensagens: list[object] = []
        self.fechado = False
        _FakeSMTP.instancias.append(self)

    def __enter__(self) -> _FakeSMTP:
        return self

    def __exit__(self, *args: object) -> None:
        self.fechado = True

    def send_message(self, msg: object) -> None:
        self.mensagens.append(msg)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


class TestSmtpEmailAdapter:
    def test_envia_email_message_com_from_to_subject_e_corpo(
        self, fake_smtp: type[_FakeSMTP], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SMTP_HOST", "mailpit")
        monkeypatch.setenv("SMTP_PORT", "1025")
        monkeypatch.setenv("SMTP_FROM", "oficina@pytstop.local")

        adapter = SmtpEmailAdapter()
        adapter.enviar(
            destinatario="maria@cliente.com",
            assunto="PytStop — Ordem de Servico abc12345: Finalizada",
            corpo="Sua ordem foi finalizada.",
        )

        assert len(fake_smtp.instancias) == 1
        conexao = fake_smtp.instancias[0]
        assert conexao.host == "mailpit"
        assert conexao.port == 1025
        # Timeout finito: envio nunca pode segurar a request indefinidamente.
        assert conexao.timeout is not None
        assert conexao.fechado is True

        assert len(conexao.mensagens) == 1
        msg = conexao.mensagens[0]
        assert msg["From"] == "oficina@pytstop.local"  # type: ignore[index]
        assert msg["To"] == "maria@cliente.com"  # type: ignore[index]
        assert msg["Subject"] == (  # type: ignore[index]
            "PytStop — Ordem de Servico abc12345: Finalizada"
        )
        assert msg.get_content().strip() == "Sua ordem foi finalizada."  # type: ignore[attr-defined]

    def test_defaults_de_configuracao_sem_env(
        self, fake_smtp: type[_FakeSMTP], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("SMTP_PORT", raising=False)
        monkeypatch.delenv("SMTP_FROM", raising=False)

        adapter = SmtpEmailAdapter()
        adapter.enviar(destinatario="x@y.com", assunto="a", corpo="b")

        conexao = fake_smtp.instancias[0]
        assert conexao.host == "localhost"
        assert conexao.port == 1025
        msg = conexao.mensagens[0]
        assert msg["From"] == "oficina@pytstop.local"  # type: ignore[index]

    def test_porta_mal_configurada_falha_no_envio_e_nao_na_construcao(
        self, fake_smtp: type[_FakeSMTP], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Misconfig de env vira falha de ENVIO (engolida pelo handler),
        nunca falha de construcao no composition root — que derrubaria a
        request da transicao inteira antes do use case rodar.
        """
        monkeypatch.setenv("SMTP_PORT", "nao-numerica")

        adapter = SmtpEmailAdapter()  # construcao nunca levanta

        with pytest.raises(ValueError, match="nao-numerica"):
            adapter.enviar(destinatario="x@y.com", assunto="a", corpo="b")
        assert fake_smtp.instancias == []

    def test_falha_de_conexao_propaga_para_o_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O adapter NAO engole falhas: a tolerancia a falha e
        responsabilidade do handler de notificacao (defesa em camada
        unica evita esconder erros de outros usos futuros da porta).
        """

        def smtp_que_recusa(*_args: object, **_kwargs: object) -> object:
            raise ConnectionRefusedError("smtp fora do ar")

        monkeypatch.setattr(smtplib, "SMTP", smtp_que_recusa)

        adapter = SmtpEmailAdapter()
        with pytest.raises(ConnectionRefusedError):
            adapter.enviar(destinatario="x@y.com", assunto="a", corpo="b")
