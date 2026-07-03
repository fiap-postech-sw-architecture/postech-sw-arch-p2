from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ui.cliente_api import (
    AcessoNegadoError,
    ApiError,
    BackendInacessivelError,
    BackendIndisponivelError,
    ConflitoEstadoError,
    NaoAutenticadoError,
    RateLimitExcedidoError,
    ValidacaoError,
)
from ui.componentes.picker_recurso import PickerRecurso

if TYPE_CHECKING:
    from collections.abc import Callable


def _picker_sem_widget(
    rotulo: str, fetcher: Callable[[], list[dict[str, Any]]]
) -> PickerRecurso:
    """Constroi PickerRecurso sem chamar __init__ (que dispara NiceGUI).

    Permite testar a logica de _obter_opcoes em isolamento, sem subir
    runtime de UI.
    """
    picker = PickerRecurso.__new__(PickerRecurso)
    picker._campo_id = "id"
    picker._campo_label = "nome"
    picker._rotulo = rotulo
    picker._fetcher = fetcher
    return picker


def test_obter_opcoes_retorna_dict_no_caminho_feliz() -> None:
    picker = _picker_sem_widget(
        rotulo="Cliente",
        fetcher=lambda: [
            {"id": "u-1", "nome": "Alfa"},
            {"id": "u-2", "nome": "Beta"},
        ],
    )

    assert picker._obter_opcoes() == {"u-1": "Alfa", "u-2": "Beta"}


def test_obter_opcoes_chama_fetcher_direto_a_cada_chamada() -> None:
    """Sem cache (removido no #174): o fetcher e a fonte a cada render/refresh.

    O antigo ``CacheRecursos`` por instancia nunca tinha hit (pickers vivem
    dentro de dialogs recriados a cada abertura) — este teste pina o contrato
    novo: N chamadas => N fetches.
    """
    chamadas = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal chamadas
        chamadas += 1
        return [{"id": "1", "nome": "Alfa"}]

    picker = _picker_sem_widget(rotulo="Cliente", fetcher=fetch)
    picker._obter_opcoes()
    picker._obter_opcoes()
    assert chamadas == 2


# Travamos o contrato "qualquer subclasse de ApiError cai no branch": se
# alguem amanha estreitar o except (ex.: so BackendInacessivelError), os
# testes parametrizados quebram em massa, expondo a regressao.
@pytest.mark.parametrize(
    "exc",
    [
        BackendInacessivelError("http://localhost:8000"),
        BackendIndisponivelError("Erro 500"),
        NaoAutenticadoError("Sessao expirada"),
        AcessoNegadoError("admin"),
        ValidacaoError([{"loc": ["nome"], "msg": "obrigatorio"}]),
        RateLimitExcedidoError(retry_after=10),
        ConflitoEstadoError("OS em AGUARDANDO_APROVACAO"),
        ApiError("Status inesperado 418"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_obter_opcoes_captura_qualquer_subclasse_de_api_error(
    monkeypatch: pytest.MonkeyPatch, exc: ApiError
) -> None:
    def fetcher_falho() -> list[dict[str, str]]:
        raise exc

    notifies: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "ui.componentes.picker_recurso.ui.notify",
        lambda msg, **kw: notifies.append((msg, kw)),
    )

    picker = _picker_sem_widget(rotulo="Cliente", fetcher=fetcher_falho)

    assert picker._obter_opcoes() == {}
    assert len(notifies) == 1
    msg, kw = notifies[0]
    # Acoplamento intencional ao `__str__` da excecao: a UX que queremos
    # validar e que a mensagem ao usuario contem informacao acionavel
    # (rotulo do recurso + descricao do erro). Se uma subclasse mudar
    # __str__ pra algo nao-acionavel, este teste e o sinal certo.
    assert "Cliente" in msg
    assert kw == {"type": "negative"}


def test_obter_opcoes_propaga_excecoes_nao_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trava a fronteira do `except ApiError`: bugs (KeyError, ValueError,
    TypeError) precisam continuar subindo pro nivel acima — caso contrario
    um refactor pra `except Exception` mascararia defeitos sem quebrar testes.
    """

    def fetcher_buggy() -> list[dict[str, str]]:
        raise ValueError("bug interno nao-API")

    notifies: list[str] = []
    monkeypatch.setattr(
        "ui.componentes.picker_recurso.ui.notify",
        lambda msg, **_: notifies.append(msg),
    )

    picker = _picker_sem_widget(rotulo="Cliente", fetcher=fetcher_buggy)

    with pytest.raises(ValueError, match="bug interno"):
        picker._obter_opcoes()
    assert notifies == []


def test_fetcher_falho_nao_impede_retentativa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline na primeira chamada nao pode 'grudar': a proxima chamada
    re-busca e retorna os dados (equivalente ao antigo teste de cache
    nao-envenenado, agora sem cache)."""
    chamadas = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            raise BackendInacessivelError("http://localhost:8000")
        return [{"id": "1", "nome": "Alfa"}]

    notifies: list[str] = []
    monkeypatch.setattr(
        "ui.componentes.picker_recurso.ui.notify",
        lambda msg, **_: notifies.append(msg),
    )

    picker = _picker_sem_widget(rotulo="Servico", fetcher=fetch)
    assert picker._obter_opcoes() == {}
    assert picker._obter_opcoes() == {"1": "Alfa"}
    assert chamadas == 2
    assert len(notifies) == 1
    assert "Servico" in notifies[0]
