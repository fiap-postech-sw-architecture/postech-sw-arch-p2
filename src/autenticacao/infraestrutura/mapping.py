from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Table, Uuid, event
from sqlalchemy.orm import registry

from src.autenticacao.dominio.papel import Papel
from src.autenticacao.dominio.token_revogado import TokenRevogado
from src.autenticacao.dominio.usuario import Usuario
from src.compartilhado.infraestrutura.database import metadata

usuarios_table = Table(
    "usuarios",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("senha_hash", String(255), nullable=False),
    Column("papel", String(20), nullable=False),
)

tokens_revogados_table = Table(
    "tokens_revogados",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("jti", String(255), nullable=False, unique=True, index=True),
    Column(
        "revogado_em",
        DateTime(timezone=True),
        nullable=False,
    ),
)

_mapeamento_iniciado = False


def iniciar_mapeamentos() -> None:
    global _mapeamento_iniciado  # noqa: PLW0603  # init-once flag
    if _mapeamento_iniciado:
        return
    _mapeamento_iniciado = True  # codeql[py/unused-global-variable] -- lida na guarda

    mapper_registry = registry()

    mapper_registry.map_imperatively(
        Usuario,
        usuarios_table,
        properties={
            "id": usuarios_table.c.id,
            "_email": usuarios_table.c.email,
            "_senha_hash": usuarios_table.c.senha_hash,
            "_papel_valor": usuarios_table.c.papel,
        },
    )

    mapper_registry.map_imperatively(
        TokenRevogado,
        tokens_revogados_table,
        properties={
            "id": tokens_revogados_table.c.id,
            "_jti": tokens_revogados_table.c.jti,
            "_revogado_em": tokens_revogados_table.c.revogado_em,
        },
    )

    @event.listens_for(Usuario, "load")
    def _reconstruir_usuario(target: Usuario, _context: object) -> None:
        # _papel_valor is a synthetic attribute injected by SQLAlchemy mapping.
        target.__dict__["_papel"] = Papel(target._papel_valor)  # type: ignore[attr-defined]
        object.__setattr__(target, "_id_atribuido", True)
        object.__setattr__(target, "_eventos_pendentes", [])

    @event.listens_for(TokenRevogado, "load")
    def _reconstruir_token(target: TokenRevogado, _context: object) -> None:
        object.__setattr__(target, "_id_atribuido", True)

    @event.listens_for(Usuario, "before_insert")
    @event.listens_for(Usuario, "before_update")
    def _decompor_papel(_mapper: object, _connection: object, target: Usuario) -> None:
        target._papel_valor = target._papel.value
