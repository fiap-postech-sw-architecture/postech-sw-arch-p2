from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.compartilhado.interfaces.dependencies import (
    configurar_session_factory,
    obter_session,
)


class TestDependencies:
    def test_obter_session_sem_factory_levanta_erro(self) -> None:
        configurar_session_factory(None)
        with pytest.raises(RuntimeError, match="Session factory"):
            next(obter_session())

    def test_obter_session_com_factory(self) -> None:
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        configurar_session_factory(mock_factory)

        gen = obter_session()
        session = next(gen)
        assert session is mock_session

        try:
            next(gen)
        except StopIteration:
            pass

        mock_factory.assert_called_once_with()
        mock_session.close.assert_called_once_with()
        configurar_session_factory(None)
