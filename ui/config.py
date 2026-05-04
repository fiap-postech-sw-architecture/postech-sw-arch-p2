"""Configuracao da UI de simulacao (dev-only).

Le env vars com defaults razoaveis para dev local. Credenciais dos usuarios
seed sao FIXAS por design: esta UI e ferramenta de dev e espelha o que
``scripts/seed_usuarios.py`` popula no banco.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

Papel = Literal["admin", "atendente", "mecanico"]


@dataclass(frozen=True)
class UsuarioSeed:
    """Credenciais fixas de um usuario dev usado pelo role switcher."""

    email: str
    senha: str
    papel: Papel


# Credenciais fixas dev-only. NUNCA promover pra producao. Elas sao
# usadas ao mesmo tempo pelo ``scripts/seed_usuarios.py`` (pra popular
# o banco) e pelo switcher de papel na UI (pra relogar). A senha tem
# >=12 chars pra passar na validacao do backend.
_USUARIOS_SEED: dict[Papel, UsuarioSeed] = {
    "admin": UsuarioSeed(
        email="admin@pytstop.dev",
        senha="admin-dev-pass-2026",
        papel="admin",
    ),
    "atendente": UsuarioSeed(
        email="atendente@pytstop.dev",
        senha="atendente-dev-pass-2026",
        papel="atendente",
    ),
    "mecanico": UsuarioSeed(
        email="mecanico@pytstop.dev",
        senha="mecanico-dev-pass-2026",
        papel="mecanico",
    ),
}


# Fallback dev-only do storage_secret. Usado SOMENTE quando UI_STORAGE_SECRET
# nao estiver definido. A UI e dev-only por design, mas exponha via env pra
# permitir override em CI, docker-compose, ou qualquer cenario fora de dev local.
_STORAGE_SECRET_DEV_FALLBACK = "pytstop-ui-dev-only-secret-change-for-public-deploy"  # noqa: S105


@dataclass(frozen=True)
class Config:
    backend_url: str
    ui_port: int
    storage_secret: str
    # SHA do commit que gerou a imagem da UI. Vem do build arg `GIT_SHA`
    # injetado em `ui/Dockerfile` (mesmo padrao do app/db). Default vazio
    # cobre rodadas locais sem build (uvicorn direto pra dev hot-reload),
    # onde nao tem imagem nem env var. Usado pra exibir versao no rodape
    # da pagina de login.
    git_sha: str = ""
    usuarios_seed: dict[Papel, UsuarioSeed] = field(
        default_factory=lambda: dict(_USUARIOS_SEED)
    )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Config:
        source = env if env is not None else dict(os.environ)
        return cls(
            backend_url=source.get("BACKEND_URL", "http://localhost:8001"),
            ui_port=int(source.get("UI_PORT", "8080")),
            storage_secret=source.get(
                "UI_STORAGE_SECRET", _STORAGE_SECRET_DEV_FALLBACK
            ),
            git_sha=source.get("PYTSTOP_GIT_SHA", ""),
            usuarios_seed=dict(_USUARIOS_SEED),
        )


CONFIG = Config.from_env()
