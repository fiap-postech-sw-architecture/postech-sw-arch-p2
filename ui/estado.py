"""State management da UI.

Abstrai o storage subjacente (em producao, ``nicegui.app.storage.user`` e
``storage.tab``; em testes, um dict in-memory). Fornece acesso tipado
para evitar que paginas toquem storage cru.

Sessao vai pro user_storage (cookie criptografado, persiste cross-reload).
Historico HTTP vai pro tab_storage (per-aba) — sem isso, n usuarios
conectados ao mesmo processo NiceGUI veriam request/response uns dos
outros, vazando dados (request bodies podem trazer PII).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, cast

Papel = Literal["admin", "atendente", "mecanico"]
_PAPEIS_VALIDOS: frozenset[str] = frozenset({"admin", "atendente", "mecanico"})


@dataclass(frozen=True)
class Sessao:
    access_token: str
    refresh_token: str
    email: str
    papel: Papel


@dataclass(frozen=True)
class RegistroHttp:
    timestamp: datetime
    metodo: str
    caminho: str
    status: int
    duracao_ms: int
    request_body: str | None
    response_body: str
    papel_no_momento: str

    def to_dict(self) -> dict[str, Any]:
        """Serializa pra dict JSON-friendly (datetime -> ISO)."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metodo": self.metodo,
            "caminho": self.caminho,
            "status": self.status,
            "duracao_ms": self.duracao_ms,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "papel_no_momento": self.papel_no_momento,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RegistroHttp:
        return cls(
            timestamp=datetime.fromisoformat(raw["timestamp"]),
            metodo=raw["metodo"],
            caminho=raw["caminho"],
            status=int(raw["status"]),
            duracao_ms=int(raw["duracao_ms"]),
            request_body=raw.get("request_body"),
            response_body=raw["response_body"],
            papel_no_momento=raw["papel_no_momento"],
        )


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
_KEY_HISTORICO = "historico_http"


class StateStore:
    """Acesso tipado ao storage. Uma instancia por processo UI.

    O historico HTTP vive em ``tab_storage`` (per-aba) — em prod a NiceGUI
    cifra o cookie e isola por tab, evitando vazar request/response entre
    sessoes que dividem o mesmo processo. Em testes, o ``_DictStorage``
    in-memory simula o mesmo contrato sem dependencia de NiceGUI.
    """

    def __init__(
        self,
        user_storage: _StorageProtocol | None = None,
        tab_storage: _StorageProtocol | None = None,
        max_entradas_historico: int = 50,
    ) -> None:
        self._user = user_storage or _DictStorage()
        self._tab = tab_storage or _DictStorage()
        self._max = max_entradas_historico

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

    # ----- historico http (per-tab) -----

    def _historico_raw(self) -> list[dict[str, Any]]:
        bruto = self._tab.get(_KEY_HISTORICO, [])
        if isinstance(bruto, list):
            return bruto
        return []

    def registrar_chamada_http(self, registro: RegistroHttp) -> None:
        # Insert no inicio + truncate em ``max_entradas_historico``: mantem
        # os mais recentes (mesmo comportamento do antigo ``deque.appendleft``
        # com ``maxlen``).
        atual = self._historico_raw()
        atual.insert(0, registro.to_dict())
        if len(atual) > self._max:
            atual = atual[: self._max]
        self._tab[_KEY_HISTORICO] = atual

    def historico_http(self) -> list[RegistroHttp]:
        return [RegistroHttp.from_dict(d) for d in self._historico_raw()]

    def limpar_historico_http(self) -> None:
        self._tab[_KEY_HISTORICO] = []


# Singleton lazy — inicializado com NiceGUI storage quando a app sobe.
_store: StateStore | None = None


def obter_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store


def configurar_store(store: StateStore) -> None:
    """Permite injetar um store customizado (usado em testes e no bootstrap)."""
    global _store
    _store = store
