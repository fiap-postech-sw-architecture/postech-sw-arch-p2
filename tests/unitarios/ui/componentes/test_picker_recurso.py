from __future__ import annotations

from ui.componentes.picker_recurso import CacheRecursos


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
