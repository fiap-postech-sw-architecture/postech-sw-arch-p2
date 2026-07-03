"""Adapter SMTP da ``EmailPort`` (RF-024 / ADR-018).

SMTP generico via ``smtplib`` (stdlib — nenhuma dependencia nova),
configurado 12-factor por variaveis de ambiente:

- ``SMTP_HOST`` (default ``localhost``)
- ``SMTP_PORT`` (default ``1025`` — porta SMTP do Mailpit)
- ``SMTP_FROM`` (default ``oficina@pytstop.local``)

Em dev/demo o servidor e o Mailpit do docker-compose (UI em
``http://localhost:8025``); trocar para um relay real (ex.: SES via
interface SMTP) e mudanca de configuracao, nao de codigo. Credenciais,
quando existirem, entram por Secret no cluster (RNF-020).

Falhas de transporte (conexao, timeout, protocolo) sao traduzidas em
``FalhaEnvioEmailException`` e PROPAGAM: o handler
``NotificarMudancaDeStatus`` loga e repassa ao relay da outbox, que dirige
retry -> backoff -> DLQ (TD-008).
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from src.ordem_servico.aplicacao.ports import FalhaEnvioEmailException

# Envio sincrono no ciclo de entrega do relay: timeout curto impede que um
# SMTP que aceita conexao mas nao responde prenda o worker da outbox.
_TIMEOUT_SEGUNDOS = 5


class SmtpEmailAdapter:
    """Realiza ``EmailPort`` falando SMTP puro com o servidor configurado.

    A configuracao e lida do ambiente DENTRO de ``enviar`` (nao no
    ``__init__``): o adapter e construido pelo relay a cada entrega
    (``relay/handlers.py``), e um ``SMTP_PORT`` mal formado no construtor
    quebraria a montagem do mapa de handlers — lendo no envio, qualquer
    misconfig vira falha de envio, tratada linha a linha (retry/DLQ).
    """

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        """Envia um e-mail texto-plano via SMTP.

        Raises:
            ValueError: ``SMTP_PORT`` configurado com valor nao numerico.
            FalhaEnvioEmailException: falha de conexao/timeout com o
                servidor SMTP ou erro de protocolo durante o envio.
        """
        host = os.environ.get("SMTP_HOST", "localhost")
        port = int(os.environ.get("SMTP_PORT", "1025"))
        remetente = os.environ.get("SMTP_FROM", "oficina@pytstop.local")
        msg = EmailMessage()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.set_content(corpo)
        try:
            with smtplib.SMTP(host, port, timeout=_TIMEOUT_SEGUNDOS) as conexao:
                conexao.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            # Traduz o transporte concreto para a excecao da porta: a
            # aplicacao (handler) nao conhece smtplib.
            raise FalhaEnvioEmailException(str(exc)) from exc
