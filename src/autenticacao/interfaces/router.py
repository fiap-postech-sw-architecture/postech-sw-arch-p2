from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.requests import Request  # noqa: TC002

from src.autenticacao.aplicacao.dtos import LoginDTO, RegistrarDTO
from src.autenticacao.interfaces.dependencies import (
    obter_login,
    obter_logout,
    obter_refresh_token,
    obter_registrar,
)
from src.autenticacao.interfaces.middleware import exigir_papel
from src.autenticacao.interfaces.schemas import (
    LoginRequest,
    RefreshRequest,
    RegistrarRequest,
    TokenResponse,
    UsuarioResponse,
)
from src.compartilhado.interfaces.dependencies import obter_session
from src.compartilhado.interfaces.middleware import limiter

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/v1/autenticacao", tags=["Autenticacao"])

_bearer_scheme_required = HTTPBearer()


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
    session: Session = Depends(obter_session),
) -> TokenResponse:
    uc = obter_login(session)
    dto = LoginDTO(email=body.email, senha=body.senha)
    result = uc.executar(dto)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


@router.post("/registrar", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def registrar(
    request: Request,
    body: RegistrarRequest,
    usuario: dict[str, object] = Depends(exigir_papel("admin")),
    session: Session = Depends(obter_session),
) -> UsuarioResponse:
    uc = obter_registrar(session)
    dto = RegistrarDTO(email=body.email, senha=body.senha, papel=body.papel)
    result = uc.executar(dto)
    return UsuarioResponse(id=result.id, email=result.email, papel=result.papel)


@router.post("/logout")
@limiter.limit("10/minute")
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme_required),
    session: Session = Depends(obter_session),
) -> dict[str, str]:
    uc = obter_logout(session)
    return uc.executar(credentials.credentials)


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh(
    request: Request,
    body: RefreshRequest,
    session: Session = Depends(obter_session),
) -> TokenResponse:
    uc = obter_refresh_token(session)
    result = uc.executar(body.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )
