"""Testes do decorator exige_autenticacao."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ui.auth_guard import exige_autenticacao


def test_exige_autenticacao_executa_func_quando_autenticado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MagicMock()
    store.esta_autenticado.return_value = True
    monkeypatch.setattr("ui.auth_guard.obter_store", lambda: store)

    chamadas: list[tuple[tuple[object, ...], dict[str, object]]] = []

    @exige_autenticacao
    def acao(x: int, y: int = 0) -> int:
        chamadas.append(((x, y), {}))
        return x + y

    resultado = acao(1, y=2)
    assert resultado == 3
    assert chamadas == [((1, 2), {})]


def test_exige_autenticacao_redireciona_e_retorna_none_quando_nao_autenticado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MagicMock()
    store.esta_autenticado.return_value = False
    monkeypatch.setattr("ui.auth_guard.obter_store", lambda: store)
    nav = MagicMock()
    monkeypatch.setattr("ui.auth_guard.ui.navigate", nav)

    chamadas: list[int] = []

    @exige_autenticacao
    def acao() -> str:
        chamadas.append(1)
        return "ok"

    resultado = acao()
    assert resultado is None
    assert chamadas == []
    nav.to.assert_called_once_with("/login")


def test_exige_autenticacao_preserva_docstring_e_nome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ui.auth_guard.obter_store", MagicMock)

    @exige_autenticacao
    def pagina_teste() -> None:
        """Docstring da pagina de teste."""

    # @wraps preserva __name__ e __doc__ — importante para NiceGUI
    # instrospectar a funcao decorada ao registrar a rota.
    assert pagina_teste.__name__ == "pagina_teste"
    assert pagina_teste.__doc__ == "Docstring da pagina de teste."
