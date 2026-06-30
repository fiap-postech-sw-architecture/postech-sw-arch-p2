"""Assinatura HMAC do webhook de decisao de orcamento (TD-027 / RF-022).

Funcao pura usada nos DOIS lados: o servidor calcula a assinatura esperada e o
chamador (sistema externo / testes / collection do Postman) assina a requisicao.
Substitui o token estatico estilo bearer (ADR-021) por uma assinatura por
requisicao sobre ``{ordem_id}.{timestamp}.`` + body, fechando replay (a janela de
timestamp e validada no servidor) e adulteracao do corpo.
"""

from __future__ import annotations

import hashlib
import hmac

# Janela anti-replay: o servidor recusa timestamps a mais de N segundos do agora.
JANELA_ANTI_REPLAY_SEGUNDOS = 300


def assinar_payload_webhook(
    segredo: str, ordem_id: str, timestamp: str, body: bytes
) -> str:
    """HMAC-SHA256 (hex) sobre ``{ordem_id}.{timestamp}.`` + ``body``.

    ``segredo`` e o ``ORCAMENTO_WEBHOOK_TOKEN`` (agora chave HMAC, nao mais um
    bearer transmitido). Incluir ``ordem_id`` + ``timestamp`` no material assinado
    amarra a assinatura a uma ordem e a um instante -> impede reuso da assinatura
    em outra ordem ou apos a janela.
    """
    mensagem = f"{ordem_id}.{timestamp}.".encode() + body
    return hmac.new(segredo.encode("utf-8"), mensagem, hashlib.sha256).hexdigest()
