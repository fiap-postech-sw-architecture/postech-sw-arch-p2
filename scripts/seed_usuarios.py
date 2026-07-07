"""Script de seed: cria admin + atendente + mecanico se ausentes.

Complementa ``scripts/seed_admin.py``: enquanto aquele cria o admin inicial
via env vars para bootstrap de producao, este popula os 3 papeis com
credenciais FIXAS em ``ui/config.py`` para uso exclusivo da UI de simulacao
em dev. Escreve direto no banco para bootstrap idempotente sem depender da
API (o endpoint ``/registrar`` aceita ``papel`` desde a issue #84, mas exige
um admin ja autenticado — circular para o seed inicial).

Uso:
    make seed-users                            # local (envs vem de .env)
    make seed-users-docker                     # via docker compose
    python scripts/seed_usuarios.py            # manual

Cloud (ADR-025 adendo): ``SEED_PAPEIS`` restringe quais papeis criar (CSV,
ex. ``ATENDENTE,MECANICO`` — o admin do cloud vem do Job de migracao e nao
e' tocado) e ``SEED_SENHA_<PAPEL>`` substitui a senha dev publica por uma
forte do ``.env.cloud``. Em ``ENVIRONMENT=production`` o seed SO roda se
todo papel selecionado tiver senha via env — a guarda contra plantar senha
publica em ambiente exposto continua valendo.

Idempotencia: checagem primaria via ``email_existe``; UNIQUE constraint em
``usuarios.email`` cobre race conditions como fallback.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

# Garante que ``src.*`` seja importavel ao rodar ``python scripts/seed_usuarios.py``
# sem ``pip install -e .``. Idempotente: no-op se o projeto ja estiver no path.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RelatorioSeed:
    criados: int
    existentes: int

    def resumo(self) -> str:
        return f"{self.criados} criados, {self.existentes} ja existiam"


# Mapeamento (nome_do_papel, email, senha). Espelho de ``ui/config.py``;
# manter sincronizado (drift checado por test_credenciais_sincronizadas_com_ui_config).
# O primeiro elemento e o NOME do enum ``Papel`` (ex: ``"ADMIN"``) para evitar
# importar ``src.*`` no escopo de modulo. Conversao via ``Papel[nome]`` dentro
# de ``criar_usuarios_seed``. Senhas dev-only com >=12 chars.
_USUARIOS_FIXOS: list[tuple[str, str, str]] = [
    ("ADMIN", "admin@pytstop.dev", "admin-dev-pass-2026"),
    ("ATENDENTE", "atendente@pytstop.dev", "atendente-dev-pass-2026"),
    ("MECANICO", "mecanico@pytstop.dev", "mecanico-dev-pass-2026"),
]


def criar_usuarios_seed(
    session_factory: Callable[[], Session],
    hasher: Callable[[str], str],
    papeis: frozenset[str] | None = None,
    senhas: dict[str, str] | None = None,
) -> RelatorioSeed:
    """Cria os papeis selecionados se ausentes. Retorna criados/existentes.

    ``papeis`` restringe o subconjunto (nomes do enum, ex. ``{"ATENDENTE"}``;
    ``None`` = todos). ``senhas`` substitui a senha dev fixa por papel —
    e' o que permite seed em cloud com senha forte (ADR-025 adendo).
    """
    from sqlalchemy.exc import IntegrityError

    from src.autenticacao.dominio.papel import Papel
    from src.autenticacao.dominio.usuario import Usuario
    from src.autenticacao.infraestrutura.repository import UsuarioSQLAlchemyRepository

    criados = 0
    existentes = 0
    for papel_name, email, senha_fixa in _USUARIOS_FIXOS:
        if papeis is not None and papel_name not in papeis:
            continue
        senha = (senhas or {}).get(papel_name, senha_fixa)
        papel = Papel[papel_name]
        with session_factory() as session:
            repo = UsuarioSQLAlchemyRepository(session=session)
            if repo.email_existe(email):
                existentes += 1
                continue
            usuario = Usuario.criar(
                email=email,
                senha_hash=hasher(senha),
                papel=papel,
            )
            try:
                repo.salvar(usuario)
                session.commit()
                criados += 1
            except IntegrityError:
                session.rollback()
                existentes += 1
    return RelatorioSeed(criados=criados, existentes=existentes)


def main() -> None:
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    papeis_brutos = os.environ.get("SEED_PAPEIS", "ADMIN,ATENDENTE,MECANICO")
    papeis = frozenset(p.strip().upper() for p in papeis_brutos.split(",") if p.strip())
    senhas = {
        papel_name: valor
        for papel_name, _, _ in _USUARIOS_FIXOS
        if (valor := os.environ.get(f"SEED_SENHA_{papel_name}"))
    }
    # Guarda de ambiente (espelha scripts/seed_admin.py): as senhas FIXAS de
    # _USUARIOS_FIXOS sao publicas (tambem em ui/config.py e nas imagens GHCR
    # publicas) — plantar qualquer uma delas fora de dev/test abriria login
    # conhecido num ambiente exposto. Em production o seed SO passa quando
    # TODO papel selecionado tem senha propria via SEED_SENHA_<PAPEL>
    # (ADR-025 adendo: atendente/mecanico com senha forte do .env.cloud).
    if environment not in {"development", "test"} and not papeis <= set(senhas):
        sem_env = sorted(papeis - set(senhas))
        print(
            "ERRO: em ENVIRONMENT "
            f"{environment!r} seed_usuarios exige SEED_SENHA_<PAPEL> para todo "
            f"papel selecionado (sem senha via env: {', '.join(sem_env)}); "
            "senhas dev publicas nao podem ir para ambiente exposto."
        )
        sys.exit(1)
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_url = "postgresql://pytstop:pytstop@localhost:5432/pytstop"

    from src.autenticacao.infraestrutura.password_hasher import hash_senha
    from src.compartilhado.infraestrutura.bootstrap import iniciar_todos_mapeamentos
    from src.compartilhado.infraestrutura.database import (
        criar_engine,
        criar_session_factory,
    )

    iniciar_todos_mapeamentos()
    engine = criar_engine(database_url)
    try:
        relatorio = criar_usuarios_seed(
            session_factory=criar_session_factory(engine),
            hasher=hash_senha,
            papeis=papeis,
            senhas=senhas,
        )
    finally:
        engine.dispose()

    print(f"Seed de usuarios ({', '.join(sorted(papeis))}): {relatorio.resumo()}.")


if __name__ == "__main__":
    main()
