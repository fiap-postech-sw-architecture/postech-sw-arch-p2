"""Orquestra a sequencia de seed do harness.

Ordem: reset (opcional) -> usuarios -> login admin -> catalogo -> estoque.

Idempotente: pode rodar antes de cada sessao. Retorna dicionarios com os recursos
semeados, usados pelas journeys no orchestrator.
"""

from __future__ import annotations

from full_test.client.system_client import SystemClient
from full_test.seeders import seed_catalogo, seed_estoque, seed_usuarios
from full_test.seeders.config import carregar_config
from full_test.seeders.seed_usuarios import credenciais_padrao


def seed_completo(*, resetar: bool = False) -> dict[str, object]:
    config = carregar_config()

    if resetar:
        from full_test.seeders.reset import resetar as _reset

        _reset(config.database_url)

    creds = credenciais_padrao(
        n_mecanicos=max(config.n_operadores, 1),
        n_atendentes=max(config.n_operadores, 1),
        admin_email=config.admin_email,
    )
    inseridos = seed_usuarios.semear(
        config.database_url, creds, admin_password=config.admin_password
    )

    # Admin login aqui vira o UNICO login admin da sessao — seu token e
    # propagado via ``admin_access_token`` para todas as journeys que
    # precisam de admin (evita 429 por rate limit de 5/min em /login).
    admin_tokens = None
    with SystemClient(config.base_url, timeout=config.http_timeout) as admin:
        admin_tokens = admin.login(
            email=config.admin_email, senha=config.admin_password
        )
        servicos = seed_catalogo.semear(admin)
        itens = seed_estoque.semear(admin)

    return {
        "config": config,
        "credenciais": creds,
        "usuarios_inseridos": inseridos,
        "servicos": servicos,
        "itens_estoque": itens,
        "admin_access_token": admin_tokens.access_token,
        "admin_refresh_token": admin_tokens.refresh_token,
    }


if __name__ == "__main__":
    import json

    resultado = seed_completo(resetar=False)
    print(
        json.dumps(
            {
                "usuarios_inseridos": resultado["usuarios_inseridos"],
                "servicos": len(resultado["servicos"]),  # type: ignore[arg-type]
                "itens_estoque": len(resultado["itens_estoque"]),  # type: ignore[arg-type]
            }
        )
    )
