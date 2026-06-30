from __future__ import annotations

from src.autenticacao.infraestrutura.password_hasher import (
    _hasher,
    hash_senha,
    verificar_senha,
)


class TestPasswordHasher:
    def test_roundtrip(self) -> None:
        h = hash_senha("senhaforte1234")
        assert verificar_senha("senhaforte1234", h)

    def test_senha_errada_falha(self) -> None:
        h = hash_senha("senhaforte1234")
        assert not verificar_senha("senhaerrada9999", h)

    def test_senhas_longas_com_prefixo_72b_nao_colidem(self) -> None:
        """TD-028: o pre-hash sha256 remove o truncamento de 72 bytes do bcrypt.

        Duas senhas que compartilham os primeiros 72 bytes mas diferem depois
        NAO podem verificar uma contra o hash da outra. Sem o pre-hash, o bcrypt
        truncaria ambas no mesmo prefixo de 72 bytes e elas colidiriam.
        """
        base = "A" * 72  # exatamente o limite do bcrypt
        senha1 = base + "diferente-um"
        senha2 = base + "diferente-dois"
        h1 = hash_senha(senha1)
        assert verificar_senha(senha1, h1)
        assert not verificar_senha(senha2, h1)

    def test_verifica_hash_legado_sobre_senha_crua(self) -> None:
        """Compat de migracao: hash do esquema antigo (senha crua) ainda verifica."""
        senha = "senhaforte1234"
        legado = _hasher.hash(senha)  # esquema pre-TD-028: bcrypt sobre a senha crua
        assert verificar_senha(senha, legado)
