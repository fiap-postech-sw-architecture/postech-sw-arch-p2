from __future__ import annotations

from uuid import uuid4

import pytest

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.password_hasher import (
    hash_senha,
    verificar_senha,
)


class TestUsuario:
    def test_criar_armazena_hash(self) -> None:
        senha_hash = hash_senha("senhaforte1234")
        u = Usuario.criar(
            email="test@test.com", senha_hash=senha_hash, papel=Papel.ADMIN
        )
        assert u.senha_hash == senha_hash

    def test_verificar_senha_correta(self) -> None:
        senha_hash = hash_senha("senhaforte1234")
        u = Usuario.criar(
            email="test@test.com", senha_hash=senha_hash, papel=Papel.ADMIN
        )
        assert verificar_senha("senhaforte1234", u.senha_hash) is True

    def test_verificar_senha_incorreta(self) -> None:
        senha_hash = hash_senha("senhaforte1234")
        u = Usuario.criar(
            email="test@test.com", senha_hash=senha_hash, papel=Papel.ADMIN
        )
        assert verificar_senha("outrasenha1234", u.senha_hash) is False

    def test_email_invalido(self) -> None:
        with pytest.raises(ValueError, match="Email invalido"):
            Usuario(_email="invalido", _senha_hash="x", _papel=Papel.ADMIN)

    def test_senha_curta(self) -> None:
        with pytest.raises(ValueError, match="Senha deve ter"):
            hash_senha("123")

    def test_propriedades(self) -> None:
        senha_hash = hash_senha("senhaforte1234")
        u = Usuario.criar(
            email="test@test.com", senha_hash=senha_hash, papel=Papel.ADMIN
        )
        assert u.email == "test@test.com"
        assert u.papel == Papel.ADMIN

    def test_identidade_por_id(self) -> None:
        id_fixo = uuid4()
        a = Usuario(
            id=id_fixo,
            _email="a@a.com",
            _senha_hash="x",
            _papel=Papel.ADMIN,
        )
        b = Usuario(
            id=id_fixo,
            _email="b@b.com",
            _senha_hash="y",
            _papel=Papel.ADMIN,
        )
        assert a == b

    def test_email_sem_ponto_no_dominio_invalido(self) -> None:
        with pytest.raises(ValueError, match="Email invalido"):
            Usuario(_email="user@dominio", _senha_hash="x", _papel=Papel.ADMIN)

    def test_email_sem_local_part_invalido(self) -> None:
        with pytest.raises(ValueError, match="Email invalido"):
            Usuario(_email="@dominio.com", _senha_hash="x", _papel=Papel.ADMIN)

    def test_email_sem_dominio_invalido(self) -> None:
        with pytest.raises(ValueError, match="Email invalido"):
            Usuario(_email="user@", _senha_hash="x", _papel=Papel.ADMIN)


class TestReprSemPii:
    """Finding da revisao de entrega: repr default vazava e-mail e hash."""

    def test_repr_nao_expoe_email_nem_hash(self) -> None:
        usuario = Usuario(
            _email="fulano@example.com",
            _senha_hash="$2b$12$hash-sensivel",
            _papel=Papel.ADMIN,
        )
        texto = repr(usuario)
        assert "fulano@example.com" not in texto
        assert "$2b$12$" not in texto
