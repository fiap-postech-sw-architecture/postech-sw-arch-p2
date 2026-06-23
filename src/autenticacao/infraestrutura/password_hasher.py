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
