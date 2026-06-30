from __future__ import annotations

import base64
import hashlib

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

_TAMANHO_MINIMO_SENHA = 12
_TAMANHO_MAXIMO_SENHA = 128
# bcrypt processa no maximo 72 bytes; o pre-hash (TD-028) garante caber, mas o
# fallback legado so e tentado quando a senha crua cabe nesse limite.
_BCRYPT_MAX_BYTES = 72
_hasher = PasswordHash((BcryptHasher(),))


def _pre_hash(senha: str) -> str:
    """Pre-hash sha256+base64 para remover o truncamento de 72 bytes do bcrypt (TD-028).

    O bcrypt ignora bytes alem de 72, entao senhas longas com prefixo comum
    colidiriam. O digest SHA-256 (32 bytes -> 44 chars base64) cabe sob o limite
    e distribui toda a entropia da senha pelos 72 bytes. Mesma estrategia do
    `bcrypt_sha256` do passlib.
    """
    digest = hashlib.sha256(senha.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def hash_senha(senha: str) -> str:
    if len(senha) < _TAMANHO_MINIMO_SENHA:
        msg = f"Senha deve ter pelo menos {_TAMANHO_MINIMO_SENHA} caracteres"
        raise ValueError(msg)
    if len(senha) > _TAMANHO_MAXIMO_SENHA:
        msg = f"Senha deve ter no maximo {_TAMANHO_MAXIMO_SENHA} caracteres"
        raise ValueError(msg)
    return _hasher.hash(_pre_hash(senha))


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    # Esquema atual (TD-028): pre-hash sha256 antes do bcrypt. Uma falha aqui cai
    # para o esquema legado abaixo -- ate dois bcrypt verify no pior caso, custo
    # dominado pelo proprio bcrypt; a janela existe so ate o reseed dos hashes no
    # deploy, que extingue os hashes legados.
    if _hasher.verify(_pre_hash(senha_plana), senha_hash):
        return True
    # Compat de migracao: hashes gerados antes do TD-028 foram computados sobre
    # a senha crua. O bcrypt REJEITA (nao trunca) senhas > 72 bytes no verify, e
    # um hash legado so pode ter vindo de uma senha que coube em 72 bytes --
    # entao so tentamos o esquema legado quando a senha cabe.
    if len(senha_plana.encode("utf-8")) <= _BCRYPT_MAX_BYTES:
        return _hasher.verify(senha_plana, senha_hash)
    return False


class PasswordHasher:
    """Adapter de `PasswordHasherPort` sobre pwdlib (bcrypt).

    Delega para as funcoes de modulo `hash_senha`/`verificar_senha`, expondo-as
    como uma instancia injetavel na camada de aplicacao (que depende do port,
    nunca deste modulo).
    """

    def hash_senha(self, senha: str) -> str:
        return hash_senha(senha)

    def verificar_senha(self, senha_plana: str, senha_hash: str) -> bool:
        return verificar_senha(senha_plana, senha_hash)
