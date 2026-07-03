"""Testes unitarios da pagina de login (probe de seed cacheado + validacao).

Nao usa Screen/browser: exercita ``_status_admin_seed`` (cache de processo do
probe, bug 2 do #170) e ``_entrar`` (validacao de campos vazios) direto.

Nota: ``ui.paginas.login`` e importado DENTRO dos testes (lazy), nunca no
nivel do modulo — import em tempo de coleta deixaria o modulo cacheado em
``sys.modules`` e o app do Screen (``componentes/test_login.py``) nao
re-registraria a rota ``@ui.page("/login")``, quebrando o teste de browser.
"""

from __future__ import annotations

from http import HTTPStatus
from types import ModuleType

import pytest


class _ApiProbeFake:
    def __init__(self, status: int | None) -> None:
        self.status = status
        self.chamadas = 0

    def tentar_login_sem_salvar(self, *, email: str, senha: str) -> int | None:
        self.chamadas += 1
        return self.status


@pytest.fixture
def pagina_login(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Importa a pagina (lazy) e zera o cache de modulo do probe."""
    from ui.paginas import login as modulo

    monkeypatch.setattr(modulo, "_probe_seed_feito", False)
    monkeypatch.setattr(modulo, "_probe_seed_status", None)
    return modulo


def test_probe_seed_roda_uma_unica_vez_por_processo(
    monkeypatch: pytest.MonkeyPatch, pagina_login: ModuleType
) -> None:
    """Bug 2 do #170: cada render de /login disparava um POST /login com as
    credenciais do admin seed. O resultado agora e cacheado em variavel de
    modulo — N renders => 1 probe."""
    api = _ApiProbeFake(status=HTTPStatus.OK)
    monkeypatch.setattr("ui.app.obter_api", lambda: api)

    assert pagina_login._status_admin_seed() == HTTPStatus.OK
    assert pagina_login._status_admin_seed() == HTTPStatus.OK
    assert pagina_login._status_admin_seed() == HTTPStatus.OK
    assert api.chamadas == 1


def test_probe_seed_cacheia_tambem_o_401(
    monkeypatch: pytest.MonkeyPatch, pagina_login: ModuleType
) -> None:
    api = _ApiProbeFake(status=HTTPStatus.UNAUTHORIZED)
    monkeypatch.setattr("ui.app.obter_api", lambda: api)

    assert pagina_login._status_admin_seed() == HTTPStatus.UNAUTHORIZED
    assert pagina_login._status_admin_seed() == HTTPStatus.UNAUTHORIZED
    assert api.chamadas == 1


def test_probe_seed_offline_nao_e_cacheado(
    monkeypatch: pytest.MonkeyPatch, pagina_login: ModuleType
) -> None:
    """Backend inacessivel (``None``) re-sonda no proximo render: cachear a
    falha esconderia o aviso de seed ausente mesmo depois do backend subir."""
    api = _ApiProbeFake(status=None)
    monkeypatch.setattr("ui.app.obter_api", lambda: api)

    assert pagina_login._status_admin_seed() is None
    assert pagina_login._status_admin_seed() is None
    assert api.chamadas == 2

    # Backend voltou: o proximo probe pega o status real e ai sim cacheia.
    api.status = HTTPStatus.OK
    assert pagina_login._status_admin_seed() == HTTPStatus.OK
    assert pagina_login._status_admin_seed() == HTTPStatus.OK
    assert api.chamadas == 3


def test_entrar_com_campos_vazios_notifica_sem_chamar_backend(
    monkeypatch: pytest.MonkeyPatch, pagina_login: ModuleType
) -> None:
    chamadas: list[str] = []
    notifies: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "ui.app.obter_api",
        lambda: chamadas.append("obter_api"),
    )
    monkeypatch.setattr(
        "ui.paginas.login.ui.notify",
        lambda msg, **kw: notifies.append((msg, kw)),
    )

    pagina_login._entrar("", "")
    pagina_login._entrar("   ", "senha-qualquer")
    pagina_login._entrar("a@b", "")

    assert chamadas == []
    assert len(notifies) == 3
    assert all("Informe e-mail e senha" in msg for msg, _ in notifies)
    assert all(kw == {"type": "warning"} for _, kw in notifies)
