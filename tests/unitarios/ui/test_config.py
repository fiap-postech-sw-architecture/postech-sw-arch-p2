from __future__ import annotations

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
