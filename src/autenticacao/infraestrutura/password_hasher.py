from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

_TAMANHO_MINIMO_SENHA = 12
_hasher = PasswordHash((BcryptHasher(),))


def hash_senha(senha: str) -> str:
    if len(senha) < _TAMANHO_MINIMO_SENHA:
        msg = f"Senha deve ter pelo menos {_TAMANHO_MINIMO_SENHA} caracteres"
        raise ValueError(msg)
    if len(senha) > 128:
        msg = "Senha deve ter no maximo 128 caracteres"
        raise ValueError(msg)
    return _hasher.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return _hasher.verify(senha_plana, senha_hash)
