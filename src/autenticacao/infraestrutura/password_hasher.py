from __future__ import annotations

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

_TAMANHO_MINIMO_SENHA = 12
_TAMANHO_MAXIMO_SENHA = 128
_hasher = PasswordHash((BcryptHasher(),))


def hash_senha(senha: str) -> str:
    if len(senha) < _TAMANHO_MINIMO_SENHA:
        msg = f"Senha deve ter pelo menos {_TAMANHO_MINIMO_SENHA} caracteres"
        raise ValueError(msg)
    if len(senha) > _TAMANHO_MAXIMO_SENHA:
        msg = f"Senha deve ter no maximo {_TAMANHO_MAXIMO_SENHA} caracteres"
        raise ValueError(msg)
    return _hasher.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return _hasher.verify(senha_plana, senha_hash)
