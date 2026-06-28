from __future__ import annotations

import pytest

from src.cliente_veiculo.dominio.contato import Contato


class TestContato:
    def test_email_valido(self) -> None:
        contato = Contato(valor="a@b.com")
        assert contato.valor == "a@b.com"

    def test_telefone_valido(self) -> None:
        contato = Contato(valor="+55 11 99999-0000")
        assert contato.valor == "+55 11 99999-0000"

    def test_misto_nome_email_telefone(self) -> None:
        valor = "Maria - maria@x.com / (11) 99999-0000"
        contato = Contato(valor=valor)
        assert contato.valor == valor

    def test_strip_remove_espacos_nas_pontas(self) -> None:
        contato = Contato(valor="  maria@x.com  ")
        assert contato.valor == "maria@x.com"

    def test_vazio_invalido(self) -> None:
        with pytest.raises(ValueError, match="contato nao pode ser vazio"):
            Contato(valor="")

    def test_somente_espacos_invalido(self) -> None:
        with pytest.raises(ValueError, match="contato nao pode ser vazio"):
            Contato(valor="   ")

    def test_maior_que_255_invalido(self) -> None:
        with pytest.raises(ValueError, match="255"):
            Contato(valor="a" * 256)

    def test_limite_255_aceito(self) -> None:
        valor = "a" * 255
        contato = Contato(valor=valor)
        assert contato.valor == valor

    def test_valor_lgpd_anonimizado_aceito(self) -> None:
        # O raw UPDATE de ``anonimizar_dados`` grava
        # ``contato="anonimizado@anonimizado.local"`` direto na coluna,
        # bypassando o ORM; ao recarregar, o listener reidrata pelo VO.
        # O VO PRECISA aceitar esse sentinela (texto livre nao-vazio).
        contato = Contato(valor="anonimizado@anonimizado.local")
        assert contato.valor == "anonimizado@anonimizado.local"

    def test_igualdade_mesmo_valor(self) -> None:
        a = Contato(valor="maria@x.com")
        b = Contato(valor="maria@x.com")
        assert a == b

    def test_desigualdade_valor_diferente(self) -> None:
        a = Contato(valor="maria@x.com")
        b = Contato(valor="joao@x.com")
        assert a != b

    def test_imutabilidade(self) -> None:
        contato = Contato(valor="maria@x.com")
        with pytest.raises(AttributeError):
            contato.valor = "outro@x.com"  # type: ignore[misc]

    def test_hash_consistente(self) -> None:
        a = Contato(valor="maria@x.com")
        b = Contato(valor="maria@x.com")
        assert hash(a) == hash(b)

    def test_usavel_em_set(self) -> None:
        a = Contato(valor="maria@x.com")
        b = Contato(valor="  maria@x.com  ")
        assert len({a, b}) == 1

    def test_repr_nao_vaza_valor_completo(self) -> None:
        # Contato e PII (pode conter e-mail/telefone/nome). O __repr__ NAO
        # pode vazar o valor completo (mesma politica do repr mascarado do CPF).
        contato = Contato(valor="maria.silva@exemplo.com")
        r = repr(contato)
        assert "maria.silva@exemplo.com" not in r
