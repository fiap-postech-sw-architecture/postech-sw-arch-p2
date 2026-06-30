from __future__ import annotations

from src.compartilhado.infraestrutura.webhook_signature import (
    assinar_payload_webhook,
)


class TestAssinarPayloadWebhook:
    def test_deterministico_e_hex_sha256(self) -> None:
        a = assinar_payload_webhook("segredo", "ordem-1", "1700000000", b"corpo")
        b = assinar_payload_webhook("segredo", "ordem-1", "1700000000", b"corpo")
        assert a == b
        assert len(a) == 64  # HMAC-SHA256 em hex
        int(a, 16)  # e hexadecimal valido

    def test_segredo_diferente_muda_assinatura(self) -> None:
        assert assinar_payload_webhook("s1", "o", "1", b"b") != assinar_payload_webhook(
            "s2", "o", "1", b"b"
        )

    def test_ordem_diferente_muda_assinatura(self) -> None:
        # Amarra a assinatura a uma ordem -> nao da pra reusar em outra OS.
        assert assinar_payload_webhook("s", "o1", "1", b"b") != assinar_payload_webhook(
            "s", "o2", "1", b"b"
        )

    def test_timestamp_diferente_muda_assinatura(self) -> None:
        assert assinar_payload_webhook("s", "o", "1", b"b") != assinar_payload_webhook(
            "s", "o", "2", b"b"
        )

    def test_corpo_diferente_muda_assinatura(self) -> None:
        # Cobre adulteracao do corpo.
        assert assinar_payload_webhook(
            "s", "o", "1", b'{"decisao":"aprovada"}'
        ) != assinar_payload_webhook("s", "o", "1", b'{"decisao":"recusada"}')
