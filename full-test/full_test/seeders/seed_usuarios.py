"""Seeder de usuarios para o harness (DB bypass; API nao suporta criacao de
MECANICO/ATENDENTE - ver orchestrator/plans/orchestrator-full-e2e-test.md).

Idempotente: re-executar e' no-op para emails ja existentes.

NOTE (seguranca): a senha padrao ``_SENHA_PADRAO`` e intencionalmente publica.
Este modulo e uma ferramenta de teste exclusiva do harness ``full-test/``
rodando contra instancia descartavel (docker compose local ou CI efemero).
Nunca importar/rodar contra banco de producao. O seed do admin real e feito
por ``scripts/seed_admin.py`` com envs ``ADMIN_EMAIL``/``ADMIN_PASSWORD``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.password_hasher import hash_senha
from src.autenticacao.infraestrutura.repository import UsuarioSQLAlchemyRepository
from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
from src.compartilhado.infraestrutura.database import (
    criar_engine,
    criar_session_factory,
)

# Senha publica de teste; ver docstring deste modulo.
_SENHA_PADRAO = "FullTestSecret123!"


@dataclass(frozen=True, slots=True)
class CredencialSeed:
    email: str
    senha: str
    papel: Papel


def credenciais_padrao(
    n_mecanicos: int, n_atendentes: int, admin_email: str
) -> list[CredencialSeed]:
    creds: list[CredencialSeed] = [
        CredencialSeed(email=admin_email, senha=_SENHA_PADRAO, papel=Papel.ADMIN),
    ]
    for i in range(n_mecanicos):
        creds.append(
            CredencialSeed(
                email=f"mecanico-{i:02d}@full-test.dev",
                senha=_SENHA_PADRAO,
                papel=Papel.MECANICO,
            )
        )
    for i in range(n_atendentes):
        creds.append(
            CredencialSeed(
                email=f"atendente-{i:02d}@full-test.dev",
                senha=_SENHA_PADRAO,
                papel=Papel.ATENDENTE,
            )
        )
    return creds


def semear(
    database_url: str,
    creds: list[CredencialSeed],
    admin_password: str,
) -> int:
    """Cria usuarios ausentes. Retorna quantidade de insercoes realizadas."""
    iniciar_todos_mapeamentos()
    engine = criar_engine(database_url)
    inseridos = 0
    try:
        session_factory = criar_session_factory(engine)
        for cred in creds:
            senha = admin_password if cred.papel == Papel.ADMIN else cred.senha
            with session_factory() as session:
                repo = UsuarioSQLAlchemyRepository(session=session)
                if repo.email_existe(cred.email):
                    continue
                usuario = Usuario.criar(
                    email=cred.email,
                    senha_hash=hash_senha(senha),
                    papel=cred.papel,
                )
                repo.salvar(usuario)
                session.commit()
                inseridos += 1
    finally:
        engine.dispose()
    return inseridos


def main() -> None:
    import sys

    from full_test.seeders.config import carregar_config

    config = carregar_config()
    creds = credenciais_padrao(
        n_mecanicos=max(config.n_operadores, 1),
        n_atendentes=max(config.n_operadores, 1),
        admin_email=config.admin_email,
    )
    inseridos = semear(config.database_url, creds, admin_password=config.admin_password)
    total = len(creds)
    restantes = total - inseridos
    print(f"Seed de usuarios: {inseridos}/{total} inseridos; {restantes} ja existiam.")
    sys.exit(0)


if __name__ == "__main__":
    main()
