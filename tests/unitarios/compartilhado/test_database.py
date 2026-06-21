from __future__ import annotations

import pytest

from src.compartilhado.infraestrutura.database import (
    criar_engine,
    criar_session_factory,
    metadata,
)

_URL_PG = "postgresql://u:p@localhost:5432/db"


class TestDatabase:
    def test_metadata_existe(self) -> None:
        assert metadata is not None

    def test_criar_engine_sqlite_em_memoria(self) -> None:
        engine = criar_engine("sqlite:///:memory:")
        assert engine is not None
        engine.dispose()

    def test_criar_session_factory(self) -> None:
        engine = criar_engine("sqlite:///:memory:")
        factory = criar_session_factory(engine)
        assert factory is not None
        session = factory()
        session.close()
        engine.dispose()


class TestDimensionamentoDoPool:
    """RNF-024: pool dimensionado para N replicas (Postgres) sem quebrar SQLite."""

    def test_postgres_aplica_defaults_do_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Sem env: cai nos defaults (5 + 10), o pior caso do HPA (75 <= 100).
        monkeypatch.delenv("DB_POOL_SIZE", raising=False)
        monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
        engine = criar_engine(_URL_PG)
        assert engine.pool.size() == 5
        assert engine.pool._max_overflow == 10
        engine.dispose()

    def test_postgres_respeita_overrides_de_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DB_POOL_SIZE", "7")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "3")
        engine = criar_engine(_URL_PG)
        assert engine.pool.size() == 7
        assert engine.pool._max_overflow == 3
        engine.dispose()

    def test_postgres_ativa_pre_ping(self) -> None:
        engine = criar_engine(_URL_PG)
        assert engine.pool._pre_ping is True
        engine.dispose()

    def test_sqlite_nao_recebe_args_de_queuepool(self) -> None:
        # SingletonThreadPool do SQLite nao tem _max_overflow; o engine so e
        # criavel porque criar_engine NAO passa pool_size para sqlite.
        engine = criar_engine("sqlite:///:memory:")
        assert not hasattr(engine.pool, "_max_overflow")
        engine.dispose()
