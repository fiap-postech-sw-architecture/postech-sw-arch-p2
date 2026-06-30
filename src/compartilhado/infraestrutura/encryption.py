from __future__ import annotations

import hashlib
import hmac
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

_logger = logging.getLogger(__name__)

# Prefixo dos tokens Fernet (versao 0x80 + timestamp, base64url) -- distingue um
# valor cifrado de um valor legado em texto plano. Mesma heuristica de mapping.py.
# Os 6 chars sao estaveis enquanto o timestamp couber em < 2^40s (ano ~36000);
# alem disso o 6o char muda. Garantido na pratica para qualquer dado real.
_PREFIXO_FERNET = "gAAAAA"


class EncryptionService:
    """Singleton de criptografia simetrica (Fernet) e hash deterministico (HMAC-SHA256).

    A chave vem de ENCRYPTION_KEY. Se ausente, uma chave e gerada em memoria com
    aviso no log -- caminho **somente de desenvolvimento/teste**. Em producao o
    boot e abortado por `validar_segredos_no_startup` (issue #73) quando
    ENCRYPTION_KEY esta ausente, justamente porque a chave efemera tornaria os
    dados cifrados irrecuperaveis apos restart e divergiria o `documento_hash`
    entre replicas. Portanto este fallback so e alcancavel fora de producao.
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
        """Decifra um token Fernet, distinguindo dado legado de falha real (issue #73).

        Um valor SEM o prefixo Fernet (`gAAAAA`) e tratado como legado em texto
        plano ainda nao cifrado e devolvido como esta (compat de migracao -- a
        mesma heuristica que `mapping.py` usa antes de chamar este metodo). Um
        valor COM o prefixo que falha a decifragem e uma quebra REAL de
        integridade/chave -> levanta `InvalidToken`. NAO faz fail-open devolvendo
        o ciphertext: isso mascararia a falha e exporia o token como se fosse o
        valor decifrado.
        """
        if not self._fernet:
            return ciphertext
        if not ciphertext.startswith(_PREFIXO_FERNET):
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            _logger.error(
                "Falha ao decifrar um token Fernet (chave incorreta ou dado "
                "corrompido); propagando o erro em vez de fazer fail-open."
            )
            raise

    def hash_deterministic(self, plaintext: str) -> str:
        """HMAC-SHA256 para busca deterministica sem expor o valor original."""
        return hmac.new(self._hmac_key, plaintext.encode(), hashlib.sha256).hexdigest()
