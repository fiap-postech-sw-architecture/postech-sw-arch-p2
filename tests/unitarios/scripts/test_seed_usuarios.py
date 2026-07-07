from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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


def test_papeis_restringe_subconjunto_e_senhas_substituem_fixas() -> None:
    """Cloud (ADR-025 adendo): so atendente/mecanico, com senha forte."""

    def session_factory() -> MagicMock:
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        return session

    hasher_chamadas: list[str] = []

    with patch(
        "src.autenticacao.infraestrutura.repository.UsuarioSQLAlchemyRepository"
    ) as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.email_existe.return_value = False
        mock_repo_cls.return_value = mock_repo

        relatorio = seed_usuarios.criar_usuarios_seed(
            session_factory=session_factory,
            hasher=lambda s: (hasher_chamadas.append(s), f"hashed-{s}")[1],
            papeis=frozenset({"ATENDENTE", "MECANICO"}),
            senhas={"ATENDENTE": "forte-at", "MECANICO": "forte-mec"},
        )

    assert relatorio.criados == 2
    usuarios_salvos = [call.args[0] for call in mock_repo.salvar.call_args_list]
    assert {u.email for u in usuarios_salvos} == {
        "atendente@pytstop.dev",
        "mecanico@pytstop.dev",
    }
    # Senhas fortes do env, nunca as dev publicas — e o admin nao e' tocado.
    assert set(hasher_chamadas) == {"forte-at", "forte-mec"}


class TestGuardaDeAmbiente:
    """main() fora de development/test exige senha via env por papel."""

    @pytest.mark.parametrize("environment", ["production", "staging", "prod"])
    def test_sai_com_codigo_1_fora_de_dev_test(
        self, environment: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        with pytest.raises(SystemExit) as exc:
            seed_usuarios.main()
        assert exc.value.code == 1

    def test_production_com_senha_parcial_ainda_aborta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ATENDENTE tem senha via env, MECANICO nao -> guarda barra (a senha
        # dev publica do MECANICO iria para o ambiente exposto).
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        monkeypatch.setenv("SEED_PAPEIS", "ATENDENTE,MECANICO")
        monkeypatch.setenv("SEED_SENHA_ATENDENTE", "forte-at")
        with pytest.raises(SystemExit) as exc:
            seed_usuarios.main()
        assert exc.value.code == 1

    def test_production_passa_quando_todo_papel_tem_senha_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        monkeypatch.setenv("SEED_PAPEIS", "atendente, mecanico")
        monkeypatch.setenv("SEED_SENHA_ATENDENTE", "forte-at")
        monkeypatch.setenv("SEED_SENHA_MECANICO", "forte-mec")
        with (
            patch.object(seed_usuarios, "criar_usuarios_seed") as mock_seed,
            patch(
                "src.compartilhado.infraestrutura.bootstrap.iniciar_todos_mapeamentos"
            ),
            patch("src.compartilhado.infraestrutura.database.criar_engine"),
            patch("src.compartilhado.infraestrutura.database.criar_session_factory"),
            patch("src.autenticacao.infraestrutura.password_hasher.hash_senha"),
        ):
            mock_seed.return_value = seed_usuarios.RelatorioSeed(
                criados=2, existentes=0
            )
            seed_usuarios.main()
        kwargs = mock_seed.call_args.kwargs
        assert kwargs["papeis"] == frozenset({"ATENDENTE", "MECANICO"})
        assert kwargs["senhas"] == {
            "ATENDENTE": "forte-at",
            "MECANICO": "forte-mec",
        }

    @pytest.mark.parametrize("environment", ["development", "test"])
    def test_prossegue_em_dev_e_test(
        self, environment: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Em dev/test a guarda deixa passar; mockamos o miolo (mapeamentos +
        # engine + criacao) para nao tocar banco real e so provar que a guarda
        # nao aborta antes de chegar la.
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        with (
            patch.object(seed_usuarios, "criar_usuarios_seed") as mock_seed,
            patch(
                "src.compartilhado.infraestrutura.bootstrap.iniciar_todos_mapeamentos"
            ),
            patch("src.compartilhado.infraestrutura.database.criar_engine"),
            patch("src.compartilhado.infraestrutura.database.criar_session_factory"),
            patch("src.autenticacao.infraestrutura.password_hasher.hash_senha"),
        ):
            mock_seed.return_value = seed_usuarios.RelatorioSeed(
                criados=3, existentes=0
            )
            seed_usuarios.main()
        mock_seed.assert_called_once()


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
