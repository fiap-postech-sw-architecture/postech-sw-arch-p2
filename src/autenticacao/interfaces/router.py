from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Runtime import (nao TYPE_CHECKING): com `from __future__ import annotations`,
# o FastAPI avalia a annotation `Annotated[Session, Depends(...)]` em runtime;
# sem o nome no modulo, a resolucao da annotation falha no startup
# (PydanticUserError: not fully defined) — verificado empiricamente.
from sqlalchemy.orm import Session  # noqa: TC002
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

router = APIRouter(prefix="/api/v1/autenticacao", tags=["autenticacao"])

# auto_error=False: o HTTPBearer default responde 403 sem WWW-Authenticate
# para header ausente; o 401 manual abaixo espelha `obter_usuario_atual`.
_bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", summary="Autentica e emite par de tokens")
@limiter.limit("5/minute")
def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[Session, Depends(obter_session)],
) -> TokenResponse:
    """Valida e-mail + senha e devolve access + refresh tokens (rate limit 5/min).

    Credenciais invalidas -> 401 (mesma resposta para e-mail inexistente ou
    senha errada, evitando enumeration).
    """
    uc = obter_login(session)
    dto = LoginDTO(email=body.email, senha=body.senha)
    result = uc.executar(dto)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
    )


@router.post(
    "/registrar",
    status_code=status.HTTP_201_CREATED,
    summary="Registra um novo usuario (admin)",
)
@limiter.limit("5/minute")
def registrar(
    request: Request,
    body: RegistrarRequest,
    usuario: Annotated[dict[str, object], Depends(exigir_papel("admin"))],
    session: Annotated[Session, Depends(obter_session)],
) -> UsuarioResponse:
    """Cria um usuario com o papel informado. Endpoint admin-gated (RBAC).

    E-mail ja cadastrado -> 409. O papel e obrigatorio no corpo (nunca um
    admin silencioso por omissao).
    """
    uc = obter_registrar(session)
    dto = RegistrarDTO(email=body.email, senha=body.senha, papel=body.papel)
    result = uc.executar(dto)
    return UsuarioResponse(id=result.id, email=result.email, papel=result.papel)


@router.post("/logout", summary="Revoga o access e, opcionalmente, o refresh")
@limiter.limit("10/minute")
def logout(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    session: Annotated[Session, Depends(obter_session)],
    refresh_token: Annotated[str | None, Body(embed=True)] = None,
) -> dict[str, str]:
    """Revoga o access token do header; se o refresh vier no corpo, revoga-o tambem.

    Sem o refresh, encerra so o access (compat com clientes que so mandam o
    header). Header ausente -> 401.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacao nao fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # refresh_token e OPCIONAL no corpo (issue #118): quando enviado, o logout
    # revoga tambem o refresh e encerra a sessao por completo (CWE-613). Corpo
    # ausente mantem o comportamento anterior (revoga so o access) — sem 422
    # para clientes que so mandam o header.
    uc = obter_logout(session)
    return uc.executar(credentials.credentials, refresh_token=refresh_token)


@router.post("/refresh", summary="Rotaciona o par de tokens via refresh")
@limiter.limit("10/minute")
def refresh(
    request: Request,
    body: RefreshRequest,
    session: Annotated[Session, Depends(obter_session)],
) -> TokenResponse:
    """Troca um refresh token valido por um novo par (access + refresh).

    Single-use: o refresh apresentado e revogado atomicamente. Refresh
    invalido/expirado/ja consumido -> 401.
    """
    uc = obter_refresh_token(session)
    result = uc.executar(body.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
    )
