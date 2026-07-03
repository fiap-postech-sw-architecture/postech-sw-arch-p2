from __future__ import annotations

import pytest

from ui.config import Config, UsuarioSeed


def test_config_usa_defaults_quando_env_vazio() -> None:
    cfg = Config.from_env(env={})
    assert cfg.backend_url == "http://localhost:8001"
    assert cfg.ui_port == 8080


def test_config_respeita_env_vars() -> None:
    cfg = Config.from_env(
        env={
            "BACKEND_URL": "http://app:8000",
            "UI_PORT": "9000",
        }
    )
    assert cfg.backend_url == "http://app:8000"
    assert cfg.ui_port == 9000


def test_config_expoe_usuarios_seed_dos_3_papeis() -> None:
    cfg = Config.from_env(env={})
    assert set(cfg.usuarios_seed.keys()) == {"admin", "atendente", "mecanico"}
    for papel, usuario in cfg.usuarios_seed.items():
        assert isinstance(usuario, UsuarioSeed)
        assert usuario.papel == papel
        assert len(usuario.senha) >= 12
        assert "@" in usuario.email


def test_config_storage_secret_tem_fallback_dev_quando_env_vazio() -> None:
    cfg = Config.from_env(env={})
    # Fallback dev-only — NAO pode estar vazio nem ser None.
    assert cfg.storage_secret
    assert "dev" in cfg.storage_secret.lower()


def test_config_storage_secret_respeita_env_override() -> None:
    cfg = Config.from_env(env={"UI_STORAGE_SECRET": "my-production-secret-abc"})
    assert cfg.storage_secret == "my-production-secret-abc"


def test_config_git_sha_default_vazio_quando_env_ausente() -> None:
    """Sem PYTSTOP_GIT_SHA (rodada local sem build), git_sha fica vazio.

    O rodape da pagina de login usa essa string vazia como sinal pra nao
    renderizar a versao -- evita mostrar 'v' sozinho ou 'vunknown'.
    """
    cfg = Config.from_env(env={})
    assert cfg.git_sha == ""


def test_config_git_sha_le_pytstop_git_sha_da_env() -> None:
    """Build do Dockerfile injeta GIT_SHA -> ENV PYTSTOP_GIT_SHA."""
    sha = "3d94aff26b7ba6830874e6cedbf15b7e40bfc5a4"
    cfg = Config.from_env(env={"PYTSTOP_GIT_SHA": sha})
    assert cfg.git_sha == sha


def test_config_ui_port_nao_numerica_tem_mensagem_clara() -> None:
    """NIT do #174: ``UI_PORT=oitenta`` estourava ``invalid literal for
    int()`` sem apontar a env var culpada."""
    with pytest.raises(ValueError, match=r"UI_PORT invalida.*oitenta"):
        Config.from_env(env={"UI_PORT": "oitenta"})


@pytest.mark.parametrize("porta", ["0", "-1", "65536"])
def test_config_ui_port_fora_do_intervalo_falha(porta: str) -> None:
    with pytest.raises(ValueError, match="UI_PORT"):
        Config.from_env(env={"UI_PORT": porta})


def test_config_ui_port_valida_passa() -> None:
    assert Config.from_env(env={"UI_PORT": "9090"}).ui_port == 9090
