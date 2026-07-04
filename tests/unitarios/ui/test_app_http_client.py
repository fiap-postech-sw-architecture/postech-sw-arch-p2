"""Testes do httpx.Client compartilhado de ``ui.app`` (fix 11 do #174).

``obter_api()`` roda a cada handler; antes, cada chamada abria um
``httpx.Client`` novo (pool de conexoes proprio) que nunca era fechado.
Agora o client e um singleton de modulo, thread-safe, fechado no shutdown.

Nota: ``ui.app`` e importado DENTRO da fixture (lazy), nunca no nivel do
modulo — import em tempo de coleta cachearia ``ui.app``/``ui.paginas.*`` em
``sys.modules`` e o app do Screen (``componentes/test_login.py``) nao
re-registraria as rotas ``@ui.page``, quebrando o teste de browser.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType

import pytest


@pytest.fixture
def ui_app() -> Iterator[ModuleType]:
    """Importa ``ui.app`` (lazy) com o singleton zerado antes/depois."""
    from ui import app as modulo

    modulo._fechar_http_client()
    yield modulo
    modulo._fechar_http_client()


def test_obter_api_reusa_o_mesmo_http_client(ui_app: ModuleType) -> None:
    api1 = ui_app.obter_api()
    api2 = ui_app.obter_api()
    assert api1 is not api2  # instancia leve por chamada (store correto)
    assert api1._client is api2._client  # pool de conexoes compartilhado


def test_fechar_http_client_fecha_e_reseta_o_singleton(ui_app: ModuleType) -> None:
    client = ui_app._obter_http_client()
    ui_app._fechar_http_client()
    assert client.is_closed
    # Proxima chamada cria um client novo e utilizavel.
    novo = ui_app._obter_http_client()
    assert novo is not client
    assert not novo.is_closed


def test_fechar_sem_client_aberto_e_no_op(ui_app: ModuleType) -> None:
    ui_app._fechar_http_client()
    ui_app._fechar_http_client()  # idempotente, nao explode
