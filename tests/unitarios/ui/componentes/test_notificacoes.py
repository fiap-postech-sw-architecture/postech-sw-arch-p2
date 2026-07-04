"""Testes do helper compartilhado de notificacao de erros de API."""

from __future__ import annotations

import pytest

from ui.cliente_api import (
    ApiError,
    BackendInacessivelError,
    ConflitoEstadoError,
    ValidacaoError,
)
from ui.componentes.notificacoes import notificar_erro_api


@pytest.fixture
def notifies(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, object]]]:
    capturadas: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "ui.componentes.notificacoes.ui.notify",
        lambda msg, **kw: capturadas.append((msg, kw)),
    )
    return capturadas


def test_validacao_junta_mensagens_do_detail(
    notifies: list[tuple[str, dict[str, object]]],
) -> None:
    exc = ValidacaoError(
        [
            {"loc": ["body", "placa"], "msg": "formato invalido"},
            {"loc": ["body", "ano"], "msg": "acima do maximo"},
        ]
    )
    notificar_erro_api(exc)
    assert notifies == [
        (
            "Invalido: formato invalido; acima do maximo",
            {"type": "negative"},
        )
    ]


def test_conflito_usa_warning_com_detail(
    notifies: list[tuple[str, dict[str, object]]],
) -> None:
    notificar_erro_api(ConflitoEstadoError("OS em AGUARDANDO_APROVACAO"))
    assert notifies == [
        ("Nao permitido: OS em AGUARDANDO_APROVACAO", {"type": "warning"})
    ]


@pytest.mark.parametrize(
    "exc",
    [ApiError("Status inesperado 418"), BackendInacessivelError("http://x")],
    ids=lambda e: type(e).__name__,
)
def test_demais_erros_usam_mensagem_generica_negativa(
    notifies: list[tuple[str, dict[str, object]]],
    exc: ApiError,
) -> None:
    notificar_erro_api(exc)
    assert len(notifies) == 1
    msg, kw = notifies[0]
    assert msg.startswith("Erro: ")
    assert kw == {"type": "negative"}
