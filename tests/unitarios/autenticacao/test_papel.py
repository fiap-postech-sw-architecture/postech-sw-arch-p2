from __future__ import annotations

from src.autenticacao.dominio.papel import Papel


class TestPapel:
    def test_admin_existe(self) -> None:
        assert Papel.ADMIN == "admin"

    def test_mecanico_existe(self) -> None:
        assert Papel.MECANICO == "mecanico"

    def test_atendente_existe(self) -> None:
        assert Papel.ATENDENTE == "atendente"

    def test_total_de_papeis(self) -> None:
        assert len(Papel) == 3

    def test_valores_sao_lowercase(self) -> None:
        for papel in Papel:
            assert papel.value == papel.value.lower()
