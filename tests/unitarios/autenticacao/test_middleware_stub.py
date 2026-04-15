from __future__ import annotations

import pytest

from src.autenticacao.interfaces.middleware import (
    exigir_papel,
    obter_usuario_atual,
)


class TestMiddlewareStub:
    def test_obter_usuario_atual_retorna_admin_stub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        user = obter_usuario_atual()
        assert user["papel"] == "admin"
        assert user["sub"] == "stub"

    def test_exigir_papel_retorna_dependency_que_chama_stub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        dep = exigir_papel("admin", "atendente")
        user = dep()
        assert user["papel"] == "admin"

    def test_stub_falha_em_producao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(RuntimeError, match="stub invocado em producao"):
            obter_usuario_atual()

    def test_exigir_papel_falha_em_producao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        dep = exigir_papel("admin")
        with pytest.raises(RuntimeError, match="stub invocado em producao"):
            dep()
