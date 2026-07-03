from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.autenticacao.dominio.exceptions import (
    TokenExpiradoException,
    TokenInvalidoException,
)
from src.autenticacao.dominio.papel import Papel
from src.autenticacao.interfaces.dependencies import obter_jwt_service
from src.compartilhado.interfaces.dependencies import obter_session

if TYPE_CHECKING:
    from collections.abc import Callable

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
        # TD-029: o gate de acesso so aceita access tokens; um refresh token
        # (type="refresh") nao pode autenticar uma requisicao -- espelha o check
        # `type == refresh` do fluxo de refresh. Defense-in-depth alem do RBAC.
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token nao e do tipo access",
            )
        jti = payload.get("jti")
        if jti is not None:
            from src.autenticacao.interfaces.dependencies import (
                obter_token_revogado_repo,
            )

            token_repo = obter_token_revogado_repo(session)
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


# Hierarquia de papeis: admin herda atendente e mecanico. Chaves e valores
# tipados como Papel (enum unico em dominio/) para evitar drift por string
# literal. MappingProxyType + frozenset impedem mutacao em tempo de execucao
# (defesa contra escalacao de privilegio via monkey-patch do _PERMISSOES).
_PERMISSOES: MappingProxyType[Papel, frozenset[Papel]] = MappingProxyType(
    {
        Papel.ADMIN: frozenset({Papel.ADMIN, Papel.ATENDENTE, Papel.MECANICO}),
        Papel.ATENDENTE: frozenset({Papel.ATENDENTE}),
        Papel.MECANICO: frozenset({Papel.MECANICO}),
    }
)


def exigir_papel(
    *papeis: str,
) -> Callable[..., dict[str, object]]:
    if not papeis:
        raise ValueError("exigir_papel requer ao menos um papel")
    try:
        papeis_exigidos: frozenset[Papel] = frozenset(Papel(p) for p in papeis)
    except ValueError as exc:
        raise ValueError(f"exigir_papel recebeu papel invalido: {exc}") from exc

    def verificar(
        usuario: dict[str, object] = Depends(obter_usuario_atual),
    ) -> dict[str, object]:
        raw = usuario.get("papel")
        papel: Papel | None
        if isinstance(raw, str):
            try:
                papel = Papel(raw)
            except ValueError:
                papel = None
        else:
            papel = None
        if papel is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Papel nao autorizado",
            )
        permissoes = _PERMISSOES.get(papel, frozenset())
        if not permissoes & papeis_exigidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Papel nao autorizado",
            )
        return usuario

    return verificar
