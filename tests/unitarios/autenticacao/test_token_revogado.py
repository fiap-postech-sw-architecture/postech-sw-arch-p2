from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.autenticacao.dominio.token_revogado import TokenRevogado


class TestTokenRevogado:
    def test_criar_com_jti(self) -> None:
        tr = TokenRevogado.criar(jti="abc-123")
        assert tr.jti == "abc-123"
        assert tr.revogado_em is not None
        assert tr.id is not None

    def test_jti_vazio_invalido(self) -> None:
        with pytest.raises(ValueError, match="JTI nao pode ser vazio"):
            TokenRevogado(_jti="")

    def test_revogado_em_auto_preenchido(self) -> None:
        antes = datetime.now(UTC)
        tr = TokenRevogado.criar(jti="xyz")
        assert tr.revogado_em >= antes

    def test_identidade_por_id(self) -> None:
        a = TokenRevogado.criar(jti="jti-1")
        b = TokenRevogado.criar(jti="jti-2")
        assert a != b

    def test_criacao_sem_revogado_em_preenche_automaticamente(self) -> None:
        antes = datetime.now(UTC)
        tr = TokenRevogado(_jti="manual-123")
        assert tr.revogado_em is not None
        assert tr.revogado_em >= antes
        assert tr.jti == "manual-123"
