from __future__ import annotations

import hashlib
import hmac
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

_logger = logging.getLogger(__name__)


class EncryptionService:
    """Singleton de criptografia simetrica (Fernet) e hash deterministico (HMAC-SHA256).

    A chave vem de ENCRYPTION_KEY. Se ausente, uma chave e gerada em memoria com
    aviso no log (valido apenas para desenvolvimento/teste). Em producao
    multi-replica isso causa inconsistencia entre instancias: ENCRYPTION_KEY deve
    ser definida explicitamente antes do startup.
    """

    _instance: EncryptionService | None = None
    _fernet: Fernet | None = None
    _hmac_key: bytes = b""

    @classmethod
    def instance(cls) -> EncryptionService:
        """Retorna a instancia singleton, criando-a no primeiro acesso."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            _logger.warning(
                "ENCRYPTION_KEY nao configurada; gerando chave efemera. "
                "Em producao defina ENCRYPTION_KEY antes do startup para evitar "
                "inconsistencia entre replicas."
            )
            key = Fernet.generate_key().decode()
        key_bytes = key.encode() if isinstance(key, str) else key
        self._fernet = Fernet(key_bytes)
        self._hmac_key = hashlib.sha256(key_bytes).digest()

    def encrypt(self, plaintext: str) -> str:
        """Cifra o texto com Fernet (AES-128-CBC + HMAC-SHA256)."""
        if not self._fernet:
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decifra um token Fernet; retorna o texto original se o token nao e valido.

        O retorno do texto original e parte do contrato (suporte a valores legados
        ainda nao migrados), entao o fallback e registrado em nivel `debug` para
        evitar ruido em fluxos normais de migracao.
        """
        if not self._fernet:
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            _logger.debug(
                "Valor nao cifrado ou com chave diferente; retornando original."
            )
            return ciphertext

    def hash_deterministic(self, plaintext: str) -> str:
        """HMAC-SHA256 para busca deterministica sem expor o valor original."""
        return hmac.new(self._hmac_key, plaintext.encode(), hashlib.sha256).hexdigest()
