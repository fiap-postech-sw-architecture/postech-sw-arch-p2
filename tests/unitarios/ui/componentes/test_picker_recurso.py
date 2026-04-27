from __future__ import annotations

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
from ui.componentes.picker_recurso import CacheRecursos, PickerRecurso


def _picker_sem_widget(rotulo: str, cache: CacheRecursos) -> PickerRecurso:
    """Constroi PickerRecurso sem chamar __init__ (que dispara NiceGUI).

    Permite testar a logica de _obter_opcoes em isolamento, sem subir
    runtime de UI.
    """
    picker = PickerRecurso.__new__(PickerRecurso)
    picker._campo_id = "id"
    picker._campo_label = "nome"
    picker._rotulo = rotulo
    picker._cache = cache
    return picker


def test_obter_opcoes_retorna_dict_no_caminho_feliz() -> None:
    cache = CacheRecursos(
        ttl_seg=30,
        fetcher=lambda: [
            {"id": "u-1", "nome": "Alfa"},
            {"id": "u-2", "nome": "Beta"},
        ],
    )
    picker = _picker_sem_widget(rotulo="Cliente", cache=cache)

    assert picker._obter_opcoes() == {"u-1": "Alfa", "u-2": "Beta"}


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

    picker = _picker_sem_widget(
        rotulo="Cliente",
        cache=CacheRecursos(ttl_seg=30, fetcher=fetcher_falho),
    )

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

    picker = _picker_sem_widget(
        rotulo="Cliente",
        cache=CacheRecursos(ttl_seg=30, fetcher=fetcher_buggy),
    )

    with pytest.raises(ValueError, match="bug interno"):
        picker._obter_opcoes()
    assert notifies == []


def test_cache_nao_e_envenenado_por_fetcher_falho() -> None:
    """Invariante facil de quebrar num refactor: se `CacheRecursos.obter`
    setar `_cache = []` antes do `fetcher()` levantar, o segundo fetch
    veria o cache vazio em vez de re-tentar.
    """
    chamadas = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            raise BackendInacessivelError("http://localhost:8000")
        return [{"id": "1", "nome": "Alfa"}]

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    with pytest.raises(BackendInacessivelError):
        cache.obter()
    assert cache.obter() == [{"id": "1", "nome": "Alfa"}]
    assert chamadas == 2


def test_refresh_chama_obter_opcoes_e_propaga_vazio_em_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_refresh` invalida o cache e re-busca; em offline, deve passar
    pelo branch ApiError (sem crash) e produzir dict vazio. O teste
    verifica que o caminho passa pelo notify (ja monkeypatchado), sem
    propagar excecao."""

    chamadas = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 1:
            return [{"id": "1", "nome": "Alfa"}]
        raise BackendInacessivelError("http://localhost:8000")

    notifies: list[str] = []
    monkeypatch.setattr(
        "ui.componentes.picker_recurso.ui.notify",
        lambda msg, **_: notifies.append(msg),
    )

    picker = _picker_sem_widget(
        rotulo="Servico",
        cache=CacheRecursos(ttl_seg=30, fetcher=fetch),
    )
    # primeira chamada popula cache
    assert picker._obter_opcoes() == {"1": "Alfa"}
    # invalida cache pra forcar re-fetch (que vai falhar)
    picker._cache.invalidar()
    assert picker._obter_opcoes() == {}
    assert len(notifies) == 1
    assert "Servico" in notifies[0]


def test_cache_retorna_itens_frescos_na_primeira_chamada() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [{"id": "1", "nome": "Alfa"}]

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    items = cache.obter()
    assert items == [{"id": "1", "nome": "Alfa"}]
    assert calls == 1


def test_cache_reutiliza_antes_de_expirar() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return []

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    cache.obter()
    cache.obter()
    cache.obter()
    assert calls == 1


def test_cache_invalidar_forca_refetch() -> None:
    calls = 0

    def fetch() -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return []

    cache = CacheRecursos(ttl_seg=30, fetcher=fetch)
    cache.obter()
    cache.invalidar()
    cache.obter()
    assert calls == 2
