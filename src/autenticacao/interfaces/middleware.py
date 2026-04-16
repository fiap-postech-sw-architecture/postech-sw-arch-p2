from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.autenticacao.dominio.exceptions import (
    TokenExpiradoException,
    TokenInvalidoException,
)
from src.autenticacao.interfaces.dependencies import obter_jwt_service
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_bearer_scheme = HTTPBearer(auto_error=False)


def obter_usuario_atual(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: Session = Depends(obter_session),
) -> dict[str, object]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacao nao fornecido",
        )
    try:
        jwt_service = obter_jwt_service()
        payload = jwt_service.validar_token(credentials.credentials)
        jti = payload.get("jti")
        if jti is not None:
            from src.autenticacao.infraestrutura.token_revogado_repository import (
                TokenRevogadoSQLAlchemyRepository,
            )

            token_repo = TokenRevogadoSQLAlchemyRepository(session=session)
            if token_repo.esta_revogado(str(jti)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revogado",
                )
        return payload
    except (TokenExpiradoException, TokenInvalidoException) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e.mensagem),
        ) from None


def exigir_papel(
    *papeis: str,
) -> Any:
    def verificar(
        usuario: dict[str, object] = Depends(obter_usuario_atual),
    ) -> dict[str, object]:
        papel = usuario.get("papel", "")
        if papel not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Papel nao autorizado",
            )
        return usuario

    return verificar
