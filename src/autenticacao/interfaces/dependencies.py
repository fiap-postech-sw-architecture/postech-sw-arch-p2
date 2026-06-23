from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src.autenticacao.infraestrutura.jwt_service import JWTService
from src.autenticacao.infraestrutura.password_hasher import PasswordHasher

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.autenticacao.aplicacao.use_cases import (
        Login,
        Logout,
        RefreshToken,
        Registrar,
    )


def obter_jwt_service() -> JWTService:
    chave = os.environ.get("JWT_SECRET")
    if not chave:
        msg = "JWT_SECRET nao configurado"
        raise RuntimeError(msg)
    expiracao = int(os.environ.get("JWT_EXPIRATION_MINUTES", "30"))
    return JWTService(chave_secreta=chave, expiracao_minutos=expiracao)


def obter_registrar(session: Session) -> Registrar:
    from src.autenticacao.aplicacao.use_cases import Registrar
    from src.autenticacao.infraestrutura.repository import (
        UsuarioSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return Registrar(
        repo=UsuarioSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
        password_hasher=PasswordHasher(),
    )


def obter_login(session: Session) -> Login:
    from src.autenticacao.aplicacao.use_cases import Login
    from src.autenticacao.infraestrutura.repository import (
        UsuarioSQLAlchemyRepository,
    )

    return Login(
        repo=UsuarioSQLAlchemyRepository(session=session),
        jwt_service=obter_jwt_service(),
        password_hasher=PasswordHasher(),
    )


def obter_logout(session: Session) -> Logout:
    from src.autenticacao.aplicacao.use_cases import Logout
    from src.autenticacao.infraestrutura.token_revogado_repository import (
        TokenRevogadoSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return Logout(
        jwt_service=obter_jwt_service(),
        token_repo=TokenRevogadoSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )


def obter_refresh_token(session: Session) -> RefreshToken:
    from src.autenticacao.aplicacao.use_cases import RefreshToken
    from src.autenticacao.infraestrutura.repository import (
        UsuarioSQLAlchemyRepository,
    )
    from src.autenticacao.infraestrutura.token_revogado_repository import (
        TokenRevogadoSQLAlchemyRepository,
    )
    from src.compartilhado.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork

    return RefreshToken(
        jwt_service=obter_jwt_service(),
        token_repo=TokenRevogadoSQLAlchemyRepository(session=session),
        usuario_repo=UsuarioSQLAlchemyRepository(session=session),
        uow=SQLAlchemyUnitOfWork(session_factory=lambda: session),
    )
