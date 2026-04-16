from __future__ import annotations

from uuid import UUID

import pytest

from src.autenticacao.aplicacao.dtos import LoginDTO, RegistrarDTO
from src.autenticacao.aplicacao.use_cases import Login, Logout, RefreshToken, Registrar
from src.autenticacao.dominio.exceptions import (
    CredenciaisInvalidasException,
    EmailDuplicadoException,
    TokenInvalidoException,
    TokenRevogadoException,
)
from src.autenticacao.dominio.usuario import Usuario
from src.autenticacao.infraestrutura.jwt_service import JWTService
from src.autenticacao.infraestrutura.password_hasher import hash_senha


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeUsuarioRepository:
    def __init__(self) -> None:
        self._usuarios: dict[UUID, Usuario] = {}

    def obter_por_id(self, usuario_id: UUID) -> Usuario | None:
        return self._usuarios.get(usuario_id)

    def obter_por_email(self, email: str) -> Usuario | None:
        for u in self._usuarios.values():
            if u.email == email:
                return u
        return None

    def salvar(self, usuario: Usuario) -> None:
        self._usuarios[usuario.id] = usuario

    def email_existe(self, email: str) -> bool:
        return any(u.email == email for u in self._usuarios.values())


class FakeTokenRevogadoRepository:
    def __init__(self) -> None:
        self._revogados: set[str] = set()

    def revogar(self, jti: str) -> None:
        self._revogados.add(jti)

    def esta_revogado(self, jti: str) -> bool:
        return jti in self._revogados


class TestRegistrar:
    def test_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow)
        dto = RegistrarDTO(email="test@test.com", senha="senhaforte1234")
        result = uc.executar(dto)
        assert result.email == "test@test.com"
        assert result.papel == "admin"

    def test_email_duplicado(self) -> None:
        repo = FakeUsuarioRepository()
        uow = FakeUnitOfWork()
        uc = Registrar(repo=repo, uow=uow)
        dto = RegistrarDTO(email="test@test.com", senha="senhaforte1234")
        uc.executar(dto)
        with pytest.raises(EmailDuplicadoException):
            uc.executar(dto)


class TestLogin:
    def test_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc)
        dto = LoginDTO(email="test@test.com", senha="senhaforte1234")
        result = uc.executar(dto)
        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"

    def test_retorna_access_e_refresh(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc)
        dto = LoginDTO(email="test@test.com", senha="senhaforte1234")
        result = uc.executar(dto)
        access_payload = jwt_svc.validar_token(result.access_token)
        refresh_payload = jwt_svc.validar_token(result.refresh_token)
        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    def test_email_nao_encontrado(self) -> None:
        repo = FakeUsuarioRepository()
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc)
        with pytest.raises(CredenciaisInvalidasException):
            uc.executar(LoginDTO(email="x@x.com", senha="senhaerrada12"))

    def test_senha_incorreta(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        uc = Login(repo=repo, jwt_service=jwt_svc)
        with pytest.raises(CredenciaisInvalidasException):
            uc.executar(LoginDTO(email="test@test.com", senha="erradaerrada1"))


class TestLogout:
    def test_revoga_jti_do_token(self) -> None:
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        token = jwt_svc.gerar_access_token(uuid4(), "t@t.com", "admin")
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)
        result = uc.executar(token)
        assert "mensagem" in result
        payload = jwt_svc.validar_token(token)
        assert token_repo.esta_revogado(str(payload["jti"]))

    def test_retorna_confirmacao(self) -> None:
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        token = jwt_svc.gerar_access_token(uuid4(), "t@t.com", "admin")
        uc = Logout(jwt_service=jwt_svc, token_repo=token_repo, uow=uow)
        result = uc.executar(token)
        assert result["mensagem"] == "Logout realizado com sucesso"


class TestRefreshToken:
    def test_rotacao_sucesso(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        old_payload = jwt_svc.validar_token(refresh)
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        result = uc.executar(refresh)
        assert result.access_token
        assert result.refresh_token
        assert token_repo.esta_revogado(str(old_payload["jti"]))

    def test_rejeita_access_token_como_refresh(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        access = jwt_svc.gerar_access_token(usuario.id, "test@test.com", "admin")
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(TokenInvalidoException, match="Token nao e do tipo refresh"):
            uc.executar(access)

    def test_rejeita_token_ja_revogado(self) -> None:
        repo = FakeUsuarioRepository()
        usuario = Usuario.criar(
            email="test@test.com", senha_hash=hash_senha("senhaforte1234")
        )
        repo.salvar(usuario)
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        refresh = jwt_svc.gerar_refresh_token(usuario.id)
        payload = jwt_svc.validar_token(refresh)
        token_repo.revogar(str(payload["jti"]))
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(TokenRevogadoException):
            uc.executar(refresh)

    def test_usuario_inexistente(self) -> None:
        repo = FakeUsuarioRepository()
        jwt_svc = JWTService(chave_secreta="test-secret")
        token_repo = FakeTokenRevogadoRepository()
        uow = FakeUnitOfWork()
        from uuid import uuid4

        refresh = jwt_svc.gerar_refresh_token(uuid4())
        uc = RefreshToken(
            jwt_service=jwt_svc,
            token_repo=token_repo,
            usuario_repo=repo,
            uow=uow,
        )
        with pytest.raises(
            CredenciaisInvalidasException, match="Usuario nao encontrado"
        ):
            uc.executar(refresh)
