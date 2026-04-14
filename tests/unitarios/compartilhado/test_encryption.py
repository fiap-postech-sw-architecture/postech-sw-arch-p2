from __future__ import annotations

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
