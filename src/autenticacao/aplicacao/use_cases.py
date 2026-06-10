from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from src.autenticacao.aplicacao.dtos import TokenDTO, UsuarioDTO
from src.autenticacao.dominio.exceptions import (
    CredenciaisInvalidasException,
    EmailDuplicadoException,
    TokenInvalidoException,
    TokenRevogadoException,
)
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.password_hasher import (
    hash_senha,
    verificar_senha,
)

if TYPE_CHECKING:
    from src.autenticacao.aplicacao.dtos import LoginDTO, RegistrarDTO
    from src.autenticacao.dominio.repository import (
        TokenRevogadoRepository,
        UsuarioRepository,
    )
    from src.autenticacao.infraestrutura.jwt_service import JWTService
    from src.compartilhado.aplicacao.unit_of_work import UnitOfWork


class Registrar:
    def __init__(self, repo: UsuarioRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    def executar(self, dto: RegistrarDTO) -> UsuarioDTO:
        if self._repo.email_existe(dto.email):
            raise EmailDuplicadoException()
        senha_hash = hash_senha(dto.senha)
        usuario = Usuario.criar(email=dto.email, senha_hash=senha_hash)
        with self._uow:
            self._repo.salvar(usuario)
            self._uow.commit()
        return UsuarioDTO(id=usuario.id, email=usuario.email, papel=usuario.papel.value)


class Login:
    def __init__(self, repo: UsuarioRepository, jwt_service: JWTService) -> None:
        self._repo = repo
        self._jwt_service = jwt_service

    def executar(self, dto: LoginDTO) -> TokenDTO:
        usuario = self._repo.obter_por_email(dto.email)
        if usuario is None:
            raise CredenciaisInvalidasException()
        if not verificar_senha(dto.senha, usuario.senha_hash):
            raise CredenciaisInvalidasException()
        access = self._jwt_service.gerar_access_token(
            usuario_id=usuario.id,
            email=usuario.email,
            papel=usuario.papel.value,
        )
        refresh = self._jwt_service.gerar_refresh_token(
            usuario_id=usuario.id,
        )
        return TokenDTO(access_token=access, refresh_token=refresh)


class Logout:
    def __init__(
        self,
        jwt_service: JWTService,
        token_repo: TokenRevogadoRepository,
        uow: UnitOfWork,
    ) -> None:
        self._jwt_service = jwt_service
        self._token_repo = token_repo
        self._uow = uow

    def executar(self, token: str) -> dict[str, str]:
        payload = self._jwt_service.validar_token(token)
        jti = str(payload["jti"])
        with self._uow:
            self._token_repo.revogar(jti)
            self._uow.commit()
        return {"mensagem": "Logout realizado com sucesso"}


class RefreshToken:
    def __init__(
        self,
        jwt_service: JWTService,
        token_repo: TokenRevogadoRepository,
        usuario_repo: UsuarioRepository,
        uow: UnitOfWork,
    ) -> None:
        self._jwt_service = jwt_service
        self._token_repo = token_repo
        self._usuario_repo = usuario_repo
        self._uow = uow

    def executar(self, refresh_token: str) -> TokenDTO:
        payload = self._jwt_service.validar_token(refresh_token)
        if payload.get("type") != "refresh":
            raise TokenInvalidoException(mensagem="Token nao e do tipo refresh")
        jti = str(payload["jti"])
        if self._token_repo.esta_revogado(jti):
            raise TokenRevogadoException()
        usuario_id = UUID(str(payload["sub"]))
        usuario = self._usuario_repo.obter_por_id(usuario_id)
        if usuario is None:
            raise CredenciaisInvalidasException(mensagem="Usuario nao encontrado")
        with self._uow:
            self._token_repo.revogar(jti)
            self._uow.commit()
        access = self._jwt_service.gerar_access_token(
            usuario_id=usuario.id,
            email=usuario.email,
            papel=usuario.papel.value,
        )
        refresh = self._jwt_service.gerar_refresh_token(
            usuario_id=usuario.id,
        )
        return TokenDTO(access_token=access, refresh_token=refresh)
