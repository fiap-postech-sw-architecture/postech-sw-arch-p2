from __future__ import annotations

import pytest
from cryptography.fernet import InvalidToken

from src.compartilhado.infraestrutura.encryption import EncryptionService


class TestEncryptionService:
    def test_encrypt_decrypt_roundtrip(self) -> None:
        enc = EncryptionService()
        plaintext = "12345678901"
        ciphertext = enc.encrypt(plaintext)
        assert ciphertext != plaintext
        assert enc.decrypt(ciphertext) == plaintext

    def test_decrypt_unencrypted_returns_original(self) -> None:
        enc = EncryptionService()
        raw = "12345678901"
        assert enc.decrypt(raw) == raw

    def test_encrypt_produces_different_ciphertext(self) -> None:
        enc = EncryptionService()
        text = "12345678901"
        c1 = enc.encrypt(text)
        c2 = enc.encrypt(text)
        assert c1 != c2

    def test_singleton_retorna_mesma_instancia(self) -> None:
        EncryptionService._instance = None
        a = EncryptionService.instance()
        b = EncryptionService.instance()
        assert a is b
        EncryptionService._instance = None

    def test_hash_deterministic_retorna_hex(self) -> None:
        enc = EncryptionService()
        resultado = enc.hash_deterministic("12345678901")
        assert isinstance(resultado, str)
        assert len(resultado) == 64

    def test_hash_deterministic_mesmo_input_mesmo_output(self) -> None:
        enc = EncryptionService()
        h1 = enc.hash_deterministic("12345678901")
        h2 = enc.hash_deterministic("12345678901")
        assert h1 == h2

    def test_hash_deterministic_inputs_diferentes_outputs_diferentes(self) -> None:
        enc = EncryptionService()
        h1 = enc.hash_deterministic("12345678901")
        h2 = enc.hash_deterministic("98765432100")
        assert h1 != h2

    def test_encrypt_sem_fernet_retorna_plaintext(self) -> None:
        enc = EncryptionService()
        enc._fernet = None
        resultado = enc.encrypt("texto")
        assert resultado == "texto"

    def test_decrypt_sem_fernet_retorna_ciphertext(self) -> None:
        enc = EncryptionService()
        enc._fernet = None
        resultado = enc.decrypt("cifrado")
        assert resultado == "cifrado"

    def test_decrypt_token_corrompido_levanta(self) -> None:
        """Token COM prefixo Fernet que falha integridade -> raise (issue #73).

        Garante que o ``decrypt`` NAO faz fail-open: um token cifrado que nao
        decifra (chave errada / corrompido) propaga ``InvalidToken`` em vez de
        devolver o ciphertext como se fosse o valor decifrado.
        """
        enc = EncryptionService()
        token = enc.encrypt("12345678901")
        assert token.startswith("gAAAAA")
        # Corrompe um caractere do corpo (mantendo o prefixo e base64 valido) ->
        # o HMAC do Fernet falha.
        pos = 20
        char_novo = "X" if token[pos] != "X" else "Y"
        corrompido = token[:pos] + char_novo + token[pos + 1 :]
        with pytest.raises(InvalidToken):
            enc.decrypt(corrompido)

    def test_decrypt_legado_sem_prefixo_nao_levanta(self) -> None:
        """Valor SEM o prefixo Fernet (legado) -> devolvido como esta (#73)."""
        enc = EncryptionService()
        # O sentinela LGPD e valores legados em texto plano nao tem prefixo gAAAAA.
        assert enc.decrypt("anonimizado@anonimizado.local") == (
            "anonimizado@anonimizado.local"
        )
        assert enc.decrypt("12345678901") == "12345678901"
