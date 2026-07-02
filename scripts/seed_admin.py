"""Script de seed: cria o usuario admin inicial se ainda nao existir.

Uso (container Docker, automatico via entrypoint.sh):
    RUN_SEED_ON_STARTUP=true docker compose up

Uso (manual, fora do container):
    make seed                          # carrega .env/.env.dev automaticamente
    python scripts/seed_admin.py       # requer envs exportadas no shell

Variaveis de ambiente obrigatorias:
    DATABASE_URL     conexao com o PostgreSQL (default dev/test: localhost).
    ADMIN_EMAIL      email do admin (normalizado para lowercase automaticamente).
    ADMIN_PASSWORD   senha do admin (>= 12 chars, sem placeholders publicos).

Idempotencia:
    Reexecucoes com o mesmo ``ADMIN_EMAIL`` sao no-op. Em caso de corrida
    entre replicas que iniciam simultaneamente, a UNIQUE constraint em
    ``usuarios.email`` faz o perdedor receber ``IntegrityError``, que este
    script trata como "ja existia".
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import EmailStr, TypeAdapter, ValidationError

# Garante que ``src.*`` seja importavel ao rodar ``python scripts/seed_admin.py``
# sem ``pip install -e .``. Idempotente: no-op se o projeto ja estiver no path.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


_PLACEHOLDERS_PROIBIDOS = frozenset(
    {
        "troque-esta-senha",
        "change-me",
        "changeme",
        "password",
        "admin",
        # Valor demo publico do repo (k8s/secret.yaml, docker-compose.yml).
        # Esta commitado e portanto nao e segredo -- nunca pode virar senha real.
        "pytstop-admin-demo-2026",
    }
)
_SENHA_MIN_LEN = 12


class _ConfigError(Exception):
    """Erro fatal de configuracao do seed; convertido em ``sys.exit(1)``."""


def ler_config(env: dict[str, str] | None = None) -> tuple[str, str, str]:
    """Valida envs e retorna ``(database_url, admin_email, admin_password)``.

    ``env`` e injetavel para testes; quando ``None``, usa ``os.environ``.
    Email e normalizado (``strip().lower()``). Senha e normalizada (``strip()``).
    """
    source = env if env is not None else dict(os.environ)
    environment = source.get("ENVIRONMENT", "development").lower()

    database_url = source.get("DATABASE_URL")
    if not database_url:
        if environment in {"development", "test"}:
            database_url = "postgresql://pytstop:pytstop@localhost:5432/pytstop"
        else:
            msg = (
                "DATABASE_URL obrigatoria quando ENVIRONMENT nao for "
                "'development' ou 'test'."
            )
            raise _ConfigError(msg)

    admin_email = (source.get("ADMIN_EMAIL") or "").strip().lower()
    if not admin_email:
        msg = "variavel ADMIN_EMAIL nao definida."
        raise _ConfigError(msg)
    try:
        TypeAdapter(EmailStr).validate_python(admin_email)
    except ValidationError as exc:
        msg = f"ADMIN_EMAIL invalido (seria rejeitado pelo login): {admin_email!r}"
        raise _ConfigError(msg) from exc

    admin_password = (source.get("ADMIN_PASSWORD") or "").strip()
    if not admin_password:
        msg = "variavel ADMIN_PASSWORD nao definida."
        raise _ConfigError(msg)
    if admin_password.lower() in _PLACEHOLDERS_PROIBIDOS:
        msg = "ADMIN_PASSWORD usa placeholder publico - troque antes de rodar o seed."
        raise _ConfigError(msg)
    if len(admin_password) < _SENHA_MIN_LEN:
        msg = f"ADMIN_PASSWORD deve ter pelo menos {_SENHA_MIN_LEN} caracteres."
        raise _ConfigError(msg)

    return database_url, admin_email, admin_password


def criar_admin_se_ausente(
    session_factory: Callable[[], Session],
    email: str,
    senha_hash: str,
) -> bool:
    """Cria admin se ``email`` nao existir. Retorna ``True`` se criou.

    Retorna ``False`` quando o email ja existe (branch idempotente) ou
    quando a UNIQUE constraint dispara ``IntegrityError`` (race entre
    replicas que iniciam em paralelo).
    """
    from sqlalchemy.exc import IntegrityError

    from src.autenticacao.dominio.papel import Papel
    from src.autenticacao.dominio.usuario import Usuario
    from src.autenticacao.infraestrutura.repository import UsuarioSQLAlchemyRepository

    with session_factory() as session:
        repo = UsuarioSQLAlchemyRepository(session=session)
        if repo.email_existe(email):
            return False
        usuario = Usuario.criar(email=email, senha_hash=senha_hash, papel=Papel.ADMIN)
        try:
            repo.salvar(usuario)
            session.commit()
        except IntegrityError:
            session.rollback()
            return False
    return True


def main() -> None:
    try:
        database_url, admin_email, admin_password = ler_config()
    except _ConfigError as exc:
        print(f"ERRO: {exc}")
        sys.exit(1)

    from src.autenticacao.infraestrutura.password_hasher import hash_senha
    from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
    from src.compartilhado.infraestrutura.database import (
        criar_engine,
        criar_session_factory,
    )

    iniciar_todos_mapeamentos()

    engine = criar_engine(database_url)
    try:
        session_factory = criar_session_factory(engine)
        senha_hash = hash_senha(admin_password)
        criou = criar_admin_se_ausente(session_factory, admin_email, senha_hash)
    finally:
        engine.dispose()

    if criou:
        print(f"Usuario admin '{admin_email}' criado com sucesso.")
    else:
        print(f"Usuario admin '{admin_email}' ja existe. Nenhuma acao necessaria.")


if __name__ == "__main__":
    main()
