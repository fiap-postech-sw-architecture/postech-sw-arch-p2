"""State management da UI.

Abstrai o storage subjacente (em producao, ``nicegui.app.storage.user``;
em testes, um dict in-memory). Fornece acesso tipado para evitar que
paginas toquem storage cru.

Sessao vai pro user_storage (cookie criptografado, persiste cross-reload).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, cast

Papel = Literal["admin", "atendente", "mecanico"]
_PAPEIS_VALIDOS: frozenset[str] = frozenset({"admin", "atendente", "mecanico"})


@dataclass(frozen=True)
class Sessao:
    access_token: str
    refresh_token: str
    email: str
    papel: Papel


class _StorageProtocol(Protocol):
    def get(self, key: str, default: object = None) -> object: ...
    def __setitem__(self, key: str, value: object) -> None: ...
    def clear(self) -> None: ...


class _DictStorage:
    """Backing store in-memory, usado em testes e como fallback."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: object) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()


_KEY_SESSAO = "sessao"


class StateStore:
    """Acesso tipado ao storage. Uma instancia por processo UI."""

    def __init__(self, user_storage: _StorageProtocol | None = None) -> None:
        self._user = user_storage or _DictStorage()

    # ----- sessao -----

    def salvar_sessao(self, sessao: Sessao) -> None:
        self._user[_KEY_SESSAO] = {
            "access_token": sessao.access_token,
            "refresh_token": sessao.refresh_token,
            "email": sessao.email,
            "papel": sessao.papel,
        }

    def limpar_sessao(self) -> None:
        self._user[_KEY_SESSAO] = None

    def _sessao_dict(self) -> dict[str, str] | None:
        valor = self._user.get(_KEY_SESSAO)
        if isinstance(valor, dict):
            return valor
        return None

    def sessao_atual(self) -> Sessao | None:
        s = self._sessao_dict()
        if s is None:
            return None
        papel = s.get("papel")
        if papel not in _PAPEIS_VALIDOS:
            return None
        return Sessao(
            access_token=s["access_token"],
            refresh_token=s["refresh_token"],
            email=s["email"],
            papel=cast("Papel", papel),
        )

    def token_atual(self) -> str | None:
        sessao = self.sessao_atual()
        return sessao.access_token if sessao else None

    def refresh_token_atual(self) -> str | None:
        sessao = self.sessao_atual()
        return sessao.refresh_token if sessao else None

    def email_atual(self) -> str | None:
        sessao = self.sessao_atual()
        return sessao.email if sessao else None

    def papel_atual(self) -> Papel | None:
        sessao = self.sessao_atual()
        return sessao.papel if sessao else None

    def esta_autenticado(self) -> bool:
        return self.sessao_atual() is not None


# Singleton lazy — inicializado com NiceGUI storage quando a app sobe.
_store: StateStore | None = None


def obter_store() -> StateStore:
    global _store  # noqa: PLW0603  # lazy singleton
    if _store is None:
        _store = StateStore()
    return _store


def configurar_store(store: StateStore) -> None:
    """Permite injetar um store customizado (usado em testes e no bootstrap)."""
    global _store  # noqa: PLW0603  # singleton swap em testes/bootstrap
    _store = store
