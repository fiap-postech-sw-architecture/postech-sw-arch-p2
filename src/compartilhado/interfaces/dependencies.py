from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

_session_factory = None


def configurar_session_factory(factory: object) -> None:
    """Registra a factory global de sessao SQLAlchemy usada por `obter_session`.

    Chamada uma vez durante o startup do app com a sessionmaker apropriada.
    """
    global _session_factory
    _session_factory = factory


def obter_session() -> Generator[Session, None, None]:
    """Dependency FastAPI que abre uma sessao por request e a fecha no teardown.

    Levanta RuntimeError se a factory nao foi configurada.
    """
    if _session_factory is None:
        msg = "Session factory nao configurada"
        raise RuntimeError(msg)
    session = _session_factory()  # type: ignore[operator]
    try:
        yield session
    finally:
        session.close()
