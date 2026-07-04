"""Fixtures locais dos testes de relay (LISTEN/NOTIFY + raw connection).

``engine_dedicado``: engine SQLAlchemy FUNCTION-scoped, criado e ``dispose``ado
DENTRO do teste. Testes que mutam ``autocommit`` numa conexao psycopg2 raw
(``test_listener_smoke``, NOTIFY em ``test_relay_fluxo``) NAO podem usar o
``engine`` session-scoped do conftest pai: uma conexao reciclada deixada em
autocommit volta ao pool compartilhado e quebra fixtures posteriores baseadas
em SAVEPOINT (``SAVEPOINT can only be used in transaction blocks`` /
``NoActiveSqlTransaction``). Hoje so passava por ordem alfabetica dos arquivos.
Um engine dedicado e descartado isola o estado do pool — nada vaza para o
``engine`` compartilhado, em qualquer ordem de execucao.

Reusa o MESMO banco/URL do ``engine`` da sessao (as tabelas ja foram criadas
por ``metadata.create_all`` la); apenas o pool de conexoes e separado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integracao.outbox_helpers import limpar_outbox

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import Engine


@pytest.fixture(autouse=True)
def _outbox_limpa(engine: Engine) -> Generator[None]:
    """Outbox/processed_events zeradas antes e depois de CADA teste do pacote.

    Os testes de relay inserem linhas via Core com commit REAL (fora do
    savepoint da fixture ``session``); sem a limpeza autouse cada arquivo
    reimplementava a sua — e quem esquecia (listener_smoke, dlq) vazava
    linhas para os vizinhos.
    """
    limpar_outbox(engine)
    yield
    limpar_outbox(engine)


@pytest.fixture
def engine_dedicado(engine: Engine) -> Generator[Engine]:
    """Engine function-scoped (pool isolado), descartado ao fim do teste."""
    from src.compartilhado.infraestrutura.database import criar_engine

    dedicado = criar_engine(engine.url.render_as_string(hide_password=False))
    try:
        yield dedicado
    finally:
        dedicado.dispose()
