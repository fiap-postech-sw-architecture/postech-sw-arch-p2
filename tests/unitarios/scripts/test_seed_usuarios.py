from __future__ import annotations

from unittest.mock import MagicMock, patch

from scripts import seed_usuarios
from src.autenticacao.dominio.papel import Papel


def test_cria_os_3_papeis_quando_banco_vazio() -> None:
    sessions: list[MagicMock] = []

    def session_factory() -> MagicMock:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        sessions.append(session)
        return session

    hasher_chamadas: list[str] = []

    def hasher(senha: str) -> str:
        hasher_chamadas.append(senha)
        return f"hashed-{senha}"

    with patch(
        "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository"
    ) as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.email_existe.return_value = False
        mock_repo_cls.return_value = mock_repo

        relatorio = seed_usuarios.criar_usuarios_seed(
            session_factory=session_factory,
            hasher=hasher,
        )

    assert relatorio.criados == 3
    assert relatorio.existentes == 0
    assert mock_repo.salvar.call_count == 3

    # Verifica que cada Usuario salvo corresponde ao par (papel, email) esperado
    # e que o hasher recebeu exatamente as 3 senhas em texto plano. Detecta
    # bugs tipo "loop envia usuario X com papel Y" que contagens nao pegam.
    usuarios_salvos = [call.args[0] for call in mock_repo.salvar.call_args_list]
    assert {(u.papel, u.email) for u in usuarios_salvos} == {
        (Papel.ADMIN, "admin@pytstop.dev"),
        (Papel.ATENDENTE, "atendente@pytstop.dev"),
        (Papel.MECANICO, "mecanico@pytstop.dev"),
    }
    assert set(hasher_chamadas) == {
        "admin-dev-pass-2026",
        "atendente-dev-pass-2026",
        "mecanico-dev-pass-2026",
    }


def test_skipa_papeis_que_ja_existem() -> None:
    def session_factory() -> MagicMock:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        return session

    with patch(
        "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository"
    ) as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.email_existe.return_value = True
        mock_repo_cls.return_value = mock_repo

        relatorio = seed_usuarios.criar_usuarios_seed(
            session_factory=session_factory,
            hasher=lambda s: f"hashed-{s}",
        )

    assert relatorio.criados == 0
    assert relatorio.existentes == 3
    assert mock_repo.salvar.call_count == 0


def test_credenciais_sincronizadas_com_ui_config() -> None:
    """Garante que ui/config.py::_USUARIOS_SEED e este script concordam."""
    from ui.config import _USUARIOS_SEED

    esperado = {
        (seed.papel, seed.email, seed.senha) for seed in _USUARIOS_SEED.values()
    }
    atual = {
        (papel_name.lower(), email, senha)
        for papel_name, email, senha in seed_usuarios._USUARIOS_FIXOS
    }
    assert esperado == atual, (
        "ui/config.py e scripts/seed_usuarios.py divergiram. Atualize ambos."
    )
