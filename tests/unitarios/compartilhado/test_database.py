from __future__ import annotations

from src.compartilhado.infraestrutura.database import (
    criar_engine,
    criar_session_factory,
    metadata,
)


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
